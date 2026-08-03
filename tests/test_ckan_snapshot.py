"""Pruebas de contrato del recopilador de snapshots CKAN (Cuenca en Datos).

Estas pruebas definen y hacen cumplir la API pública prevista de
``mobility_reliability.ingestion.ckan_snapshot``: captura, selección,
integridad de la persistencia y reparación offline de manifests huérfanos.
Todos los fixtures son sintéticos y en memoria; no ocurre ningún acceso a red
ni captura real.

API pública bajo prueba
-----------------------
- ``mobility_reliability.ingestion.ckan_snapshot.CkanSnapshotCollector``
- ``mobility_reliability.ingestion.ckan_snapshot.DATASET_SPECS``
- ``mobility_reliability.ingestion.ckan_snapshot.CKAN_PACKAGE_SHOW_URLS``
- ``mobility_reliability.ingestion.ckan_snapshot.supersede_orphan_manifest``

``DATASET_SPECS`` mapea los dos dataset ids CKAN aprobados a sus specs; cada
spec lleva al menos ``source_id``, ``license_declared`` (``CC BY-NC 2.0``),
``allowed_formats`` y ``schema_version``. ``CKAN_PACKAGE_SHOW_URLS`` mapea los
mismos dataset ids a las dos URLs package_show aprobadas (ninguna otra URL).

Contrato del constructor
------------------------
``CkanSnapshotCollector(raw_dir, manifest_dir, *, transport, clock)``

- ``raw_dir`` / ``manifest_dir``: rutas de escritura para las capturas raw y
  los manifests (``pathlib.Path`` o ``str``).
- ``transport``: cliente HTTP con tipado duck que expone ``get(url, **kwargs)``
  y devuelve una respuesta con ``status_code``, ``headers`` y ``content``.
  Los fallos a nivel de transporte lanzan ``OSError``; el recopilador los
  captura y registra un manifest ``failed`` (ver Estados del manifest abajo).
- ``clock``: objeto que expone ``now()`` y devuelve un ``datetime`` UTC con
  zona horaria; el recopilador lo usa como marca de tiempo de recopilación.

Contrato de ``collect(dataset_id)``
-----------------------------------
- Acepta exactamente los dos dataset ids aprobados
  (``rutas-de-transporte-publico`` y ``paradas-de-transporte-publico``).
  Cualquier otro id — incluido el id de geometría de rutas
  ``recorrido-de-las-rutas-de-transporte-publico`` — lanza ``ValueError``
  antes de cualquier acceso a red y no escribe ningún artefacto.
- En caso de éxito devuelve un dict de manifest serializable a JSON y escribe
  exactamente dos archivos:
  - captura raw: ``raw_dir/<dataset_id>/<utc-stamp>.json``
  - manifest:    ``manifest_dir/<dataset_id>/<utc-stamp>.manifest.json``
  donde ``<utc-stamp>`` es la hora de recopilación UTC en una forma segura para
  el sistema de archivos (``2026-01-02T03-04-05Z`` para el reloj de prueba
  fijo).
- ``manifest["raw_file"]`` es la ruta raw relativa a ``raw_dir``.
- Los destinos existentes se detectan antes de cualquier acceso a red y lanzan
  ``FileExistsError``; en ese caso nunca se escribe ni sobrescribe nada
  (tampoco un manifest nuevo).

Estados del manifest
--------------------
- ``success``: package_show verificado, licencia verificada, un resource
  compatible descargado con un Content-Length que coincide con el cuerpo
  recibido. Los bytes raw exactos se conservan bajo la ruta raw determinista
  y ``content_hash`` es su SHA-256. ``warnings`` y ``notes`` están vacíos en
  una captura limpia (un título de licencia CKAN genérico añade una
  advertencia).
- ``partial``: la longitud del cuerpo del resource no coincide con el
  ``Content-Length`` declarado (en cualquier dirección). Los bytes *recibidos*
  se conservan exactamente bajo la ruta raw determinista y se les calcula el
  hash; el status es ``"partial"`` — nunca ``"success"``.
- ``failed``: cualquiera de los siguientes — package_show ``success: false``,
  respuesta de paquete malformada (JSON no analizable, falta ``success`` o
  falta ``result``), resources ausentes/null/vacíos, fallos de la compuerta de
  licencia (verificados **antes** de la descarga del resource: título
  ausente/vacío, URL de licencia faltante, una URL de Creative Commons distinta
  de la URL oficial CC BY-NC 2.0, o un license id distinto de ``cc-nc``),
  formato de resource no soportado, error HTTP del paquete, ``OSError`` de
  transporte (etapa de paquete o resource), error HTTP del resource o cuerpo
  de resource inválido. Se escribe un manifest ``failed`` bajo la ruta
  determinista del manifest con ``status == "failed"``, el ``dataset_id`` y
  ``source_url`` exactos, y ``warnings`` y ``notes`` no vacíos. **Los fallos
  previos a la descarga nunca reclaman un archivo raw**: ``raw_file``,
  ``content_hash`` y ``row_count`` permanecen null. Cuando el cuerpo del
  resource se descarga pero falla la decodificación/análisis del CSV (p. ej.
  UTF-8 inválido), los bytes exactos **sí** se conservan bajo la ruta raw
  determinista y se les calcula el hash desde el archivo en disco, y el
  manifest fallido referencia ese archivo raw con ``row_count`` null.

Política de selección del resource
----------------------------------
Entre los resources con un formato permitido (solo CSV), ``id``/``name``
válidos y una ``url`` http(s) absoluta que **no** identifiquen geometría,
datos geoespaciales, geometría de rutas, recorrido o shapes (comparados sin
distinguir mayúsculas en ``id``/``name``/``description``/``url``), el
recopilador selecciona deterministamente el **más nuevo**: la clave de
recencia es la señal más reciente entre la fecha de corte de datos incrustada
en el name/description (año de 4 dígitos con nombre de mes en español o
inglés, p. ej. ``2025Abril``/``2022Septiembre``, o un mes numérico) y las
fechas de metadatos del resource (``metadata_modified``, ``last_modified``,
``created``); los empates recurren a cada señal en orden y finalmente al ``id``
estable del resource. La selección nunca es posicional: un resource más nuevo
publicado más adelante en la lista gana sobre uno más antiguo publicado
primero. Los resources ZIP/ODS/GeoJSON y de geometría se excluyen antes de la
comparación de recencia.

Compuerta de licencia (antes de cualquier descarga del resource)
----------------------------------------------------------------
La huella de licencia publicada debe satisfacer todo lo siguiente: un
``license_title`` no vacío; ``license_id`` igual a ``cc-nc``; y la URL oficial
de la licencia CC BY-NC 2.0 (esquema ``http`` o ``https``,
``creativecommons.org/licenses/by-nc/2.0``, barra final opcional). El título
exacto ``"CC BY-NC 2.0"`` es limpio; el título genérico CKAN
``"Creative Commons Non-Commercial (Cualquiera)"`` se acepta con una
advertencia de que el título es genérico. Las URLs faltantes, otras URLs de
Creative Commons y los ids incompatibles fallan antes de la descarga del
resource. ``license_declared`` permanece ``"CC BY-NC 2.0"`` mientras que
``license_published``, ``license_id``, ``license_url`` e ``isopen`` conservan
los valores publicados, y ``restrictions`` lista la restricción explícita
NonCommercial.

Reglas de preflight (sin acceso a red, sin artefactos)
------------------------------------------------------
- Destino raw o manifest existente -> ``FileExistsError``.
- Dataset id desconocido (incluida la geometría de rutas) -> ``ValueError``.

Reparación offline de manifests huérfanos
-----------------------------------------
``supersede_orphan_manifest(manifest_path, raw_dir, sidecar_path=None)``
escribe un sidecar exclusivo ``.manifest.correction.json`` junto a un manifest
fallido cuyo archivo raw reclamado falta. Lee el manifest original pero nunca
lo reescribe; rechaza rutas raw absolutas o con traversal; falla cerrado
cuando el raw reclamado existe o el sidecar existe; y registra la ruta/hash
raw originales solo bajo ``unverified_original_claims`` con
``status: superseded``, ``raw_verifiable: false`` y ``raw_file``/
``content_hash`` de nivel superior null.

Esquema del manifest (se permite superset; estas claves son obligatorias)
------------------------------------------------------------------------
``status``                   -> ``"success"`` | ``"partial"`` | ``"failed"``
``source_id``                -> spec ``source_id``
``dataset_id``               -> el dataset id CKAN pasado a ``collect``
``source_url``               -> la URL package_show exacta utilizada
``license_declared``         -> ``"CC BY-NC 2.0"`` (explícito según el contrato de fuente)
``license_published``        -> el ``license_title`` publicado exactamente como se publicó
``license_id``               -> el license id CKAN publicado (``cc-nc``)
``license_url``              -> la URL de licencia publicada exacta (null cuando el
                                paquete no publica ninguna)
``isopen``                   -> el flag ``isopen`` publicado (``false`` para NC)
``restrictions``             -> lista de restricciones explícita (``["NonCommercial"]``)
``collection_timestamp_utc`` -> cadena ISO 8601 UTC del reloj inyectado
``schema_version``           -> spec ``schema_version``
``content_hash``             -> SHA-256 hexadecimal de los bytes raw exactos capturados
``raw_file``                 -> ruta relativa a la captura raw
``resource``                 -> dict de metadatos completo del resource seleccionado
``source_metadata``          -> metadatos del paquete, incluidos al menos ``id``,
                                ``name``, ``title`` y ``metadata_modified``
``source_published_at``      -> hora de publicación/actualización del paquete cuando el
                                paquete publica una (aquí: ``metadata_modified``)
``resource_id``              -> ``id`` del resource seleccionado
``resource_name``            -> ``name`` del resource seleccionado
``resource_url``             -> ``url`` del resource seleccionado
``resource_format``          -> ``format`` del resource seleccionado
``attribution``              -> cadena de atribución no vacía para la fuente
``row_count``                -> conteo de filas cuando la fuente publica uno
                                (ausente/desconocido -> null)
``retrieval_method``         -> ``"public documented CKAN API"``
``warnings``                 -> lista de cadenas de advertencia (vacía en un success limpio)
``notes``                    -> cadena de nota de forma libre (vacía en un success limpio)

Los valores pueden ser null/vacíos solo donde el paquete no los publica
(p. ej. ``row_count``); los campos generados por el recopilador siempre están
poblados.

Todos los fixtures son sintéticos y en memoria (solo ``tmp_path``); ningún
acceso a red real ni escrituras bajo ``data/``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mobility_reliability.ingestion.ckan_snapshot import (
    CKAN_PACKAGE_SHOW_URLS,
    DATASET_SPECS,
    CkanSnapshotCollector,
    supersede_orphan_manifest,
)

# ---------------------------------------------------------------------------
# Constantes de contrato
# ---------------------------------------------------------------------------

ROUTES_DATASET_ID = "rutas-de-transporte-publico"
STOPS_DATASET_ID = "paradas-de-transporte-publico"
EXCLUDED_DATASET_ID = "recorrido-de-las-rutas-de-transporte-publico"

ROUTES_PACKAGE_URL = (
    "https://cuencaendatos.cuenca.gob.ec/api/3/action/"
    "package_show?id=rutas-de-transporte-publico"
)
STOPS_PACKAGE_URL = (
    "https://cuencaendatos.cuenca.gob.ec/api/3/action/"
    "package_show?id=paradas-de-transporte-publico"
)

ROUTES_RESOURCE_URL = "https://fixtures.invalid/rutas.csv"
STOPS_RESOURCE_URL = "https://fixtures.invalid/paradas.csv"

ROUTES_RESOURCE_CONTENT = (
    b"LINEA,COMPANIA,SENTIDO,ORIGEN,DESTINO\n"
    b"1,COMPANIA A,I,CENTRO,EL VALLE\n"
    b"2,COMPANIA B,V,EL VALLE,CENTRO\n"
)
STOPS_RESOURCE_CONTENT = (
    b"CODIGO,NOMBRE,LATITUD,LONGITUD\n"
    b"1,PARADA CENTRO,-2.8974,-79.0045\n"
    b"2,PARADA EL VALLE,-2.8891,-78.9905\n"
)

LICENSE_DECLARED = "CC BY-NC 2.0"
LICENSE_ID_APPROVED = "cc-nc"
LICENSE_URL_APPROVED = "http://creativecommons.org/licenses/by-nc/2.0/"
LICENSE_URL_APPROVED_HTTPS = "https://creativecommons.org/licenses/by-nc/2.0/"
LICENSE_URL_CC_BY_4 = "http://creativecommons.org/licenses/by/4.0/"
LICENSE_URL_CC_BY_NC_SA = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
GENERIC_LICENSE_TITLE = "Creative Commons Non-Commercial (Cualquiera)"
RETRIEVAL_METHOD = "public documented CKAN API"
FIXED_NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
FIXED_UTC_STAMP = "2026-01-02T03-04-05Z"

REQUIRED_MANIFEST_FIELDS = frozenset(
    {
        "status",
        "source_id",
        "dataset_id",
        "source_url",
        "license_declared",
        "license_published",
        "license_id",
        "license_url",
        "isopen",
        "restrictions",
        "collection_timestamp_utc",
        "schema_version",
        "content_hash",
        "raw_file",
        "resource",
        "source_metadata",
        "source_published_at",
        "resource_id",
        "resource_name",
        "resource_url",
        "resource_format",
        "attribution",
        "row_count",
        "retrieval_method",
        "warnings",
        "notes",
    }
)

OMITTED = object()  # centinela: una clave ausente del result del paquete


# ---------------------------------------------------------------------------
# Fixtures sintéticos en memoria
# ---------------------------------------------------------------------------


class FakeResponse:
    """Respuesta mínima que expone la superficie contratada."""

    def __init__(
        self, status_code: int = 200, content: bytes | None = b"", headers: dict | None = None
    ):
        self.status_code = status_code
        self.content = content
        self.headers = dict(headers or {})


class FakeTransport:
    """Transport con tipado duck: mapea URLs a respuestas; las entradas de excepción se lanzan.

    Las entradas de excepción simulan fallos de transporte (``OSError``) que
    el recopilador debe capturar y registrar como manifest ``failed``.
    """

    def __init__(self, responses: dict[str, FakeResponse | Exception] | None = None):
        self.responses = dict(responses or {})
        self.calls: list[str] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(url)
        if url not in self.responses:
            raise AssertionError(f"se llamó al transport con una URL inesperada: {url}")
        entry = self.responses[url]
        if isinstance(entry, Exception):
            raise entry
        return entry


class FakeClock:
    """Devuelve un datetime UTC fijo con zona horaria."""

    def __init__(self, now: datetime):
        self._now = now

    def now(self, tz: timezone = timezone.utc) -> datetime:
        return self._now


def package_response(package_bytes: bytes, *, status_code: int = 200) -> FakeResponse:
    return FakeResponse(status_code, package_bytes, {"Content-Type": "application/json"})


def resource_response(
    content: bytes | None,
    *,
    status_code: int = 200,
    headers: dict | None = None,
) -> FakeResponse:
    return FakeResponse(
        status_code,
        content,
        headers if headers is not None else {"Content-Length": str(len(content or b""))},
    )


def build_transport(
    *,
    package_url: str,
    package_bytes: bytes = b"",
    package_status: int = 200,
    resource_url: str | None = None,
    resource_content: bytes | None = b"",
    resource_status: int = 200,
    resource_headers: dict | None = None,
    extra: dict[str, FakeResponse | Exception] | None = None,
) -> FakeTransport:
    responses: dict[str, FakeResponse | Exception] = {
        package_url: package_response(package_bytes, status_code=package_status)
    }
    if resource_url is not None:
        responses[resource_url] = resource_response(
            resource_content, status_code=resource_status, headers=resource_headers
        )
    if extra:
        responses.update(extra)
    return FakeTransport(responses)


def make_resource(
    *,
    resource_id: str,
    name: str,
    url: str,
    format_: str = "CSV",
    content: bytes = b"",
    **overrides,
) -> dict:
    resource = {
        "id": resource_id,
        "name": name,
        "format": format_,
        "url": url,
        "mimetype": "text/csv",
        "size": len(content),
        "created": "2025-06-01T12:00:00Z",
    }
    resource.update(overrides)
    return resource


def make_result(
    *,
    dataset_id: str,
    title: str,
    resources: list | None,
    license_title: str | None = LICENSE_DECLARED,
    license_id: str = LICENSE_ID_APPROVED,
    license_url: str | None = LICENSE_URL_APPROVED,
    isopen: bool = False,
    metadata_modified: str = "2025-06-01T12:00:00Z",
    **overrides,
) -> dict:
    result = {
        "id": dataset_id,
        "name": dataset_id,
        "title": title,
        "license_id": license_id,
        "license_url": license_url,
        "license_title": license_title,
        "isopen": isopen,
        "metadata_modified": metadata_modified,
        "resources": resources,
    }
    result.update(overrides)
    return result


def package_show_bytes(result: dict, *, success: bool = True) -> bytes:
    return json.dumps({"success": success, "result": result}, ensure_ascii=False).encode("utf-8")


def routes_world() -> tuple[dict, dict, FakeTransport]:
    """Paquete completo de rutas en el camino feliz: resource seleccionado, result del paquete, transport."""
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    return resource, result, transport


def expected_raw_path(raw_dir: Path, dataset_id: str) -> Path:
    return raw_dir / dataset_id / f"{FIXED_UTC_STAMP}.json"


def expected_manifest_path(manifest_dir: Path, dataset_id: str) -> Path:
    return manifest_dir / dataset_id / f"{FIXED_UTC_STAMP}.manifest.json"


def assert_no_captures(raw_dir: Path, manifest_dir: Path) -> None:
    """No puede existir ninguna captura raw ni ningún archivo manifest (fallos de preflight)."""
    assert list(raw_dir.rglob("*")) == []
    assert list(manifest_dir.rglob("*")) == []


def assert_failed_manifest(
    manifest: dict,
    raw_dir: Path,
    manifest_dir: Path,
    dataset_id: str,
    package_url: str,
    *,
    raw_bytes: bytes | None = None,
) -> dict:
    """Existe un manifest fallido bajo la ruta determinista.

    Con ``raw_bytes=None`` (fallo previo a la descarga) no puede existir
    ningún archivo raw y ``raw_file``/``content_hash``/``row_count`` deben
    permanecer null para que el manifest nunca apunte a un raw inexistente.
    Con ``raw_bytes`` dado (cuerpo descargado pero decodificación CSV
    fallida) los bytes exactos deben existir en disco, con hash, y con
    ``row_count`` null.
    """
    manifest_path = expected_manifest_path(manifest_dir, dataset_id)
    assert manifest_path.is_file()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert manifest["status"] == "failed"
    assert manifest["dataset_id"] == dataset_id
    assert manifest["source_url"] == package_url
    assert manifest["warnings"]
    assert manifest["notes"]
    assert manifest["row_count"] is None
    if raw_bytes is None:
        assert manifest["raw_file"] is None
        assert manifest["content_hash"] is None
        assert list(raw_dir.rglob("*")) == []  # sin captura raw en el fallo
    else:
        raw_path = expected_raw_path(raw_dir, dataset_id)
        assert raw_path.is_file()
        assert raw_path.read_bytes() == raw_bytes
        assert manifest["raw_file"] == f"{dataset_id}/{FIXED_UTC_STAMP}.json"
        assert manifest["content_hash"] == hashlib.sha256(raw_bytes).hexdigest()
    return manifest


def assert_partial_manifest(
    manifest: dict,
    raw_dir: Path,
    manifest_dir: Path,
    dataset_id: str,
    received_bytes: bytes,
) -> dict:
    """Existe un manifest parcial; los bytes recibidos se conservan exactamente."""
    raw_path = expected_raw_path(raw_dir, dataset_id)
    assert raw_path.is_file()
    assert raw_path.read_bytes() == received_bytes

    manifest_path = expected_manifest_path(manifest_dir, dataset_id)
    assert manifest_path.is_file()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert manifest["status"] == "partial"
    assert manifest["status"] != "success"  # nunca se trata como snapshot exitoso
    assert manifest["content_hash"] == hashlib.sha256(received_bytes).hexdigest()
    return manifest


@pytest.fixture
def collector_factory(tmp_path):
    def _make(*, transport, raw_dir=None, manifest_dir=None, clock=None):
        return CkanSnapshotCollector(
            raw_dir=raw_dir if raw_dir is not None else tmp_path / "raw",
            manifest_dir=manifest_dir if manifest_dir is not None else tmp_path / "manifests",
            transport=transport,
            clock=clock if clock is not None else FakeClock(FIXED_NOW),
        )

    return _make


# ---------------------------------------------------------------------------
# 1. Camino feliz: package_show + captura del resource para rutas
# ---------------------------------------------------------------------------


def test_captura_exitosa_de_package_show_y_resource_para_rutas(tmp_path, collector_factory):
    resource, result, transport = routes_world()
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert manifest["status"] == "success"
    assert manifest["dataset_id"] == ROUTES_DATASET_ID
    assert manifest["resource"] == resource
    assert transport.calls == [ROUTES_PACKAGE_URL, ROUTES_RESOURCE_URL]

    raw_path = expected_raw_path(tmp_path / "raw", ROUTES_DATASET_ID)
    assert raw_path.is_file()
    assert raw_path.read_bytes() == ROUTES_RESOURCE_CONTENT

    manifest_path = expected_manifest_path(tmp_path / "manifests", ROUTES_DATASET_ID)
    assert manifest_path.is_file()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest


# ---------------------------------------------------------------------------
# 2. Las paradas se capturan y se identifican por separado
# ---------------------------------------------------------------------------


def test_captura_exitosa_identifica_paradas_por_separado(tmp_path, collector_factory):
    resource = make_resource(
        resource_id="res-stops-1",
        name="paradas.csv",
        url=STOPS_RESOURCE_URL,
        content=STOPS_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=STOPS_DATASET_ID,
        title="Paradas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=STOPS_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=STOPS_RESOURCE_URL,
        resource_content=STOPS_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(STOPS_DATASET_ID)

    assert manifest["status"] == "success"
    assert manifest["dataset_id"] == STOPS_DATASET_ID
    assert manifest["dataset_id"] != ROUTES_DATASET_ID
    assert manifest["source_id"] == DATASET_SPECS[STOPS_DATASET_ID]["source_id"]
    assert manifest["source_id"] != DATASET_SPECS[ROUTES_DATASET_ID]["source_id"]
    assert manifest["source_url"] == STOPS_PACKAGE_URL
    assert transport.calls == [STOPS_PACKAGE_URL, STOPS_RESOURCE_URL]

    raw_path = expected_raw_path(tmp_path / "raw", STOPS_DATASET_ID)
    assert raw_path.is_file()
    assert raw_path.read_bytes() == STOPS_RESOURCE_CONTENT
    assert not (tmp_path / "raw" / ROUTES_DATASET_ID).exists()


# ---------------------------------------------------------------------------
# 3. URLs de source aprobadas exactas
# ---------------------------------------------------------------------------


def test_las_urls_de_source_son_las_dos_urls_package_show_aprobadas():
    assert CKAN_PACKAGE_SHOW_URLS == {
        ROUTES_DATASET_ID: ROUTES_PACKAGE_URL,
        STOPS_DATASET_ID: STOPS_PACKAGE_URL,
    }


# ---------------------------------------------------------------------------
# 4. package_show con success:false registra un manifest fallido
# ---------------------------------------------------------------------------


def test_package_show_con_success_false_registra_manifest_fallido(tmp_path, collector_factory):
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes({}, success=False),
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]


# ---------------------------------------------------------------------------
# 5. Respuesta de paquete malformada registra un manifest fallido
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "package_bytes",
    [b"<html><body>gateway error</body></html>", b"{}", b'{"success": true}'],
    ids=["json-invalido", "sin-success", "sin-result"],
)
def test_respuesta_de_paquete_malformada_registra_manifest_fallido(
    tmp_path, collector_factory, package_bytes
):
    transport = build_transport(package_url=ROUTES_PACKAGE_URL, package_bytes=package_bytes)
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]


# ---------------------------------------------------------------------------
# 6. Falta el resource: se registra un manifest fallido
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "resources", [OMITTED, [], None], ids=["omitido", "lista-vacia", "nulo"]
)
def test_falta_el_resource_y_registra_manifest_fallido(tmp_path, collector_factory, resources):
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[],
    )
    if resources is OMITTED:
        del result["resources"]
    else:
        result["resources"] = resources
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]  # nada descargado


# ---------------------------------------------------------------------------
# 7. Compuerta de licencia: huella aprobada (id cc-nc + URL oficial CC BY-NC 2.0)
# ---------------------------------------------------------------------------


def test_license_id_valido_y_url_oficial_cc_by_nc_2_0_con_esquema_http(tmp_path, collector_factory):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert manifest["status"] == "success"
    assert transport.calls == [ROUTES_PACKAGE_URL, ROUTES_RESOURCE_URL]


def test_license_id_valido_y_url_oficial_cc_by_nc_2_0_con_esquema_https(tmp_path, collector_factory):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
        license_url=LICENSE_URL_APPROVED_HTTPS,
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert manifest["status"] == "success"
    assert manifest["license_url"] == LICENSE_URL_APPROVED_HTTPS


@pytest.mark.parametrize(
    "license_url",
    [LICENSE_URL_APPROVED, "http://creativecommons.org/licenses/by-nc/2.0"],
    ids=["con-barra-final", "sin-barra-final"],
)
def test_license_id_valido_y_url_oficial_cc_by_nc_2_0_con_barra_final_opcional(
    tmp_path, collector_factory, license_url
):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
        license_url=license_url,
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert manifest["status"] == "success"
    # El manifest conserva la URL publicada exacta, con o sin barra final.
    assert manifest["license_url"] == license_url


def test_titulo_de_licencia_ckan_generico_aceptado_con_advertencia(tmp_path, collector_factory):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
        license_title=GENERIC_LICENSE_TITLE,
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert manifest["status"] == "success"
    # El título genérico publicado se conserva exactamente, nunca se reescribe.
    assert manifest["license_published"] == GENERIC_LICENSE_TITLE
    assert manifest["source_metadata"]["license_title"] == GENERIC_LICENSE_TITLE
    assert any("genérico" in warning.lower() for warning in manifest["warnings"])


def test_el_manifest_conserva_la_huella_de_licencia_y_la_restriccion_noncommercial(
    tmp_path, collector_factory
):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert manifest["status"] == "success"
    assert manifest["license_id"] == LICENSE_ID_APPROVED
    assert manifest["license_url"] == LICENSE_URL_APPROVED  # forma publicada exacta
    assert manifest["isopen"] is False
    assert manifest["restrictions"] == ["NonCommercial"]
    assert manifest["license_published"] == LICENSE_DECLARED


# ---------------------------------------------------------------------------
# 8. Compuerta de licencia: fail closed (sin descarga del resource)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("license_title", [None, ""])
def test_licencia_ausente_registra_manifest_fallido_sin_descargar_resource(
    tmp_path, collector_factory, license_title
):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
        license_title=license_title,
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]  # compuerta de licencia antes de descargar el resource


def test_clave_de_licencia_ausente_registra_manifest_fallido_sin_descargar_resource(
    tmp_path, collector_factory
):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
    )
    del result["license_title"]
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]  # compuerta de licencia antes de descargar el resource


@pytest.mark.parametrize("license_url", [None, "", OMITTED], ids=["nulo", "vacio", "omitido"])
def test_url_de_licencia_ausente_falla_antes_de_descargar_resource(
    tmp_path, collector_factory, license_url
):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    if license_url is OMITTED:
        result = make_result(
            dataset_id=ROUTES_DATASET_ID,
            title="Rutas de transporte público",
            resources=[resource],
        )
        del result["license_url"]
    else:
        result = make_result(
            dataset_id=ROUTES_DATASET_ID,
            title="Rutas de transporte público",
            resources=[resource],
            license_url=license_url,
        )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]  # el resource nunca se descargó


def test_url_de_licencia_incompatible_registra_manifest_fallido_sin_descargar_resource(
    tmp_path, collector_factory
):
    # La incompatibilidad la causa la URL publicada (CC BY 4.0), no un título
    # distinto del contrato: el título y el id siguen siendo compatibles.
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
        license_url=LICENSE_URL_CC_BY_4,
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]  # compuerta de licencia antes de descargar el resource


def test_otra_url_de_licencia_creative_commons_falla_antes_de_descargar_resource(
    tmp_path, collector_factory
):
    # Un título que afirma CC BY-NC 2.0 no puede anular una URL de licencia CC distinta.
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
        license_id="cc-by-nc-sa",
        license_url=LICENSE_URL_CC_BY_NC_SA,
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]  # el resource nunca se descargó


def test_license_id_incompatible_falla_antes_de_descargar_resource(tmp_path, collector_factory):
    # Un license id no-NC falla incluso cuando el título y la URL parecen compatibles.
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
        license_id="cc-by",
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]  # el resource nunca se descargó


# ---------------------------------------------------------------------------
# 10. Formato de resource no soportado registra un manifest fallido; regla de selección
# ---------------------------------------------------------------------------


def test_formato_de_resource_no_soportado_registra_manifest_fallido(tmp_path, collector_factory):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.geojson",
        url="https://fixtures.invalid/rutas.geojson",
        format_="GeoJSON",
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]  # nada descargado


def test_el_resource_seleccionado_es_el_csv_aprobado_mas_nuevo(tmp_path, collector_factory):
    # El resource GeoJSON se excluye por formato; el CSV es el único candidato
    # aprobado y por lo tanto el más nuevo seleccionado.
    geojson = make_resource(
        resource_id="res-geo",
        name="rutas.geojson",
        url="https://fixtures.invalid/rutas.geojson",
        format_="GeoJSON",
    )
    csv = make_resource(
        resource_id="res-csv",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[geojson, csv],
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert manifest["status"] == "success"
    assert manifest["resource"] == csv
    assert transport.calls == [ROUTES_PACKAGE_URL, ROUTES_RESOURCE_URL]


# ---------------------------------------------------------------------------
# 11. Error HTTP del paquete y error de red registran un manifest fallido
# ---------------------------------------------------------------------------


def test_error_http_del_paquete_registra_manifest_fallido(tmp_path, collector_factory):
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=b"server error",
        package_status=500,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]


def test_error_de_red_del_paquete_registra_manifest_fallido(tmp_path, collector_factory):
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes({}),
        extra={ROUTES_PACKAGE_URL: OSError("connection refused")},
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL]


# ---------------------------------------------------------------------------
# 12. Errores de red / HTTP / cuerpo inválido del resource registran un manifest fallido
# ---------------------------------------------------------------------------


def test_error_de_red_del_resource_registra_manifest_fallido(tmp_path, collector_factory):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
        extra={ROUTES_RESOURCE_URL: OSError("connection reset by peer")},
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL, ROUTES_RESOURCE_URL]


def test_error_http_del_resource_registra_manifest_fallido(tmp_path, collector_factory):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=b"resource error",
        resource_status=500,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL, ROUTES_RESOURCE_URL]


def test_cuerpo_invalido_del_resource_registra_manifest_fallido(tmp_path, collector_factory):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
        extra={ROUTES_RESOURCE_URL: FakeResponse(200, None)},
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    assert transport.calls == [ROUTES_PACKAGE_URL, ROUTES_RESOURCE_URL]


# ---------------------------------------------------------------------------
# 13. La descarga parcial nunca es success (desajuste de Content-Length)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("declared_length", [10_000, 4])
def test_la_descarga_parcial_nunca_es_success(tmp_path, collector_factory, declared_length):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
        resource_headers={"Content-Length": str(declared_length)},
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    # Los bytes recibidos se conservan exactamente, nunca se tratan como success.
    assert_partial_manifest(
        manifest,
        tmp_path / "raw",
        tmp_path / "manifests",
        ROUTES_DATASET_ID,
        ROUTES_RESOURCE_CONTENT,
    )
    assert transport.calls == [ROUTES_PACKAGE_URL, ROUTES_RESOURCE_URL]


# ---------------------------------------------------------------------------
# 14. Los bytes raw se conservan exactos; SHA-256 coincide con los bytes originales
# ---------------------------------------------------------------------------


def test_los_bytes_raw_se_conservan_exactos_y_sha256_coincide(tmp_path, collector_factory):
    _, _, transport = routes_world()
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    raw_path = expected_raw_path(tmp_path / "raw", ROUTES_DATASET_ID)
    assert raw_path.read_bytes() == ROUTES_RESOURCE_CONTENT
    assert manifest["content_hash"] == hashlib.sha256(ROUTES_RESOURCE_CONTENT).hexdigest()


# ---------------------------------------------------------------------------
# 15. Completitud del manifest: campos, metadatos, marca de tiempo UTC, ruta relativa
# ---------------------------------------------------------------------------


def test_el_manifest_contiene_todos_los_campos_y_metadatos_completos(
    tmp_path, collector_factory
):
    resource, result, transport = routes_world()
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert REQUIRED_MANIFEST_FIELDS.issubset(manifest)
    assert manifest["status"] == "success"
    assert manifest["dataset_id"] == ROUTES_DATASET_ID
    assert manifest["source_id"] == DATASET_SPECS[ROUTES_DATASET_ID]["source_id"]
    assert manifest["source_url"] == ROUTES_PACKAGE_URL
    assert manifest["license_declared"] == LICENSE_DECLARED
    assert manifest["schema_version"] == DATASET_SPECS[ROUTES_DATASET_ID]["schema_version"]
    assert manifest["content_hash"] == hashlib.sha256(ROUTES_RESOURCE_CONTENT).hexdigest()

    # Metadatos completos del resource seleccionado, exactamente como los publicó package_show.
    assert manifest["resource"] == result["resources"][0]

    # Metadatos de la fuente del result del paquete.
    for key in ("id", "name", "title", "metadata_modified"):
        assert manifest["source_metadata"][key] == result[key]

    # Marca de tiempo de recopilación UTC del reloj inyectado.
    parsed = datetime.fromisoformat(manifest["collection_timestamp_utc"])
    assert parsed == FIXED_NOW
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)

    # raw_file relativo: nombra la captura exacta y permanece dentro de raw_dir.
    raw_file = manifest["raw_file"]
    assert isinstance(raw_file, str)
    assert raw_file == f"{ROUTES_DATASET_ID}/{FIXED_UTC_STAMP}.json"
    assert not Path(raw_file).is_absolute()
    assert ".." not in Path(raw_file).parts
    assert (tmp_path / "raw" / raw_file).read_bytes() == ROUTES_RESOURCE_CONTENT

    # Metadatos de publicación, proyección del resource, atribución, método de
    # recuperación y campos de calidad. Los valores son null/vacíos solo donde el
    # paquete no los publica (el paquete CKAN no publica row_count).
    assert manifest["source_published_at"] == result["metadata_modified"]
    assert manifest["resource_id"] == resource["id"]
    assert manifest["resource_name"] == resource["name"]
    assert manifest["resource_url"] == resource["url"]
    assert manifest["resource_format"] == resource["format"]
    assert isinstance(manifest["attribution"], str) and manifest["attribution"]
    assert "row_count" in manifest
    assert manifest["retrieval_method"] == RETRIEVAL_METHOD
    assert manifest["warnings"] == []  # success limpio: sin advertencias
    assert manifest["notes"] == ""


# ---------------------------------------------------------------------------
# 16. Sin sobrescritura accidental de destinos raw o manifest existentes
# ---------------------------------------------------------------------------


def test_no_sobrescribe_cuando_el_destino_raw_ya_existe(tmp_path, collector_factory):
    raw_dir = tmp_path / "raw"
    raw_path = expected_raw_path(raw_dir, ROUTES_DATASET_ID)
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"pre-existing-raw")

    _, _, transport = routes_world()
    collector = collector_factory(transport=transport, raw_dir=raw_dir)

    with pytest.raises(FileExistsError):
        collector.collect(ROUTES_DATASET_ID)

    assert raw_path.read_bytes() == b"pre-existing-raw"  # nunca sobrescrito
    assert transport.calls == []  # la verificación del destino ocurre antes de cualquier acceso a red
    assert [p for p in raw_dir.rglob("*") if p.is_file()] == [raw_path]
    assert list((tmp_path / "manifests").rglob("*")) == []  # tampoco un manifest nuevo


def test_no_sobrescribe_cuando_el_destino_manifest_ya_existe(tmp_path, collector_factory):
    manifest_dir = tmp_path / "manifests"
    manifest_path = expected_manifest_path(manifest_dir, ROUTES_DATASET_ID)
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text('{"pre": "existing"}', encoding="utf-8")

    _, _, transport = routes_world()
    collector = collector_factory(transport=transport, manifest_dir=manifest_dir)

    with pytest.raises(FileExistsError):
        collector.collect(ROUTES_DATASET_ID)

    assert manifest_path.read_text(encoding="utf-8") == '{"pre": "existing"}'
    assert transport.calls == []
    assert not (tmp_path / "raw").exists()  # el lado raw nunca se toca


def test_recapturar_con_la_misma_marca_de_tiempo_falla_cerrado_en_lugar_de_sobrescribir(
    tmp_path, collector_factory
):
    _, _, transport = routes_world()
    collector = collector_factory(transport=transport)

    first = collector.collect(ROUTES_DATASET_ID)

    with pytest.raises(FileExistsError):
        collector.collect(ROUTES_DATASET_ID)

    assert transport.calls == [ROUTES_PACKAGE_URL, ROUTES_RESOURCE_URL]  # segunda llamada: sin red
    raw_path = expected_raw_path(tmp_path / "raw", ROUTES_DATASET_ID)
    assert raw_path.read_bytes() == ROUTES_RESOURCE_CONTENT
    manifest_path = expected_manifest_path(tmp_path / "manifests", ROUTES_DATASET_ID)
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == first


# ---------------------------------------------------------------------------
# 17. Los dataset ids y source ids de rutas y paradas permanecen distintos
# ---------------------------------------------------------------------------


def test_los_dataset_ids_y_source_ids_de_rutas_y_paradas_permanecen_distintos():
    assert set(DATASET_SPECS) == {ROUTES_DATASET_ID, STOPS_DATASET_ID}
    assert set(CKAN_PACKAGE_SHOW_URLS) == {ROUTES_DATASET_ID, STOPS_DATASET_ID}

    route_spec = DATASET_SPECS[ROUTES_DATASET_ID]
    stop_spec = DATASET_SPECS[STOPS_DATASET_ID]

    assert route_spec["source_id"] != stop_spec["source_id"]
    assert route_spec["license_declared"] == LICENSE_DECLARED
    assert stop_spec["license_declared"] == LICENSE_DECLARED
    assert "CSV" in route_spec["allowed_formats"]
    assert "CSV" in stop_spec["allowed_formats"]
    assert route_spec["schema_version"] >= 1
    assert stop_spec["schema_version"] >= 1


# ---------------------------------------------------------------------------
# 18. El dataset de geometría de rutas (recorrido) sigue excluido, sin llamadas al transport
# ---------------------------------------------------------------------------


def test_el_dataset_de_geometria_de_rutas_queda_excluido_y_nunca_activa_el_transport(
    tmp_path, collector_factory
):
    assert EXCLUDED_DATASET_ID not in DATASET_SPECS
    assert EXCLUDED_DATASET_ID not in CKAN_PACKAGE_SHOW_URLS

    transport = FakeTransport()
    collector = collector_factory(transport=transport)

    with pytest.raises(ValueError) as excinfo:
        collector.collect(EXCLUDED_DATASET_ID)

    assert EXCLUDED_DATASET_ID in str(excinfo.value)
    assert transport.calls == []  # falla antes del acceso a red
    assert_no_captures(tmp_path / "raw", tmp_path / "manifests")


# ---------------------------------------------------------------------------
# 19. Selección del resource: CSV no geométrico aprobado más nuevo
# ---------------------------------------------------------------------------


def test_se_selecciona_el_csv_mas_nuevo_sobre_el_snapshot_anterior(tmp_path, collector_factory):
    older = make_resource(
        resource_id="res-stops-2022",
        name="GADCuenca_ParadasTransporte_2022Septiembre.csv",
        url="https://fixtures.invalid/stops-2022.csv",
        content=STOPS_RESOURCE_CONTENT,
        description="Paradas de transporte público con corte a septiembre del 2022",
        created="2022-10-20T21:02:22.710187",
        last_modified="2023-01-23T15:11:15.934982",
        metadata_modified="2023-01-23T15:11:15.954774",
    )
    newer = make_resource(
        resource_id="res-stops-2025",
        name="GADCuenca_ParadasTransporte_2025Abril.csv",
        url="https://fixtures.invalid/stops-2025.csv",
        content=STOPS_RESOURCE_CONTENT,
        description="Detalle de paradas de transporte público con corte a abril del 2025",
        created="2025-05-15T20:53:40.540706",
        last_modified="2025-05-15T21:24:23.812354",
        metadata_modified="2025-05-15T21:24:23.831778",
    )
    result = make_result(
        dataset_id=STOPS_DATASET_ID,
        title="Paradas de transporte público",
        resources=[older, newer],  # el snapshot anterior va primero: la selección no es posicional
    )
    transport = build_transport(
        package_url=STOPS_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url="https://fixtures.invalid/stops-2025.csv",
        resource_content=STOPS_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(STOPS_DATASET_ID)

    assert manifest["status"] == "success"
    assert manifest["resource_id"] == "res-stops-2025"
    assert manifest["resource_name"] == "GADCuenca_ParadasTransporte_2025Abril.csv"
    assert transport.calls == [STOPS_PACKAGE_URL, "https://fixtures.invalid/stops-2025.csv"]


def test_paradas_selecciona_el_csv_de_abril_2025_sobre_el_de_septiembre_2022(tmp_path, collector_factory):
    sep2022 = make_resource(
        resource_id="ffa506af-01c4-4b5b-afe2-e2f63b862ca6",
        name="GADCuenca_ParadasTransporte_2022Septiembre.csv",
        url="https://fixtures.invalid/2022septiembre.csv",
        content=STOPS_RESOURCE_CONTENT,
        created="2022-10-20T21:02:22.710187",
        metadata_modified="2023-01-23T15:11:15.954774",
    )
    apr2025 = make_resource(
        resource_id="ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e",
        name="GADCuenca_ParadasTransporte_2025Abril.csv",
        url="https://fixtures.invalid/2025abril.csv",
        content=STOPS_RESOURCE_CONTENT,
        created="2025-05-15T20:53:40.540706",
        metadata_modified="2025-05-15T21:24:23.831778",
    )
    result = make_result(
        dataset_id=STOPS_DATASET_ID,
        title="Paradas de transporte público",
        resources=[sep2022, apr2025],  # septiembre 2022 va primero; la selección no debe ser posicional
    )
    transport = build_transport(
        package_url=STOPS_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url="https://fixtures.invalid/2025abril.csv",
        resource_content=STOPS_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(STOPS_DATASET_ID)

    assert manifest["status"] == "success"
    assert manifest["resource_id"] == "ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e"
    assert manifest["resource_id"] != "ffa506af-01c4-4b5b-afe2-e2f63b862ca6"
    assert manifest["resource_name"] == "GADCuenca_ParadasTransporte_2025Abril.csv"


def test_los_resources_zip_y_csv_de_geometria_se_excluyen_aun_siendo_mas_nuevos(
    tmp_path, collector_factory
):
    zip_resource = make_resource(
        resource_id="res-zip-geo",
        name="GADCuenca_ParadasTransporteGeo_2022Septiembre.zip",
        url="https://fixtures.invalid/geo.zip",
        format_="ZIP",
        content=b"PK\x03\x04not a real zip",
        description="Paradas georreferenciadas con corte a septiembre del 2022",
        created="2025-05-01T00:00:00Z",
        metadata_modified="2025-05-02T00:00:00Z",  # metadatos más nuevos de los tres
    )
    geometry_csv = make_resource(
        resource_id="res-geometry-csv",
        name="GADCuenca_Recorrido_2025Abril.csv",
        url="https://fixtures.invalid/recorrido.csv",
        content=STOPS_RESOURCE_CONTENT,
        description="Recorrido (geometría) de rutas con corte a abril del 2025",
        created="2025-06-01T00:00:00Z",
        metadata_modified="2025-06-02T00:00:00Z",  # aún más nuevos: la geometría debe perder igual
    )
    plain_csv = make_resource(
        resource_id="res-plain-csv",
        name="GADCuenca_ParadasTransporte_2025Abril.csv",
        url="https://fixtures.invalid/plain.csv",
        content=STOPS_RESOURCE_CONTENT,
        created="2025-05-15T20:53:40.540706",
        metadata_modified="2025-05-15T21:24:23.831778",
    )
    result = make_result(
        dataset_id=STOPS_DATASET_ID,
        title="Paradas de transporte público",
        resources=[zip_resource, geometry_csv, plain_csv],
    )
    transport = build_transport(
        package_url=STOPS_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url="https://fixtures.invalid/plain.csv",
        resource_content=STOPS_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(STOPS_DATASET_ID)

    assert manifest["status"] == "success"
    assert manifest["resource_id"] == "res-plain-csv"
    # Solo se solicita el CSV simple seleccionado; las URLs ZIP/geometry nunca.
    assert transport.calls == [STOPS_PACKAGE_URL, "https://fixtures.invalid/plain.csv"]


# ---------------------------------------------------------------------------
# 20. Manifests fallidos: raw/hash/row_count coherentes; los errores de decodificación conservan los bytes
# ---------------------------------------------------------------------------


def test_manifest_fallido_sin_raw_persistido_tiene_raw_hash_y_row_count_nulos(
    tmp_path, collector_factory
):
    resource = make_resource(
        resource_id="res-routes-1",
        name="rutas.csv",
        url=ROUTES_RESOURCE_URL,
        content=ROUTES_RESOURCE_CONTENT,
    )
    result = make_result(
        dataset_id=ROUTES_DATASET_ID,
        title="Rutas de transporte público",
        resources=[resource],
        license_url=LICENSE_URL_CC_BY_4,
    )
    transport = build_transport(
        package_url=ROUTES_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=ROUTES_RESOURCE_URL,
        resource_content=ROUTES_RESOURCE_CONTENT,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(ROUTES_DATASET_ID)

    assert_failed_manifest(
        manifest, tmp_path / "raw", tmp_path / "manifests", ROUTES_DATASET_ID, ROUTES_PACKAGE_URL
    )
    # Un manifest fallido que nunca persistió un raw no debe apuntar a un archivo inexistente.
    assert manifest["raw_file"] is None
    assert manifest["content_hash"] is None
    assert manifest["row_count"] is None


def test_csv_utf8_invalido_conserva_los_bytes_raw_exactos_y_manifest_fallido_coherente(
    tmp_path, collector_factory
):
    invalid_utf8 = b"CODIGO,NOMBRE\n1,PARADA CENTRO\n2,\xff\xfe\x90 broken\n"
    resource = make_resource(
        resource_id="res-bad-encoding",
        name="paradas.csv",
        url=STOPS_RESOURCE_URL,
        content=invalid_utf8,
    )
    result = make_result(
        dataset_id=STOPS_DATASET_ID,
        title="Paradas de transporte público",
        resources=[resource],
    )
    transport = build_transport(
        package_url=STOPS_PACKAGE_URL,
        package_bytes=package_show_bytes(result),
        resource_url=STOPS_RESOURCE_URL,
        resource_content=invalid_utf8,
    )
    collector = collector_factory(transport=transport)

    manifest = collector.collect(STOPS_DATASET_ID)

    assert_failed_manifest(
        manifest,
        tmp_path / "raw",
        tmp_path / "manifests",
        STOPS_DATASET_ID,
        STOPS_PACKAGE_URL,
        raw_bytes=invalid_utf8,
    )
    assert any("UTF-8" in warning for warning in manifest["warnings"])
    raw_path = expected_raw_path(tmp_path / "raw", STOPS_DATASET_ID)
    assert raw_path.read_bytes() == invalid_utf8  # bytes exactos conservados, nunca reserializados
    assert manifest["content_hash"] == hashlib.sha256(raw_path.read_bytes()).hexdigest()


def test_content_hash_se_calcula_y_verifica_contra_el_raw_en_disco(
    monkeypatch, tmp_path, collector_factory
):
    _, _, transport = routes_world()
    collector = collector_factory(transport=transport)

    original_write_raw = CkanSnapshotCollector._write_raw

    def tampering_write(raw_path: Path, body: bytes) -> None:
        original_write_raw(raw_path, body + b"TAMPERED-ON-DISK")

    monkeypatch.setattr(CkanSnapshotCollector, "_write_raw", staticmethod(tampering_write))

    with pytest.raises(OSError, match="verificaci"):
        collector.collect(ROUTES_DATASET_ID)

    # Fail closed: sin reclamos huérfanos, sin archivo raw suelto, sin manifest.
    # (Pueden quedar directorios padre vacíos, igual que en cualquier otra ruta de fallo.)
    assert [p for p in (tmp_path / "raw").rglob("*") if p.is_file()] == []
    assert [p for p in (tmp_path / "manifests").rglob("*") if p.is_file()] == []


# ---------------------------------------------------------------------------
# 21. Sidecar de reparación offline de manifests huérfanos
# ---------------------------------------------------------------------------

ORPHAN_CONTENT_HASH = "a15063103fc7ea1e050f73b0fd8045def0bc786799069db32daebcd71f11c6ef"


def write_orphan_failed_manifest(
    manifest_dir: Path, dataset_id: str, *, raw_file: str | None = None
) -> Path:
    """Escribe un manifest fallido que reclama un archivo raw (que puede estar ausente)."""
    manifest_path = expected_manifest_path(manifest_dir, dataset_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "snapshot_id": f"{dataset_id}@{FIXED_UTC_STAMP}",
        "source_id": DATASET_SPECS[dataset_id]["source_id"],
        "dataset_id": dataset_id,
        "collection_timestamp_utc": "2026-08-02T18:51:08Z",
        "status": "failed",
        "raw_file": raw_file if raw_file is not None else f"{dataset_id}/{FIXED_UTC_STAMP}.json",
        "content_hash": ORPHAN_CONTENT_HASH,
        "row_count": None,
        "warnings": ["CSV body is not valid UTF-8"],
        "notes": "Body validation failed",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def default_sidecar_path(manifest_path: Path) -> Path:
    return manifest_path.with_name(
        manifest_path.name.replace(".manifest.json", ".manifest.correction.json")
    )


def test_supersede_orphan_manifest_escribe_sidecar_sin_tocar_el_original(tmp_path):
    manifest_path = write_orphan_failed_manifest(tmp_path / "manifests", STOPS_DATASET_ID)
    original_bytes = manifest_path.read_bytes()

    sidecar = supersede_orphan_manifest(manifest_path, tmp_path / "raw")

    sidecar_path = default_sidecar_path(manifest_path)
    assert sidecar_path.is_file()
    assert json.loads(sidecar_path.read_text(encoding="utf-8")) == sidecar
    assert sidecar["status"] == "superseded"
    assert sidecar["raw_verifiable"] is False
    assert sidecar["raw_file"] is None
    assert sidecar["content_hash"] is None
    assert sidecar["row_count"] is None
    # Los reclamos huérfanos sobreviven solo como reclamos explícitamente no verificados...
    assert sidecar["unverified_original_claims"] == {
        "raw_file": f"{STOPS_DATASET_ID}/{FIXED_UTC_STAMP}.json",
        "content_hash": ORPHAN_CONTENT_HASH,
    }
    # ...y el sidecar declara que no hay ningún raw disponible y que el hash no está confirmado.
    assert "archivo raw" in sidecar["note"].lower()
    assert "no está confirmado" in sidecar["note"].lower()
    # El manifest original se lee, nunca se reescribe; no se inventa ningún raw.
    assert manifest_path.read_bytes() == original_bytes
    assert list((tmp_path / "raw").rglob("*")) == []


def test_supersede_orphan_manifest_falla_cerrado_cuando_el_raw_file_existe(tmp_path):
    manifest_path = write_orphan_failed_manifest(tmp_path / "manifests", STOPS_DATASET_ID)
    raw_path = tmp_path / "raw" / STOPS_DATASET_ID / f"{FIXED_UTC_STAMP}.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"the raw actually exists")

    with pytest.raises(FileExistsError, match="no es huérfano"):
        supersede_orphan_manifest(manifest_path, tmp_path / "raw")

    assert not default_sidecar_path(manifest_path).exists()


@pytest.mark.parametrize(
    "unsafe_raw_file",
    ["../escape.json", "/etc/passwd", "other/../../escape.json"],
    ids=["traversal", "absoluta", "traversal-anidada"],
)
def test_supersede_orphan_manifest_rechaza_rutas_raw_inseguras(tmp_path, unsafe_raw_file):
    manifest_path = write_orphan_failed_manifest(
        tmp_path / "manifests", STOPS_DATASET_ID, raw_file=unsafe_raw_file
    )

    with pytest.raises(ValueError, match="raw_file"):
        supersede_orphan_manifest(manifest_path, tmp_path / "raw")

    assert not default_sidecar_path(manifest_path).exists()


def test_supersede_orphan_manifest_nunca_sobrescribe_un_sidecar_existente(tmp_path):
    manifest_path = write_orphan_failed_manifest(tmp_path / "manifests", STOPS_DATASET_ID)
    sidecar_path = default_sidecar_path(manifest_path)
    sidecar_path.write_text('{"existing": true}', encoding="utf-8")

    with pytest.raises(FileExistsError):
        supersede_orphan_manifest(manifest_path, tmp_path / "raw", sidecar_path=sidecar_path)

    assert sidecar_path.read_text(encoding="utf-8") == '{"existing": true}'
    assert manifest_path.read_text(encoding="utf-8") != ""  # original intacto
