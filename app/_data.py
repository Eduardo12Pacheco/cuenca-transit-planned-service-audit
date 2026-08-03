"""Acceso de solo lectura a los datos de la demo local sin conexión.

Este módulo solo *carga*: la transformación canónica combinada
(``transform_captures``), el artefacto existente de auditoría de coordenadas y
(según el modo; solo en checkout limpio) el fixture sintético versionado con forma
canónica. La validación estricta y toda la semántica de parsing permanecen en
``mobility_reliability`` (``validate_source_snapshot`` / ``transform_captures``)
— nada aquí duplica el parser ``_coordinate``, el parser de horarios ni la
clasificación de la auditoría. La demo nunca escribe nada.

``load_combined`` sigue siendo estricta real/raw para sus llamadores
existentes. ``load_demo_payload`` decide el modo de la demo por la presencia de
los dos raw aprobados: ambos presentes -> camino real estricto; ninguno
presente -> carga/valida la forma del fixture sintético de forma estricta;
exactamente uno presente -> fail closed (nunca un respaldo).

Todas las rutas apuntan por defecto a las capturas aprobadas fijadas; los
llamadores (tests) pueden pasar rutas explícitas.
"""

from __future__ import annotations

import json
from pathlib import Path

from mobility_reliability.transformation import transform_captures
from mobility_reliability.validation import SnapshotValidationError

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent

ROUTES_MANIFEST = REPO_ROOT / "data/manifests/rutas-de-transporte-publico/2026-08-02T18-51-08Z.manifest.json"
STOPS_MANIFEST = (
    REPO_ROOT / "data/manifests/paradas-de-transporte-publico/2026-08-02T19-27-36Z.manifest.json"
)
RAW_DIR = REPO_ROOT / "data/raw"
COORDINATE_AUDIT_JSON = REPO_ROOT / "data/quality/coordinate-format-audit.json"
COORDINATE_AUDIT_MARKDOWN = REPO_ROOT / "docs/coordinate-quality-audit.md"

# Las dos capturas raw aprobadas (las rutas reflejan los valores raw_file
# fijados en los manifests aprobados). Solo su existencia decide el modo de la
# demo; el camino real nunca toca el fixture sintético.
ROUTES_RAW_FILE = "rutas-de-transporte-publico/2026-08-02T18-51-08Z.json"
STOPS_RAW_FILE = "paradas-de-transporte-publico/2026-08-02T19-27-36Z.json"

# Fixture sintético versionado con forma canónica, usado SOLO cuando no existe
# ningún raw aprobado (checkout limpio): ver data/demo/README.md.
SYNTHETIC_COMBINED_JSON = REPO_ROOT / "data/demo/synthetic-combined.json"

# Modos de datos de la demo que devuelve ``load_demo_payload``.
DATA_MODE_REAL = "real"
DATA_MODE_SYNTHETIC = "synthetic"

# Aviso prominente en español para el modo sintético (frase exacta, fijada
# por tests): la demo nunca debe confundirse con evidencia de Cuenca.
SYNTHETIC_MODE_BANNER = (
    "Modo demostración: los datos mostrados son completamente sintéticos, "
    "no son datos oficiales y no describen el servicio real de Cuenca."
)

# Leyenda de la barra lateral en modo sintético: distingue el fixture de los
# snapshots oficiales aprobados.
SYNTHETIC_EVIDENCE_HINT = (
    "Fixture sintético versionado (data/demo/synthetic-combined.json): los "
    "valores son ficticios, no provienen de snapshots oficiales y no "
    "describen el servicio real."
)

# Texto de la pestaña de evidencia en modo sintético: aquí nunca se renderizan
# hashes/IDs de recurso/URLs/licencias oficiales.
SYNTHETIC_PROVENANCE_WARNING = (
    "Modo demostración: TODO este contenido es sintético. Esta vista no "
    "muestra hashes raw oficiales, IDs de recurso, URLs de fuente, licencias "
    "ni atribuciones oficiales: el fixture no contiene evidencia oficial."
)
SYNTHETIC_PROVENANCE_INTRO = (
    "Todos los valores de esta demo provienen del fixture sintético "
    "versionado `data/demo/synthetic-combined.json` (fixture "
    "`{fixture_name}`), creado desde cero por los autores del repositorio: "
    "no se deriva de capturas oficiales, de tests ni de archivos raw. Ver "
    "`data/demo/README.md` para autoría, limitaciones y reutilización."
)

# Límite prominente de solo-planificado mostrado en cada ejecución de la demo
# (redacción exacta en español con saltos de línea legibles; fijado por tests).
# La demo es evidencia de servicio planificado, nunca un producto de movilidad
# observada.
PLANNED_ONLY_BOUNDARY = (
    "Esta demo muestra únicamente servicio planificado.\n"
    "No representa puntualidad, retrasos, frecuencia observada,\n"
    "GTFS-Realtime, AVL ni cobertura geográfica."
)

# Frase exacta en español de la decisión de no mostrar mapa (fijada por
# tests). El formato de las coordenadas de la fuente, el orden de los ejes y el
# CRS no están resueltos, por lo que no se puede dibujar un mapa; la demo
# explica que es una decisión de calidad de datos, no una función faltante.
NO_MAP_DECISION = (
    "No se muestra un mapa porque el formato de las coordenadas,\n"
    "el orden de los ejes y el sistema de referencia CRS no están resueltos."
)

# Etiquetas en español de los tipos de día para la visualización; los valores
# canónicos de day_type (weekday/saturday/sunday) nunca cambian.
DAY_TYPE_LABELS = {
    "weekday": "Entre semana",
    "saturday": "Sábado",
    "sunday": "Domingo",
}
DIRECTION_VALUES = ("IDA", "RETORNO")


def load_combined(
    route_manifest: str | Path | None = None,
    stops_manifest: str | Path | None = None,
    raw_dir: str | Path | None = None,
) -> dict:
    """Carga la transformación canónica combinada de los dos snapshots aprobados.

    Primero ejecuta la validación estructural estricta (``SnapshotValidationError``
    se propaga: fail closed). Devuelve el dict de ``transform_captures`` con
    ``source_snapshots``, ``mobility_network``, ``planned_service``,
    ``quality_reports`` y los metadatos de ``transformation``. Solo lectura.
    """
    return transform_captures(
        Path(route_manifest) if route_manifest is not None else ROUTES_MANIFEST,
        Path(stops_manifest) if stops_manifest is not None else STOPS_MANIFEST,
        Path(raw_dir) if raw_dir is not None else RAW_DIR,
    )


def load_coordinate_audit(path: str | Path | None = None) -> dict | None:
    """Lee el artefacto existente de auditoría de coordenadas (solo lectura).

    Devuelve el dict JSON, o ``None`` cuando el artefacto falta o no es JSON
    legible (la demo muestra entonces la decisión de auditoría como no
    disponible — nunca inventa una decisión).
    """
    audit_path = Path(path) if path is not None else COORDINATE_AUDIT_JSON
    if not audit_path.is_file():
        return None
    try:
        loaded = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def format_service_minutes(minutes: int | None) -> str | None:
    """Formatea los minutos tipados del día de servicio como ``H:MM`` solo para
    visualización.

    Solo formato de vista: los valores raw ``*_raw`` H:MM siguen siendo la
    fuente de verdad y siempre se muestran junto a estos. ``1510`` -> ``"25:10"``
    (los valores superiores a 24:00 nunca se convierten a calendario).
    """
    if minutes is None:
        return None
    return f"{minutes // 60}:{minutes % 60:02d}"


def load_failure_message(
    exc: BaseException,
    *,
    route_manifest: str | Path | None = None,
    stops_manifest: str | Path | None = None,
    raw_dir: str | Path | None = None,
) -> str:
    """Cartel de error legible para un snapshot que no pudo cargarse.

    El error de validación estricta se muestra textualmente (sin traceback)
    junto con la identidad esperada de manifest/fuente. La demo nunca muestra
    valores inventados cuando la evidencia subyacente falta.
    """
    return (
        "La demo no pudo cargar los snapshots capturados, por lo que no se "
        "muestran valores. La validación estricta falló y no se muestra ningún "
        "rastreo de error:\n\n"
        f"{exc}\n\n"
        "Manifiestos esperados:\n"
        f"- {Path(route_manifest) if route_manifest is not None else ROUTES_MANIFEST}\n"
        f"- {Path(stops_manifest) if stops_manifest is not None else STOPS_MANIFEST}\n"
        f"Raíz de archivos raw: {Path(raw_dir) if raw_dir is not None else RAW_DIR}"
    )


_CANONICAL_DAY_TYPES = ("weekday", "saturday", "sunday")
_CANONICAL_SERVICE_STATUSES = ("active", "no_service", "invalid")
_CANONICAL_DIRECTIONS = ("IDA", "RETORNO")


class SyntheticFixtureError(Exception):
    """Se lanza cuando el fixture sintético de demostración versionado falta o es
    inválido.

    La demo falla de forma estricta ante este error (un cartel claro en
    español, sin valores) y nunca recurre a nada más.
    """


def _approved_raw_paths(raw_dir: Path) -> tuple[Path, Path]:
    """Las dos rutas de captura raw aprobadas, resueltas bajo ``raw_dir``."""
    return raw_dir / ROUTES_RAW_FILE, raw_dir / STOPS_RAW_FILE


def load_demo_payload(
    route_manifest: str | Path | None = None,
    stops_manifest: str | Path | None = None,
    raw_dir: str | Path | None = None,
    synthetic_combined: str | Path | None = None,
) -> dict:
    """Cargador de la demo de solo lectura, consciente del modo.

    Devuelve ``{"mode", "combined", "audit"}`` donde ``mode`` es
    ``DATA_MODE_REAL`` (ambas capturas raw aprobadas presentes: ``load_combined``
    estricto más la auditoría de coordenadas existente, sin cambios) o
    ``DATA_MODE_SYNTHETIC`` (ningún raw aprobado presente: carga/valida de
    forma estricta la forma del fixture sintético versionado con forma canónica
    y usa su payload de auditoría sintético).

    Reglas fail-closed (nunca un respaldo): exactamente un raw aprobado
    presente lanza ``SnapshotValidationError`` (evidencia parcial); la
    evidencia real inválida se propaga desde ``load_combined`` sin cambios;
    un fixture ausente, malformado o con forma inválida lanza
    ``SyntheticFixtureError``.
    """
    resolved_raw_dir = Path(raw_dir) if raw_dir is not None else RAW_DIR
    routes_raw, stops_raw = _approved_raw_paths(resolved_raw_dir)
    routes_present = routes_raw.is_file()
    stops_present = stops_raw.is_file()
    if routes_present and stops_present:
        return {
            "mode": DATA_MODE_REAL,
            "combined": load_combined(route_manifest, stops_manifest, resolved_raw_dir),
            "audit": load_coordinate_audit(),
        }
    if not routes_present and not stops_present:
        combined = load_synthetic_combined(synthetic_combined)
        return {
            "mode": DATA_MODE_SYNTHETIC,
            "combined": combined,
            "audit": combined["coordinate_audit"],
        }
    present = routes_raw if routes_present else stops_raw
    missing = stops_raw if routes_present else routes_raw
    raise SnapshotValidationError(
        "evidencia parcial: exactamente uno de los dos raw aprobados está "
        f"presente (encontrado {present}, faltante {missing}); la demo falla "
        "de forma estricta y nunca recurre al fixture sintético"
    )


def load_synthetic_combined(path: str | Path | None = None) -> dict:
    """Carga y valida de forma estricta la forma del fixture sintético versionado.

    El fixture tiene forma de salida canónica (sin filas raw de fuente, sin
    parsing, sin transformación): este cargador solo lee el JSON y valida la
    estructura que las vistas necesitan. Cualquier estado ausente, malformado
    o con forma inválida lanza ``SyntheticFixtureError`` (fail closed, sin
    valores).
    """
    fixture_path = Path(path) if path is not None else SYNTHETIC_COMBINED_JSON
    if not fixture_path.is_file():
        raise SyntheticFixtureError(
            f"no se encontró el fixture sintético de demostración: {fixture_path}"
        )
    try:
        loaded = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyntheticFixtureError(
            f"el fixture sintético de demostración no es JSON legible en "
            f"{fixture_path}: {exc}"
        )
    if not isinstance(loaded, dict):
        raise SyntheticFixtureError(
            f"el fixture sintético de demostración no es un objeto JSON en "
            f"{fixture_path}"
        )
    _validate_synthetic_shape(loaded)
    return loaded


def _validate_synthetic_shape(loaded: dict) -> None:
    """Validación estructural de la forma del fixture sintético (sin parsing).

    Verifica las secciones canónicas y las claves exactas de registro que
    consumen las vistas, más los dominios de valores canónicos de
    day_type/service_status/direction, el marcador synthetic del fixture y el
    join de planned_service con el network_id de rutas. Los problemas se
    recopilan y se lanzan juntos.
    """
    problems: list[str] = []

    fixture = loaded.get("fixture")
    if not isinstance(fixture, dict) or fixture.get("synthetic") is not True:
        problems.append(
            "faltan los metadatos del fixture o no están marcados como synthetic=true"
        )

    for key, expected in (
        ("source_snapshots", list),
        ("mobility_network", list),
        ("planned_service", list),
        ("quality_reports", list),
        ("coordinate_audit", dict),
        ("transformation", dict),
    ):
        if not isinstance(loaded.get(key), expected):
            problems.append(f"falta la sección {key!r} o no es un/una {expected.__name__}")

    network = loaded.get("mobility_network")
    routes: list[dict] = []
    if isinstance(network, list):
        routes = [r for r in network if r.get("element_type") == "route"]
        stops = [r for r in network if r.get("element_type") == "stop"]
        if not routes:
            problems.append("mobility_network no tiene registros de rutas")
        if not stops:
            problems.append("mobility_network no tiene registros de paradas")
        for index, record in enumerate(network):
            if not isinstance(record, dict):
                problems.append(f"mobility_network[{index}] no es un objeto")
                continue
            element_type = record.get("element_type")
            required = ("network_id", "snapshot_id", "quality_flags")
            if element_type == "route":
                required += ("route_line", "company", "direction", "origin", "destination")
                if record.get("direction") not in _CANONICAL_DIRECTIONS:
                    problems.append(
                        f"mobility_network[{index}] direction "
                        f"{record.get('direction')!r} no está en {_CANONICAL_DIRECTIONS}"
                    )
            elif element_type == "stop":
                required += ("stop_id", "stop_name", "latitude", "longitude", "geometry")
            else:
                problems.append(
                    f"mobility_network[{index}] element_type desconocido {element_type!r}"
                )
            for key in required:
                if key not in record:
                    problems.append(f"mobility_network[{index}] no tiene {key!r}")
            if not isinstance(record.get("quality_flags"), list):
                problems.append(f"mobility_network[{index}] quality_flags no es una lista")

    services = loaded.get("planned_service")
    if isinstance(services, list):
        if not services:
            problems.append("planned_service está vacío")
        route_network_ids = {r.get("network_id") for r in routes}
        for index, record in enumerate(services):
            if not isinstance(record, dict):
                problems.append(f"planned_service[{index}] no es un objeto")
                continue
            for key in (
                "service_id",
                "snapshot_id",
                "network_id",
                "route_line",
                "direction",
                "day_type",
                "planned_start",
                "planned_end",
                "planned_headway",
                "planned_start_raw",
                "planned_end_raw",
                "planned_headway_raw",
                "service_status",
                "quality_flags",
                "provenance",
            ):
                if key not in record:
                    problems.append(f"planned_service[{index}] no tiene {key!r}")
            day_type = record.get("day_type")
            if day_type not in _CANONICAL_DAY_TYPES:
                problems.append(
                    f"planned_service[{index}] day_type {day_type!r} no está en "
                    f"{_CANONICAL_DAY_TYPES}"
                )
            status = record.get("service_status")
            if status not in _CANONICAL_SERVICE_STATUSES:
                problems.append(
                    f"planned_service[{index}] service_status {status!r} no está en "
                    f"{_CANONICAL_SERVICE_STATUSES}"
                )
            if record.get("direction") not in _CANONICAL_DIRECTIONS:
                problems.append(
                    f"planned_service[{index}] direction no está en {_CANONICAL_DIRECTIONS}"
                )
            if not isinstance(record.get("quality_flags"), list):
                problems.append(f"planned_service[{index}] quality_flags no es una lista")
            if not isinstance(record.get("provenance"), dict):
                problems.append(f"planned_service[{index}] provenance no es un objeto")
            if record.get("network_id") not in route_network_ids:
                problems.append(
                    f"planned_service[{index}] network_id "
                    f"{record.get('network_id')!r} no coincide con ningún registro de ruta"
                )

    snapshots = loaded.get("source_snapshots")
    if isinstance(snapshots, list):
        if len(snapshots) != 2:
            problems.append(
                "source_snapshots debe contener exactamente los dos snapshots de la demo"
            )
        for index, snapshot in enumerate(snapshots):
            if not isinstance(snapshot, dict):
                problems.append(f"source_snapshots[{index}] no es un objeto")
                continue
            for key in ("dataset_id", "snapshot_id", "collection_timestamp_utc", "row_count"):
                if key not in snapshot:
                    problems.append(f"source_snapshots[{index}] no tiene {key!r}")

    reports = loaded.get("quality_reports")
    if isinstance(reports, list):
        if len(reports) < 2:
            problems.append("quality_reports debe contener los reportes de rutas y paradas")
        if reports and not isinstance(reports[0], dict):
            problems.append("quality_reports[0] no es un objeto")
        if reports and isinstance(reports[0], dict):
            if not isinstance(reports[0].get("no_service_windows"), list):
                problems.append("quality_reports[0] no tiene una lista no_service_windows")
            if not isinstance(reports[0].get("schedule"), dict):
                problems.append("quality_reports[0] no tiene un objeto schedule")
        if len(reports) > 1 and not isinstance(reports[1], dict):
            problems.append("quality_reports[1] no es un objeto")
        if len(reports) > 1 and isinstance(reports[1], dict):
            if not isinstance(reports[1].get("coordinates"), dict):
                problems.append("quality_reports[1] no tiene un objeto coordinates")

    audit = loaded.get("coordinate_audit")
    if isinstance(audit, dict):
        for key in (
            "decision",
            "format_resolved",
            "conversion_justified",
            "geometry_generated",
            "columns_audited",
            "per_column_counts",
            "examples",
            "raw_sha256",
            "row_count",
        ):
            if key not in audit:
                problems.append(f"coordinate_audit no tiene {key!r}")
        if audit.get("decision") != "format_unresolved":
            problems.append(
                "la decisión de coordinate_audit debe ser 'format_unresolved' para la demo"
            )
        if not isinstance(audit.get("examples"), dict):
            problems.append("coordinate_audit examples no es un objeto")

    if problems:
        raise SyntheticFixtureError(
            "falló la validación de la forma del fixture sintético:\n- "
            + "\n- ".join(problems)
        )


def load_fixture_failure_message(exc: BaseException) -> str:
    """Cartel de error legible para un fixture sintético ausente o inválido.

    La demo nunca muestra valores inventados cuando el fixture no puede
    cargarse; el problema técnico se muestra textualmente (sin traceback).
    """
    return (
        "La demo no pudo cargar el fixture sintético de demostración, por lo "
        "que no se muestran valores. No hay capturas reales en este checkout "
        "y el modo demostración requiere el fixture versionado "
        f"({SYNTHETIC_COMBINED_JSON}). Sin rastreo de error:\n\n"
        f"{exc}"
    )


__all__ = [
    "APP_DIR",
    "REPO_ROOT",
    "ROUTES_MANIFEST",
    "STOPS_MANIFEST",
    "RAW_DIR",
    "ROUTES_RAW_FILE",
    "STOPS_RAW_FILE",
    "SYNTHETIC_COMBINED_JSON",
    "COORDINATE_AUDIT_JSON",
    "COORDINATE_AUDIT_MARKDOWN",
    "PLANNED_ONLY_BOUNDARY",
    "NO_MAP_DECISION",
    "DAY_TYPE_LABELS",
    "DIRECTION_VALUES",
    "DATA_MODE_REAL",
    "DATA_MODE_SYNTHETIC",
    "SYNTHETIC_MODE_BANNER",
    "SYNTHETIC_EVIDENCE_HINT",
    "SYNTHETIC_PROVENANCE_WARNING",
    "SYNTHETIC_PROVENANCE_INTRO",
    "SnapshotValidationError",
    "SyntheticFixtureError",
    "load_combined",
    "load_coordinate_audit",
    "load_demo_payload",
    "load_synthetic_combined",
    "load_fixture_failure_message",
    "format_service_minutes",
    "load_failure_message",
]
