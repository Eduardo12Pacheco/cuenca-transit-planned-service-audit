"""Implementación de la validación estricta de snapshots manifest/raw.

Ver ``mobility_reliability.validation`` para el contrato público y la
semántica. Este módulo realiza la validación estructural en sí; nunca escribe,
descarga ni muta nada.
"""

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from mobility_reliability.ingestion.ckan_snapshot import (
    CKAN_PACKAGE_SHOW_URLS,
    DATASET_SPECS,
)

__all__ = [
    "OFFICIAL_CC_BY_NC_2_0_URL",
    "SnapshotValidationError",
    "SourceSnapshot",
    "validate_source_snapshot",
]

OFFICIAL_CC_BY_NC_2_0_URL = "http://creativecommons.org/licenses/by-nc/2.0/"
_REQUIRED_LICENSE_ID = "cc-nc"
_REQUIRED_LICENSE_DECLARED = "CC BY-NC 2.0"
_APPROVED_LICENSE_HOST = "creativecommons.org"
_APPROVED_LICENSE_PATH = "/licenses/by-nc/2.0"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Marcadores geometry/geoespaciales reflejados de la compuerta de ingestión
# (``CkanSnapshotCollector._is_geometric``): no se acepta un recurso
# seleccionado cuyo id/name/description/url identifique datos de geometría.
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

# Campos de cadena obligatorios y no vacíos de la proyección del manifest.
# El portal publica source_published_at como ISO sin zona horaria; se acepta
# esa forma, mientras collection_timestamp_utc debe ser UTC estricto.
_REQUIRED_STRING_FIELDS = (
    "snapshot_id",
    "source_id",
    "dataset_id",
    "source_url",
    "resource_id",
    "resource_name",
    "resource_url",
    "resource_format",
    "license_declared",
    "license_published",
    "license_id",
    "license_url",
    "attribution",
    "content_hash",
    "raw_file",
    "collection_timestamp_utc",
    "source_published_at",
)

# Claves de metadatos de corte/fecha requeridas en el dict ``resource`` anidado.
_RESOURCE_CUTOFF_KEYS = ("description", "created", "last_modified", "metadata_modified")


class SnapshotValidationError(Exception):
    """Se lanza cuando un snapshot capturado falla la validación estructural (fail closed).

    Los fallos estructurales de provenance se lanzan; nunca se degradan a
    advertencias. El mensaje enumera cada problema detectado.
    """


@dataclass
class SourceSnapshot:
    """Un snapshot de fuente validado: proyección más datos necesarios río abajo.

    Atributos públicos: los campos de la proyección ``source_snapshot``
    (``snapshot_id``, ``source_id``, ``dataset_id``, ``source_url``,
    ``resource_id``, ``resource_name``, ``resource_format``, ``resource_url``,
    ``collection_timestamp_utc``, ``source_published_at`` (obligatorio; se
    acepta la forma ISO ingenua del portal), ``license_*``,
    ``attribution``, ``content_hash``, ``raw_file``, ``row_count``, ``status``,
    ``schema_version``, ``resource_cutoff``, ``retrieval_method``,
    ``warnings``, ``notes``) más los datos estructurales que la capa de
    transformación necesita: el dict completo ``manifest``, la ``raw_path``
    absoluta, la tupla ``header`` del CSV y las ``rows`` analizadas (un dict
    por fila de datos; claves = nombres del encabezado, valores = cadenas raw
    textuales).

    ``as_dict()`` devuelve solo la proyección ``source_snapshot`` compatible
    con JSON.
    """

    snapshot_id: str
    source_id: str
    dataset_id: str
    source_url: str
    resource_id: str
    resource_name: str
    resource_format: str
    resource_url: str
    collection_timestamp_utc: str
    source_published_at: str
    license_declared: str
    license_published: str
    license_id: str
    license_url: str
    attribution: str
    content_hash: str
    raw_file: str
    row_count: int
    status: str
    schema_version: int
    resource_cutoff: dict
    retrieval_method: str
    warnings: list
    notes: str
    manifest: dict = field(repr=False)
    raw_path: Path = field(repr=False)
    header: tuple = field(repr=False)
    rows: list = field(repr=False)

    def as_dict(self) -> dict:
        """Proyección ``source_snapshot`` compatible con JSON (sin datos raw)."""
        return {
            "snapshot_id": self.snapshot_id,
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "source_url": self.source_url,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "resource_format": self.resource_format,
            "resource_url": self.resource_url,
            "collection_timestamp_utc": self.collection_timestamp_utc,
            "source_published_at": self.source_published_at,
            "license_declared": self.license_declared,
            "license_published": self.license_published,
            "license_id": self.license_id,
            "license_url": self.license_url,
            "attribution": self.attribution,
            "content_hash": self.content_hash,
            "raw_file": self.raw_file,
            "row_count": self.row_count,
            "status": self.status,
            "schema_version": self.schema_version,
            "resource_cutoff": dict(self.resource_cutoff),
            "retrieval_method": self.retrieval_method,
            "warnings": list(self.warnings),
            "notes": self.notes,
        }


def _is_blank(value: object) -> bool:
    return not isinstance(value, str) or not value.strip()


def _is_official_cc_by_nc_2_0_url(published: object) -> bool:
    """URL oficial de la licencia CC BY-NC 2.0 (http/https, barra final opcional).

    Los puertos, userinfo, query strings y fragmentos se rechazan por
    ambiguos; la mayúscula/minúscula de scheme y host y HTTP-vs-HTTPS son
    equivalentes. Refleja la compuerta de licencia de la ingestión.
    """
    if not isinstance(published, str) or not published.strip():
        return False
    try:
        parts = urlsplit(published.strip())
    except ValueError:
        return False
    if parts.scheme.lower() not in ("http", "https"):
        return False
    if parts.netloc.lower() != _APPROVED_LICENSE_HOST:
        return False
    if parts.query or parts.fragment:
        return False
    return parts.path in (_APPROVED_LICENSE_PATH, f"{_APPROVED_LICENSE_PATH}/")


def _is_geometric_resource(resource: dict) -> bool:
    """True cuando id/name/description/url identifican datos geometry/geoespaciales."""
    text = " ".join(
        str(resource.get(key) or "").lower() for key in ("id", "name", "description", "url")
    )
    return any(marker in text for marker in _GEOMETRY_MARKERS)


def _parse_iso(value: object) -> datetime | None:
    """Analiza una cadena ISO-8601 estilo CKAN (se acepta el sufijo ``Z``)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_utc(value: object) -> datetime | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc) if parsed.utcoffset() == timedelta(0) else None


def validate_source_snapshot(manifest_path: str | Path, raw_dir: str | Path) -> SourceSnapshot:
    """Valida estrictamente un snapshot capturado y devuelve su ``SourceSnapshot``.

    Lee el manifest y los bytes raw exactos localmente; lanza
    ``SnapshotValidationError`` ante cualquier inconsistencia estructural
    (ver el docstring del paquete para la lista fail-closed completa). En
    caso de éxito devuelve la proyección validada más manifest/raw/filas para
    las transformaciones.

    ``raw_dir`` es la raíz contra la que se resuelve el ``raw_file`` relativo
    del manifest (normalmente ``data/raw``).
    """
    manifest_path = Path(manifest_path)
    raw_dir = Path(raw_dir)
    problems: list[str] = []

    if not manifest_path.is_file():
        raise SnapshotValidationError(
            f"no se encontró el archivo manifest: {manifest_path}; no se puede validar el snapshot"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotValidationError(f"el manifest no es JSON legible en {manifest_path}: {exc}")
    if not isinstance(manifest, dict):
        raise SnapshotValidationError(
            f"el manifest no es un objeto JSON en {manifest_path} (encontrado {type(manifest).__name__})"
        )

    # -- estado (status) ---------------------------------------------------------
    status = manifest.get("status")
    if status != "success":
        problems.append(f"el status es {status!r}; solo se validan snapshots con status 'success'")

    # -- campos obligatorios ----------------------------------------------------
    for key in _REQUIRED_STRING_FIELDS:
        if _is_blank(manifest.get(key)):
            problems.append(f"el campo obligatorio {key} falta o está vacío")

    schema_version = manifest.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version < 1:
        problems.append(f"schema_version {schema_version!r} es inválida (se espera int >= 1)")

    row_count = manifest.get("row_count")
    if not isinstance(row_count, int) or isinstance(row_count, bool) or row_count < 0:
        problems.append(f"row_count {row_count!r} es inválido (se espera int >= 0)")

    # -- marcas de tiempo -------------------------------------------------------
    collection_utc = manifest.get("collection_timestamp_utc")
    if not isinstance(collection_utc, str) or _parse_utc(collection_utc) is None:
        problems.append(
            f"collection_timestamp_utc {collection_utc!r} no es una marca de tiempo UTC ISO-8601 válida"
        )
    source_published_at = manifest.get("source_published_at")
    if not _is_blank(source_published_at) and _parse_iso(source_published_at) is None:
        problems.append(
            f"source_published_at {source_published_at!r} no es una marca de tiempo ISO-8601 válida "
            "(se acepta ISO ingenua; el portal publica sin zona horaria)"
        )

    # -- dataset / source_url / source_id --------------------------------------
    dataset_id = manifest.get("dataset_id")
    if dataset_id not in CKAN_PACKAGE_SHOW_URLS:
        problems.append(
            f"dataset_id {dataset_id!r} no es uno de los datasets aprobados "
            f"{sorted(CKAN_PACKAGE_SHOW_URLS)}"
        )
        dataset_id = None  # evita el KeyError de abajo mientras problems ya lo reporta

    source_url = manifest.get("source_url")
    if dataset_id is not None and source_url != CKAN_PACKAGE_SHOW_URLS[dataset_id]:
        problems.append(
            f"source_url {source_url!r} no es la URL package_show aprobada exacta de "
            f"{dataset_id}"
        )

    source_id = manifest.get("source_id")
    if dataset_id is not None and source_id != DATASET_SPECS[dataset_id]["source_id"]:
        problems.append(f"source_id {source_id!r} es inconsistente con el dataset {dataset_id}")

    # -- huella de licencia ----------------------------------------------------
    license_id = manifest.get("license_id")
    if license_id != _REQUIRED_LICENSE_ID:
        problems.append(f"license_id {license_id!r} != {_REQUIRED_LICENSE_ID!r}")
    license_url = manifest.get("license_url")
    if not _is_official_cc_by_nc_2_0_url(license_url):
        problems.append(f"license_url {license_url!r} no es la URL oficial CC BY-NC 2.0")
    if manifest.get("license_declared") != _REQUIRED_LICENSE_DECLARED:
        problems.append(
            f"license_declared {manifest.get('license_declared')!r} != {_REQUIRED_LICENSE_DECLARED!r}"
        )

    # -- atribución / consistencia de resource ---------------------------------
    if _is_blank(manifest.get("attribution")):
        problems.append("la atribución falta o está vacía")

    resource = manifest.get("resource")
    if not isinstance(resource, dict) or not resource:
        problems.append("los metadatos de resource faltan o no son un objeto")
        resource = {}

    resource_format = manifest.get("resource_format")
    nested_format = resource.get("format") if resource else None
    if resource_format is None or not isinstance(resource_format, str) or resource_format.strip().upper() != "CSV":
        problems.append(
            f"resource_format {resource_format!r} no es CSV; solo se aceptan recursos CSV"
        )
    elif not (isinstance(nested_format, str) and nested_format.strip().upper() == "CSV"):
        problems.append(
            f"el formato anidado de resource {nested_format!r} es inconsistente (se esperaba CSV)"
        )

    resource_id = manifest.get("resource_id")
    if resource and resource.get("id") != resource_id:
        problems.append("resource_id es inconsistente con los metadatos anidados de resource")
    if resource and resource.get("name") != manifest.get("resource_name"):
        problems.append("resource_name es inconsistente con los metadatos anidados de resource")
    if resource and resource.get("url") != manifest.get("resource_url"):
        problems.append("resource_url es inconsistente con los metadatos anidados de resource")
    if resource and _is_geometric_resource(resource):
        problems.append(
            "el recurso seleccionado identifica datos geometry/geoespaciales "
            "(geometry de rutas, recorrido, georreferenciado, shapes) y no se acepta"
        )
    if resource:
        for key in _RESOURCE_CUTOFF_KEYS:
            if key not in resource:
                problems.append(f"los metadatos anidados de resource no tienen la clave de corte {key!r}")

    # -- consistencia de los metadatos del paquete (source_metadata) -----------
    source_metadata = manifest.get("source_metadata")
    if not isinstance(source_metadata, dict) or not source_metadata:
        problems.append("source_metadata falta o no es un objeto")
    else:
        if source_metadata.get("name") != dataset_id:
            problems.append(
                f"source_metadata.name {source_metadata.get('name')!r} no coincide con "
                f"dataset_id {dataset_id!r}"
            )
        published_resources = source_metadata.get("resources")
        if not isinstance(published_resources, list):
            problems.append("source_metadata.resources falta o no es una lista")
        elif resource_id not in [
            entry.get("id") for entry in published_resources if isinstance(entry, dict)
        ]:
            problems.append(
                f"source_metadata.resources no contiene el resource_id seleccionado {resource_id!r}"
            )

    # -- ruta raw --------------------------------------------------------------
    raw_file = manifest.get("raw_file")
    raw_path: Path | None = None
    if not isinstance(raw_file, str) or not raw_file.strip():
        problems.append("raw_file falta o está vacío")
    else:
        raw_file = raw_file.strip()
        candidate = Path(raw_file)
        if candidate.is_absolute() or ".." in candidate.parts:
            problems.append(f"raw_file {raw_file!r} debe ser una ruta relativa sin traversal")
        else:
            resolved = (raw_dir / candidate).resolve()
            if not resolved.is_relative_to(raw_dir.resolve()):
                problems.append(f"raw_file {raw_file!r} escapa de raw_dir {raw_dir}")
            elif not resolved.is_file():
                problems.append(f"no se encontró el archivo raw en {resolved}")
            else:
                raw_path = resolved

    # -- hash de contenido -----------------------------------------------------
    content_hash = manifest.get("content_hash")
    if not isinstance(content_hash, str) or _SHA256_RE.fullmatch(content_hash) is None:
        problems.append(f"content_hash {content_hash!r} no es un SHA-256 hexadecimal en minúsculas de 64 caracteres")

    if problems:
        _raise_with(problems)

    # -- bytes raw: hash, UTF-8, CSV, conteo de filas --------------------------
    assert raw_path is not None  # protegido: problems ya se habría lanzado arriba
    raw_bytes = raw_path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if digest != content_hash:
        problems.append(
            f"el content_hash no coincide: el manifest declara {content_hash}, "
            f"los bytes raw generan el hash {digest}"
        )
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        problems.append(f"los bytes raw no son UTF-8 válido: {exc}")
    else:
        try:
            parsed_rows = list(csv.reader(io.StringIO(text)))
        except csv.Error as exc:
            problems.append(f"el CSV raw no pudo analizarse: {exc}")
        else:
            non_empty = [row for row in parsed_rows if row]
            if not non_empty:
                problems.append("el CSV raw no contiene filas")
            else:
                header = tuple(non_empty[0])
                data_rows = non_empty[1:]
                ragged = [i for i, row in enumerate(non_empty[1:], start=2) if len(row) != len(header)]
                if ragged:
                    problems.append(
                        f"el CSV raw está desalineado: las filas de datos {ragged} tienen un conteo de campos "
                        f"distinto del encabezado ({len(header)})"
                    )
                elif len(data_rows) != row_count:
                    problems.append(
                        f"el row_count no coincide: el manifest declara {row_count}, "
                        f"el CSV raw tiene {len(data_rows)} filas de datos"
                    )

    if problems:
        _raise_with(problems)

    rows = [
        dict(zip(header, row, strict=True)) for row in data_rows  # type: ignore[name-defined]
    ]
    return SourceSnapshot(
        snapshot_id=manifest["snapshot_id"],
        source_id=manifest["source_id"],
        dataset_id=manifest["dataset_id"],
        source_url=manifest["source_url"],
        resource_id=manifest["resource_id"],
        resource_name=manifest["resource_name"],
        resource_format=manifest["resource_format"],
        resource_url=manifest["resource_url"],
        collection_timestamp_utc=manifest["collection_timestamp_utc"],
        source_published_at=source_published_at,
        license_declared=manifest["license_declared"],
        license_published=manifest["license_published"],
        license_id=manifest["license_id"],
        license_url=manifest["license_url"],
        attribution=manifest["attribution"],
        content_hash=content_hash,
        raw_file=raw_file,
        row_count=row_count,
        status=status,
        schema_version=schema_version,
        resource_cutoff={key: resource.get(key) for key in _RESOURCE_CUTOFF_KEYS},
        retrieval_method=manifest.get("retrieval_method"),
        warnings=list(manifest.get("warnings") or []),
        notes=manifest.get("notes") or "",
        manifest=manifest,
        raw_path=raw_path,
        header=header,
        rows=rows,
    )


def _raise_with(problems: list[str]) -> None:
    raise SnapshotValidationError(
        "falló la validación del snapshot de fuente:\n- " + "\n- ".join(problems)
    )
