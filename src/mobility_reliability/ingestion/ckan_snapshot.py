"""Recopilador de snapshots CKAN para los dos datasets aprobados de Cuenca en Datos.

Alcance (según ``docs/source-contract.md``)
-------------------------------------------
Solo pueden capturarse los dos datasets aprobados: rutas
(``rutas-de-transporte-publico``) y paradas (``paradas-de-transporte-publico``),
ambos declarados ``CC BY-NC 2.0`` en el portal CKAN del Municipio de Cuenca.
La geometría de rutas (recorrido), los snapshots históricos masivos, el clima
y cualquier otra fuente quedan fuera de alcance y fallan antes de cualquier
acceso a red. Solo se captura el estado publicado actual; no ocurre ninguna
recopilación histórica masiva.

API pública
-----------
- ``CKAN_PACKAGE_SHOW_URLS``: las dos URLs package_show aprobadas (ningún otro
  endpoint).
- ``DATASET_SPECS``: política de adquisición por dataset (``source_id``,
  licencia declarada, formatos permitidos, versión de esquema, atribución).
- ``CkanSnapshotCollector(raw_dir, manifest_dir, *, transport=None, clock=None)``
  con ``collect(dataset_id)`` que devuelve un manifest serializable a JSON y
  escribe:
  - ``raw_dir/<dataset_id>/<UTC-stamp>.json`` — los bytes exactos del resource;
  - ``manifest_dir/<dataset_id>/<UTC-stamp>.manifest.json`` — el manifest.
  Puede inyectarse un ``transport`` con tipado duck que exponga
  ``get(url, **kwargs)`` y devuelva una respuesta con
  ``status_code``/``headers``/``content`` (por defecto: un pequeño adaptador
  ``urllib``). Puede inyectarse un ``clock`` con tipado duck que exponga
  ``now()`` y devuelva un ``datetime`` UTC con zona horaria (por defecto:
  reloj UTC del sistema). Los valores de reloj ingenuos se rechazan antes de
  cualquier acceso a red.
- ``supersede_orphan_manifest(manifest_path, raw_dir, sidecar_path=None)``:
  reparación offline que escribe un sidecar exclusivo
  ``.manifest.correction.json`` junto a un manifest fallido cuyo archivo raw
  reclamado falta (ver más abajo).

Estados del manifest
--------------------
- ``success``: huella de licencia verificada, un resource compatible
  descargado con un ``Content-Length`` que coincide con el cuerpo recibido;
  los bytes exactos se conservan bajo la ruta raw determinista y
  ``content_hash`` es su SHA-256. ``warnings`` y ``notes`` están vacíos en
  una captura limpia (un título de licencia CKAN genérico añade una
  advertencia).
- ``partial``: desajuste de ``Content-Length`` — los bytes recibidos se
  conservan exactamente y se les calcula el hash; el snapshot nunca se marca
  como success.
- ``failed``: fallos de paquete/HTTP/red/licencia/formato/cuerpo — se escribe
  un manifest con ``warnings``/``notes`` no vacíos. Los fallos previos a la
  descarga nunca reclaman un archivo raw: ``raw_file``/``content_hash``/
  ``row_count`` permanecen null. Cuando el cuerpo del resource se descarga
  pero falla la decodificación/análisis del CSV (p. ej. UTF-8 inválido), los
  bytes exactos se conservan primero bajo la ruta raw determinista y se les
  calcula el hash desde el archivo en disco; el manifest fallido entonces
  referencia ese archivo raw con ``row_count`` null.

Selección del resource
----------------------
Solo los resources CSV son elegibles. Se excluyen los resources cuyo
id/name/description/url identifiquen geometría, datos geoespaciales,
geometría de rutas (recorrido) o shapes (p. ej.
``GADCuenca_ParadasTransporteGeo_*``), así como los formatos ZIP/ODS y otros.
Entre los resources CSV restantes con metadatos válidos y una URL http(s)
absoluta, se selecciona el más nuevo de forma determinista: la clave de
recencia es la señal más reciente entre la fecha de corte de datos incrustada
en el name/description (año de 4 dígitos con nombre de mes en español o
inglés — p. ej. ``2025Abril``/``2022Septiembre`` — o un mes numérico) y las
fechas de metadatos del resource (``metadata_modified``, ``last_modified``,
``created``), con cada señal en ese orden y finalmente el id estable del
resource como desempate. La selección nunca es posicional.

Integridad de la persistencia
-----------------------------
``content_hash`` siempre se calcula desde, y se verifica contra, el archivo
raw en disco antes de escribir el manifest que lo contiene; un fallo de
verificación elimina el archivo raw y lanza ``OSError``, sin dejar ningún
manifest. Los destinos raw y manifest se crean de forma exclusiva
(``xb``/``x``) y nunca se sobrescriben.

Compuerta de licencia (antes de cualquier descarga del resource)
----------------------------------------------------------------
La huella de licencia publicada debe satisfacer todo lo siguiente: un
``license_title`` no vacío; ``license_id`` igual a ``cc-nc``; y la URL
oficial de la licencia CC BY-NC 2.0 (esquema ``http`` o ``https``,
``creativecommons.org/licenses/by-nc/2.0``, barra final opcional). El título
exacto ``"CC BY-NC 2.0"`` es limpio; cualquier otro título (p. ej. el título
genérico CKAN en vivo ``"Creative Commons Non-Commercial (Cualquiera)"``)
añade una advertencia que contiene ``genérico``. ``license_declared``
permanece ``"CC BY-NC 2.0"`` mientras que ``license_published``,
``license_id``, ``license_url`` e ``isopen`` conservan los valores
publicados, y ``restrictions`` registra ``["NonCommercial"]`` para la huella
compatible.

Preflight (sin acceso a red, sin escrituras)
--------------------------------------------
Los dataset ids desconocidos lanzan ``ValueError``; los destinos raw o
manifest existentes lanzan ``FileExistsError``. Nada se sobrescribe jamás.

Reparación offline de manifests huérfanos
-----------------------------------------
``supersede_orphan_manifest(manifest_path, raw_dir, sidecar_path=None)`` lee
un manifest fallido cuyo archivo raw reclamado falta (la ruta raw debe ser
relativa y permanecer dentro de ``raw_dir``; el raw reclamado no debe
existir) y escribe un sidecar exclusivo junto a él — por defecto el nombre
del manifest con un sufijo ``.manifest.correction.json``. El sidecar registra
``status: "superseded"``, ``raw_verifiable: false``, ``raw_file``/
``content_hash`` de nivel superior null, y la ruta/hash raw originales solo
bajo ``unverified_original_claims``; declara que no hay ningún raw
disponible y que el hash original no está confirmado. El manifest original
nunca se reescribe y no ocurre ningún acceso a red.

CLI
---
``python -m mobility_reliability.ingestion.ckan_snapshot --dataset routes``
``python -m mobility_reliability.ingestion.ckan_snapshot --dataset stops``
(``--dataset all`` ejecuta ambos; ``--raw-dir``/``--manifest-dir`` tienen por
defecto ``data/raw``/``data/manifests``).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import urllib.request
from copy import deepcopy
from datetime import UTC, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

__all__ = [
    "CKAN_PACKAGE_SHOW_URLS",
    "DATASET_SPECS",
    "CkanSnapshotCollector",
    "LICENSE_DECLARED",
    "RETRIEVAL_METHOD",
    "main",
    "supersede_orphan_manifest",
]

RETRIEVAL_METHOD = "public documented CKAN API"
LICENSE_DECLARED = "CC BY-NC 2.0"
_APPROVED_LICENSE_ID = "cc-nc"
_APPROVED_LICENSE_HOST = "creativecommons.org"
_APPROVED_LICENSE_PATH = "/licenses/by-nc/2.0"
_LICENSE_URL_CANONICAL = "http://creativecommons.org/licenses/by-nc/2.0/"
CUENCA_ATTRIBUTION = "Municipio de Cuenca — Cuenca en Datos (portal oficial de datos abiertos)"

ROUTES_DATASET_ID = "rutas-de-transporte-publico"
STOPS_DATASET_ID = "paradas-de-transporte-publico"

CKAN_PACKAGE_SHOW_URLS = {
    ROUTES_DATASET_ID: ("https://cuencaendatos.cuenca.gob.ec/api/3/action/package_show?id=rutas-de-transporte-publico"),
    STOPS_DATASET_ID: (
        "https://cuencaendatos.cuenca.gob.ec/api/3/action/package_show?id=paradas-de-transporte-publico"
    ),
}

DATASET_SPECS = {
    ROUTES_DATASET_ID: {
        "source_id": "cuenca-en-datos-routes",
        "license_declared": LICENSE_DECLARED,
        "allowed_formats": ("CSV",),
        "schema_version": 1,
        "attribution": CUENCA_ATTRIBUTION,
    },
    STOPS_DATASET_ID: {
        "source_id": "cuenca-en-datos-stops",
        "license_declared": LICENSE_DECLARED,
        "allowed_formats": ("CSV",),
        "schema_version": 1,
        "attribution": CUENCA_ATTRIBUTION,
    },
}

# Marcadores geometry/geoespaciales comparados sin distinguir mayúsculas en
# el id, name, description y url del resource (ver ``_is_geometric``).
_GEOMETRY_MARKERS = (
    "geometry",
    "geometri",
    "geospatial",
    "geoespacial",
    "georreferencia",
    "georeferenc",
    "recorrido",
    "shape",
    "geo",
)

_MONTH_NAMES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# "2025Abril", "2022Septiembre", "2022-09" (año primero, en los nombres).
_YEAR_FIRST_DATE = re.compile(r"(\d{4})\s*(?:[-/.]\s*)?([a-záéíóúñü]+|\d{1,2})")
# "corte a septiembre del 2022" / "abril de 2025" (mes primero, en las descripciones).
_MONTH_FIRST_DATE = re.compile(r"([a-záéíóúñü]+)\s+(?:del|de)?\s+(\d{4})")


class _Response:
    """Respuesta mínima que expone la superficie contratada."""

    def __init__(self, status_code: int, content: bytes, headers: dict | None = None):
        self.status_code = status_code
        self.content = content
        self.headers = dict(headers or {})


class UrllibTransport:
    """Transport por defecto: adaptador ``urllib`` de la stdlib (sin dependencias de terceros)."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def get(self, url: str, **kwargs) -> _Response:
        timeout = kwargs.get("timeout", self.timeout)
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return _Response(response.status, response.read(), dict(response.headers.items()))


class _UtcClock:
    """Reloj por defecto: hora actual como datetime UTC con zona horaria."""

    def now(self, tz: timezone = UTC) -> datetime:
        return datetime.now(tz)


class CkanSnapshotCollector:
    """Recopila un snapshot CKAN actual por dataset aprobado, fail closed."""

    def __init__(
        self,
        raw_dir: str | Path,
        manifest_dir: str | Path,
        *,
        transport: object | None = None,
        clock: object | None = None,
    ):
        self.raw_dir = Path(raw_dir)
        self.manifest_dir = Path(manifest_dir)
        self.transport = transport if transport is not None else UrllibTransport()
        self.clock = clock if clock is not None else _UtcClock()

    # -- público -------------------------------------------------------------

    def collect(self, dataset_id: str) -> dict:
        """Captura ``dataset_id`` y devuelve su manifest (success/partial/failed).

        Lanza ``ValueError`` para dataset ids desconocidos y ``FileExistsError``
        cuando el destino determinista raw o manifest ya existe — ambos antes
        de cualquier acceso a red y antes de cualquier escritura.
        """
        if dataset_id not in CKAN_PACKAGE_SHOW_URLS:
            raise ValueError(
                f"dataset id desconocido: {dataset_id!r}; se esperaba uno de {sorted(CKAN_PACKAGE_SHOW_URLS)}"
            )
        spec = DATASET_SPECS[dataset_id]

        now = self.clock.now()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("clock.now() debe devolver un datetime UTC con zona horaria")
        now_utc = now.astimezone(UTC)
        stamp = now_utc.strftime("%Y-%m-%dT%H-%M-%SZ")
        iso_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        raw_path = self.raw_dir / dataset_id / f"{stamp}.json"
        manifest_path = self.manifest_dir / dataset_id / f"{stamp}.manifest.json"
        self._preflight(raw_path, manifest_path)

        source_url = CKAN_PACKAGE_SHOW_URLS[dataset_id]
        manifest = self._base_manifest(dataset_id, spec, source_url, iso_utc, stamp)
        relative_raw_file = f"{dataset_id}/{stamp}.json"

        result = self._fetch_package(source_url, manifest, manifest_path)
        if result is None:
            return manifest
        self._attach_source_metadata(manifest, result)
        if not self._check_license(manifest, spec, result, manifest_path):
            return manifest
        selected = self._select_resource(manifest, spec, result, manifest_path)
        if selected is None:
            return manifest
        self._attach_resource(manifest, selected)

        response = self._fetch_resource(manifest, selected["url"], manifest_path)
        if response is None:
            return manifest
        body = bytes(response.content)

        declared_length = self._declared_content_length(response.headers)
        if declared_length is not None and declared_length != len(body):
            manifest["status"] = "partial"
            manifest["warnings"].append(
                f"desajuste de Content-Length: se declararon {declared_length} bytes, se recibieron {len(body)} bytes"
            )
            manifest["notes"] = (
                f"Descarga parcial para {dataset_id}: los bytes recibidos se conservan en "
                f"{relative_raw_file}; el snapshot no se marca como success."
            )
            self._persist_snapshot(
                manifest_path,
                manifest,
                raw_path,
                body,
                relative_raw_file,
                status="partial",
                row_count=None,
            )
            return manifest

        row_count, invalid_reason = self._validate_body(manifest, manifest["resource_format"], body)
        if invalid_reason is not None:
            # Los bytes exactos se conservan antes de escribir el manifest
            # fallido; el hash se calcula desde el archivo raw en disco.
            manifest["status"] = "failed"
            manifest["warnings"] = [invalid_reason]
            manifest["notes"] = f"Falló la validación del cuerpo para {dataset_id}: {invalid_reason}"
            self._persist_snapshot(
                manifest_path,
                manifest,
                raw_path,
                body,
                relative_raw_file,
                status="failed",
                row_count=None,
            )
            return manifest
        self._persist_snapshot(
            manifest_path,
            manifest,
            raw_path,
            body,
            relative_raw_file,
            status="success",
            row_count=row_count,
        )
        return manifest

    # -- preflight y persistencia -------------------------------------------

    @staticmethod
    def _preflight(raw_path: Path, manifest_path: Path) -> None:
        if raw_path.exists():
            raise FileExistsError(f"el destino raw ya existe: {raw_path}")
        if manifest_path.exists():
            raise FileExistsError(f"el destino manifest ya existe: {manifest_path}")

    def _fail(self, manifest_path: Path, manifest: dict, warnings: list, notes: str) -> dict:
        manifest["status"] = "failed"
        manifest["raw_file"] = None
        manifest["content_hash"] = None
        manifest["row_count"] = None
        manifest["warnings"] = list(warnings)
        manifest["notes"] = notes
        self._write_manifest(manifest_path, manifest)
        return manifest

    def _persist_raw_and_hash(self, raw_path: Path, body: bytes) -> str:
        """Escribe los bytes exactos de forma exclusiva y luego calcula el hash del archivo en disco.

        Los bytes en disco se verifican contra el cuerpo descargado: un desajuste
        elimina el archivo raw y lanza ``OSError`` para que ningún manifest pueda
        reclamar bytes no verificados.
        """
        self._write_raw(raw_path, body)
        try:
            on_disk = raw_path.read_bytes()
        except OSError:
            raw_path.unlink(missing_ok=True)  # el archivo fue creado por esta ejecución
            raise
        if on_disk != body:
            raw_path.unlink(missing_ok=True)  # el archivo fue creado por esta ejecución
            raise OSError(
                f"falló la verificación del archivo raw: los bytes en disco en {raw_path} "
                "difieren del cuerpo descargado; no se escribió ningún manifest"
            )
        return hashlib.sha256(on_disk).hexdigest()

    def _persist_snapshot(
        self,
        manifest_path: Path,
        manifest: dict,
        raw_path: Path,
        body: bytes,
        relative_raw_file: str,
        *,
        status: str,
        row_count: int | None,
    ) -> None:
        """Primero persiste raw + hash verificado y luego escribe el manifest.

        El manifest se escribe solo después de que el archivo raw está en disco
        y el hash se ha verificado contra él, de modo que nunca reclama un
        archivo raw inexistente ni bytes que no puede verificar.
        """
        content_hash = self._persist_raw_and_hash(raw_path, body)
        manifest["status"] = status
        manifest["row_count"] = row_count
        manifest["content_hash"] = content_hash
        manifest["raw_file"] = relative_raw_file
        try:
            self._write_manifest(manifest_path, manifest)
        except BaseException:
            raw_path.unlink(missing_ok=True)  # el archivo raw fue creado por esta ejecución
            raise

    @staticmethod
    def _write_raw(raw_path: Path, body: bytes) -> None:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(raw_path, "xb")  # creación exclusiva: nunca sobrescribe
        try:
            with handle:
                handle.write(body)
        except BaseException:
            raw_path.unlink(missing_ok=True)  # el archivo fue creado por esta ejecución
            raise

    @staticmethod
    def _write_manifest(manifest_path: Path, manifest: dict) -> None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(manifest_path, "x", encoding="utf-8")  # creación exclusiva: nunca sobrescribe
        try:
            with handle:
                json.dump(manifest, handle, ensure_ascii=False, indent=2)
        except BaseException:
            manifest_path.unlink(missing_ok=True)  # el archivo fue creado por esta ejecución
            raise

    # -- construcción del manifest -------------------------------------------

    def _base_manifest(self, dataset_id: str, spec: dict, source_url: str, iso_utc: str, stamp: str) -> dict:
        return {
            "snapshot_id": f"{dataset_id}@{stamp}",
            "source_id": spec["source_id"],
            "dataset_id": dataset_id,
            "collection_timestamp_utc": iso_utc,
            "source_published_at": None,
            "source_url": source_url,
            "resource_id": None,
            "resource_name": None,
            "resource_url": None,
            "resource_format": None,
            "license_declared": spec["license_declared"],
            "license_published": None,
            "license_id": None,
            "license_url": None,
            "isopen": None,
            "restrictions": None,
            "attribution": spec["attribution"],
            "content_hash": None,
            "raw_file": None,
            "row_count": None,
            "status": "success",
            "schema_version": spec["schema_version"],
            "retrieval_method": RETRIEVAL_METHOD,
            "warnings": [],
            "notes": "",
            "resource": None,
            "source_metadata": None,
        }

    def _attach_source_metadata(self, manifest: dict, result: dict) -> None:
        manifest["source_metadata"] = deepcopy(result)
        published = result.get("metadata_modified")
        if isinstance(published, str) and published.strip():
            manifest["source_published_at"] = published
        manifest["license_published"] = result.get("license_title")
        manifest["license_id"] = result.get("license_id")
        manifest["license_url"] = result.get("license_url")
        manifest["isopen"] = result.get("isopen")
        attribution = self._derive_attribution(result)
        if attribution:
            manifest["attribution"] = attribution

    @staticmethod
    def _derive_attribution(result: dict) -> str | None:
        organization = result.get("organization")
        if isinstance(organization, dict):
            for key in ("title", "name"):
                value = organization.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        author = result.get("author")
        if isinstance(author, str) and author.strip():
            return author.strip()
        return None

    def _attach_resource(self, manifest: dict, resource: dict) -> None:
        manifest["resource"] = deepcopy(resource)
        manifest["resource_id"] = resource.get("id")
        manifest["resource_name"] = resource.get("name")
        manifest["resource_url"] = resource.get("url")
        manifest["resource_format"] = resource.get("format")

    # -- compuertas de adquisición --------------------------------------------

    def _fetch_package(self, source_url: str, manifest: dict, manifest_path: Path) -> dict | None:
        """Obtiene y valida package_show; devuelve el dict result o None (fallido)."""
        try:
            response = self.transport.get(source_url)
        except OSError as exc:
            self._fail(
                manifest_path,
                manifest,
                [f"error de transporte en package_show: {exc}"],
                f"No se pudo obtener los metadatos CKAN del paquete desde {source_url}.",
            )
            return None
        status = getattr(response, "status_code", None)
        if status is None or not (200 <= status < 300):
            self._fail(
                manifest_path,
                manifest,
                [f"package_show devolvió HTTP status {status!r}"],
                f"CKAN package_show devolvió HTTP {status} para {source_url}.",
            )
            return None
        content = getattr(response, "content", None)
        if not isinstance(content, (bytes, bytearray, memoryview)) or len(content) == 0:
            self._fail(
                manifest_path,
                manifest,
                ["el cuerpo de la respuesta package_show falta, está vacío o no es bytes"],
                f"CKAN package_show devolvió un cuerpo inválido para {source_url}.",
            )
            return None
        try:
            payload = json.loads(bytes(content))
        except (ValueError, TypeError) as exc:
            self._fail(
                manifest_path,
                manifest,
                [f"la respuesta package_show no es JSON válido: {exc}"],
                f"No se pudo analizar la respuesta package_show para {source_url}.",
            )
            return None
        if not isinstance(payload, dict):
            self._fail(
                manifest_path,
                manifest,
                ["la respuesta package_show no es un objeto JSON"],
                f"La forma de la respuesta package_show es inválida para {source_url}.",
            )
            return None
        if payload.get("success") is not True:
            self._fail(
                manifest_path,
                manifest,
                ["package_show devolvió success=false"],
                f"CKAN package_show falló para {manifest['dataset_id']}.",
            )
            return None
        result = payload.get("result")
        if not isinstance(result, dict):
            self._fail(
                manifest_path,
                manifest,
                ["el result de package_show falta o no es un objeto"],
                f"CKAN package_show no devolvió ningún objeto result para {manifest['dataset_id']}.",
            )
            return None
        return result

    def _check_license(self, manifest: dict, spec: dict, result: dict, manifest_path: Path) -> bool:
        """Compuerta de licencia: se ejecuta antes de cualquier descarga del resource.

        La compatibilidad se decide por el license id publicado (``cc-nc``) y
        la URL canónica oficial de la licencia CC BY-NC 2.0. El título debe ser
        no vacío pero es orientativo: el título canónico exacto es limpio,
        cualquier otro título (p. ej. el título genérico CKAN en vivo) añade una
        advertencia.
        """
        published_title = result.get("license_title")
        if not isinstance(published_title, str) or not published_title.strip():
            self._fail(
                manifest_path,
                manifest,
                ["el título de licencia del dataset está ausente"],
                f"Compuerta de licencia: {manifest['dataset_id']} no publica título de licencia; "
                f"se esperaba {spec['license_declared']}.",
            )
            return False

        published_id = result.get("license_id")
        if not isinstance(published_id, str) or published_id.strip().lower() != _APPROVED_LICENSE_ID:
            self._fail(
                manifest_path,
                manifest,
                [f"el license id del dataset {published_id!r} es incompatible"],
                f"Compuerta de licencia: se esperaba el license id {_APPROVED_LICENSE_ID!r} pero se encontró "
                f"{published_id!r}; se rechaza la descarga del resource.",
            )
            return False

        published_url = result.get("license_url")
        if not isinstance(published_url, str) or not self._is_official_cc_by_nc_url(published_url):
            if not isinstance(published_url, str) or not published_url.strip():
                self._fail(
                    manifest_path,
                    manifest,
                    ["la URL de licencia del dataset está ausente"],
                    f"Compuerta de licencia: {manifest['dataset_id']} no publica URL de licencia; "
                    f"se esperaba la URL oficial CC BY-NC 2.0 ({_LICENSE_URL_CANONICAL}).",
                )
            else:
                self._fail(
                    manifest_path,
                    manifest,
                    [f"la URL de licencia del dataset {published_url.strip()!r} no es la oficial CC BY-NC 2.0"],
                    f"Compuerta de licencia: {published_url.strip()!r} no es la URL oficial "
                    f"de la licencia CC BY-NC 2.0; se rechaza la descarga del resource.",
                )
            return False

        # Huella compatible: se registra la restricción explícita NonCommercial.
        manifest["restrictions"] = ["NonCommercial"]
        if published_title.strip() != spec["license_declared"]:
            manifest["warnings"].append(
                f"el título de licencia CKAN es genérico ({published_title.strip()!r}); "
                "la compatibilidad se decide por el license id y la URL de licencia canónica"
            )
        return True

    @staticmethod
    def _is_official_cc_by_nc_url(published: str) -> bool:
        """Verificación canónica contra la URL oficial de Creative Commons BY-NC 2.0.

        Acepta solo http/https en el host ``creativecommons.org`` con la ruta
        ``/licenses/by-nc/2.0`` (una barra final opcional); el esquema, las
        mayúsculas del host y HTTP-vs-HTTPS son equivalentes. Los puertos,
        userinfo, cadenas de consulta y fragmentos se rechazan por ambiguos.
        """
        candidate = published.strip()
        if not candidate:
            return False
        try:
            parts = urlsplit(candidate)
        except ValueError:
            return False
        if parts.scheme.lower() not in ("http", "https"):
            return False
        if parts.netloc.lower() != _APPROVED_LICENSE_HOST:
            return False
        if parts.query or parts.fragment:
            return False
        return parts.path in (_APPROVED_LICENSE_PATH, f"{_APPROVED_LICENSE_PATH}/")

    def _select_resource(self, manifest: dict, spec: dict, result: dict, manifest_path: Path) -> dict | None:
        """Selecciona el CSV no geométrico aprobado más nuevo, de forma determinista.

        Los resources elegibles tienen formato CSV, un ``id``/``name`` válidos y
        una URL http(s) absoluta, y no identifican datos geometry/geoespaciales.
        Entre ellos se elige el más nuevo con la clave de recencia determinista
        (``_recency_key``); la selección nunca es posicional.
        """
        resources = result.get("resources")
        if not isinstance(resources, list) or not resources:
            self._fail(
                manifest_path,
                manifest,
                ["el dataset no publica resources"],
                f"No hay resources publicados para {manifest['dataset_id']}.",
            )
            return None
        allowed_formats = {fmt.strip().upper() for fmt in spec["allowed_formats"]}
        candidates = [resource for resource in resources if self._is_acceptable_resource(resource, allowed_formats)]
        if not candidates:
            self._fail(
                manifest_path,
                manifest,
                ["no se encontró ningún resource compatible"],
                f"No hay ningún resource con un formato soportado ({', '.join(spec['allowed_formats'])}) "
                f"no geométrico con una URL http(s) absoluta válida para "
                f"{manifest['dataset_id']}.",
            )
            return None
        return max(candidates, key=self._recency_key)

    @staticmethod
    def _is_acceptable_resource(resource: object, allowed_formats: set[str]) -> bool:
        """Elegibilidad solo CSV: formato permitido, id/name válidos, URL http(s) absoluta
        y sin identidad geometry/geoespacial."""
        if not isinstance(resource, dict) or not resource:
            return False
        resource_format = resource.get("format")
        if not isinstance(resource_format, str) or not resource_format.strip():
            return False
        if resource_format.strip().upper() not in allowed_formats:
            return False
        for key in ("id", "name"):
            value = resource.get(key)
            if not isinstance(value, str) or not value.strip():
                return False
        url = resource.get("url")
        if not isinstance(url, str) or not url.strip():
            return False
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return False
        if CkanSnapshotCollector._is_geometric(resource):
            return False
        return True

    @staticmethod
    def _is_geometric(resource: dict) -> bool:
        """True cuando id/name/description/url identifican datos de geometría o geoespaciales.

        Las subcadenas marcadoras se comparan sin distinguir mayúsculas en el
        id, name, description y url del resource: geometry/geometría,
        geospatial/geoespacial, georreferenciadas/georeferenced, recorrido
        (geometría de rutas), shape(s) y geo.
        """
        text = " ".join(str(resource.get(key) or "").lower() for key in ("id", "name", "description", "url"))
        return any(marker in text for marker in _GEOMETRY_MARKERS)

    @staticmethod
    def _month_token(token: str) -> int | None:
        """Resuelve un token de mes (nombre en español/inglés o número de 1-2 dígitos)."""
        normalized = token.strip().lower()
        if normalized in _MONTH_NAMES:
            return _MONTH_NAMES[normalized]
        if normalized.isdigit() and 1 <= int(normalized) <= 12:
            return int(normalized)
        return None

    @classmethod
    def _embedded_date(cls, resource: dict) -> tuple[int, int | None] | None:
        """Extrae la fecha de corte de datos incrustada en el name/description.

        Coincide con tokens al estilo ``2025Abril``/``2022Septiembre`` y frases
        como ``septiembre del 2022``/``abril de 2025``; un año suelto se
        resuelve a ``(year, None)``. Devuelve None cuando no se encuentra
        ninguna fecha.
        """
        name = resource.get("name")
        description = resource.get("description")
        text = " ".join(str(value) for value in (name, description) if isinstance(value, str) and value.strip()).lower()
        if not text:
            return None
        year_first = _YEAR_FIRST_DATE.search(text)
        month_first = _MONTH_FIRST_DATE.search(text)
        if year_first is None and month_first is None:
            return None
        if month_first is None or (year_first is not None and year_first.start() <= month_first.start()):
            return int(year_first.group(1)), cls._month_token(year_first.group(2))
        return int(month_first.group(2)), cls._month_token(month_first.group(1))

    @classmethod
    def _embedded_date_ordinal(cls, resource: dict) -> int:
        """Ordinal del día de la fecha de corte incrustada; 0 cuando está ausente."""
        parts = cls._embedded_date(resource)
        if parts is None:
            return 0
        year, month = parts
        if month is None:
            return datetime(year, 1, 1).toordinal()
        return datetime(year, month, 1).toordinal()

    @staticmethod
    def _iso_date_ordinal(value: object) -> int:
        """Ordinal del día de una fecha de metadatos CKAN ISO-8601; 0 cuando no se puede analizar."""
        if not isinstance(value, str) or not value.strip():
            return 0
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return 0
        return parsed.toordinal()

    @classmethod
    def _recency_key(cls, resource: dict) -> tuple:
        """Clave de comparación determinista más-nuevo-primero para los resources elegibles.

        Primaria: la señal más reciente entre la fecha de corte incrustada y las
        fechas de metadatos del resource (``metadata_modified``, ``last_modified``,
        ``created``), normalizadas a ordinales de día. Los empates recurren a cada
        señal en orden y luego al id estable del resource. ``max`` sobre esta
        clave selecciona el resource más nuevo.
        """
        embedded = cls._embedded_date_ordinal(resource)
        metadata = cls._iso_date_ordinal(resource.get("metadata_modified"))
        last = cls._iso_date_ordinal(resource.get("last_modified"))
        created = cls._iso_date_ordinal(resource.get("created"))
        return (
            max(embedded, metadata, last, created),
            embedded,
            metadata,
            last,
            created,
            resource["id"],
        )

    def _fetch_resource(self, manifest: dict, resource_url: str, manifest_path: Path) -> object | None:
        """Descarga el resource seleccionado; devuelve la respuesta o None (fallido)."""
        try:
            response = self.transport.get(resource_url)
        except OSError as exc:
            self._fail(
                manifest_path,
                manifest,
                [f"error de transporte en la descarga del resource: {exc}"],
                f"No se pudo descargar el resource desde {resource_url}.",
            )
            return None
        status = getattr(response, "status_code", None)
        if status is None or not (200 <= status < 300):
            self._fail(
                manifest_path,
                manifest,
                [f"la descarga del resource devolvió HTTP status {status!r}"],
                f"La descarga del resource devolvió HTTP {status} para {resource_url}.",
            )
            return None
        body = getattr(response, "content", None)
        if not isinstance(body, (bytes, bytearray, memoryview)) or len(body) == 0:
            self._fail(
                manifest_path,
                manifest,
                ["el cuerpo del resource falta, está vacío o no es bytes"],
                f"El cuerpo del resource es inválido para {resource_url}.",
            )
            return None
        return response

    @staticmethod
    def _declared_content_length(headers: object) -> int | None:
        headers = headers or {}
        raw = headers.get("Content-Length")
        if raw is None:
            raw = headers.get("content-length")
        if raw is None:
            return None
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _validate_body(manifest: dict, resource_format: object, body: bytes) -> tuple:
        """Validación mínima del cuerpo; devuelve (row_count, invalid_reason_o_None)."""
        fmt = (resource_format or "").strip().upper()
        if fmt == "CSV":
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError as exc:
                return None, f"el cuerpo CSV no es UTF-8 válido: {exc}"
            try:
                rows = list(csv.reader(io.StringIO(text)))
            except csv.Error as exc:
                return None, f"el cuerpo CSV no pudo analizarse: {exc}"
            if not rows:
                manifest["warnings"].append("el cuerpo CSV no contiene filas; row_count desconocido")
                return None, None
            return max(len(rows) - 1, 0), None
        if fmt == "JSON":
            try:
                payload = json.loads(body)
            except (ValueError, TypeError) as exc:
                return None, f"el cuerpo JSON no pudo analizarse: {exc}"
            if isinstance(payload, list):
                return len(payload), None
            manifest["warnings"].append("row_count desconocido: el payload JSON no es una lista de nivel superior")
            return None, None
        # ZIP/XLSX/ODS y otros formatos declarados: bytes no vacíos opacos.
        return None, None


def supersede_orphan_manifest(
    manifest_path: str | Path,
    raw_dir: str | Path,
    sidecar_path: str | Path | None = None,
) -> dict:
    """Escribe un sidecar de reparación exclusivo para un manifest fallido cuyo raw falta.

    Lee ``manifest_path`` sin reescribirlo jamás. El archivo raw referenciado
    (``manifest["raw_file"]``) debe ser una ruta relativa no vacía que permanezca
    dentro de ``raw_dir`` (se rechazan las rutas absolutas y el traversal ``..``)
    y no debe existir en disco — de lo contrario el manifest no es huérfano y
    este helper falla cerrado. El sidecar se crea con semántica exclusiva (nunca
    sobrescribe) junto al manifest, por defecto el nombre del manifest con un
    sufijo ``.manifest.correction.json``. Registra ``status: "superseded"``,
    ``raw_verifiable: false``, ``raw_file``/``content_hash`` de nivel superior
    null, y la ruta/hash raw originales solo bajo ``unverified_original_claims``,
    declarando explícitamente que no hay ningún raw disponible y que el hash
    original no está confirmado. No ocurre ningún acceso a red y no se inventa
    ningún dato.
    """
    manifest_path = Path(manifest_path)
    raw_dir = Path(raw_dir)

    with open(manifest_path, encoding="utf-8") as handle:
        original = json.load(handle)

    if original.get("status") != "failed":
        raise ValueError(f"el manifest {manifest_path} no está fallido; se rechaza supersederlo")

    raw_file = original.get("raw_file")
    if not isinstance(raw_file, str) or not raw_file.strip():
        raise ValueError(f"el manifest {manifest_path} no reclama ningún raw_file; no hay nada que superseder")
    resolved_raw = (raw_dir / raw_file).resolve()
    if not resolved_raw.is_relative_to(raw_dir.resolve()):
        raise ValueError(f"raw_file {raw_file!r} escapa de raw_dir {raw_dir}; se rechaza la supersedencia")
    if resolved_raw.exists():
        raise FileExistsError(f"el archivo raw referenciado existe en {resolved_raw}; el manifest no es huérfano")

    if sidecar_path is None:
        name = manifest_path.name
        if name.endswith(".manifest.json"):
            name = name[: -len(".manifest.json")] + ".manifest.correction.json"
        else:
            name = name + ".manifest.correction.json"
        sidecar_path = manifest_path.with_name(name)
    sidecar_path = Path(sidecar_path)

    sidecar = {
        "snapshot_id": original.get("snapshot_id"),
        "dataset_id": original.get("dataset_id"),
        "source_id": original.get("source_id"),
        "collection_timestamp_utc": original.get("collection_timestamp_utc"),
        "supersedes_manifest": manifest_path.name,
        "status": "superseded",
        "raw_verifiable": False,
        "raw_file": None,
        "content_hash": None,
        "row_count": None,
        "unverified_original_claims": {
            "raw_file": original.get("raw_file"),
            "content_hash": original.get("content_hash"),
        },
        "note": (
            "No hay ningún archivo raw disponible para este manifest; el hash "
            "de contenido reclamado originalmente no está confirmado."
        ),
        "superseded_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_version": 1,
    }
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(sidecar_path, "x", encoding="utf-8")  # exclusivo: nunca sobrescribe
    try:
        with handle:
            json.dump(sidecar, handle, ensure_ascii=False, indent=2)
    except BaseException:
        sidecar_path.unlink(missing_ok=True)  # el archivo fue creado por esta ejecución
        raise
    return sidecar


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI: captura rutas, paradas o ambos datasets aprobados."""
    parser = argparse.ArgumentParser(
        prog="python -m mobility_reliability.ingestion.ckan_snapshot",
        description=(
            "Captura un snapshot actual de los datasets aprobados de Cuenca en Datos "
            "(CKAN package_show + el resource CSV no geométrico aprobado más nuevo). "
            "Sin recopilación histórica masiva."
        ),
    )
    parser.add_argument(
        "--dataset",
        choices=("routes", "stops", "all"),
        required=True,
        help="routes, stops o all (solo los dos datasets aprobados)",
    )
    parser.add_argument(
        "--raw-dir",
        default="data/raw",
        help="directorio de captura raw (por defecto: data/raw)",
    )
    parser.add_argument(
        "--manifest-dir",
        default="data/manifests",
        help="directorio de manifests (por defecto: data/manifests)",
    )
    args = parser.parse_args(argv)

    dataset_ids = {
        "routes": (ROUTES_DATASET_ID,),
        "stops": (STOPS_DATASET_ID,),
        "all": tuple(CKAN_PACKAGE_SHOW_URLS),
    }[args.dataset]

    collector = CkanSnapshotCollector(args.raw_dir, args.manifest_dir)
    any_failed = False
    for dataset_id in dataset_ids:
        manifest = collector.collect(dataset_id)
        status = manifest["status"]
        raw_file = manifest.get("raw_file") or "(sin archivo raw)"
        print(f"{dataset_id}: {status} raw={raw_file} sha256={manifest.get('content_hash')}")
        for warning in manifest.get("warnings", []):
            print(f"  advertencia: {warning}")
        if manifest.get("notes"):
            print(f"  nota: {manifest['notes']}")
        if status != "success":
            any_failed = True
    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
