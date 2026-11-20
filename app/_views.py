"""Modelos de vista puros y deterministas para la demo local sin conexión.

Estas funciones transforman la salida canónica de ``transform_captures`` y el
artefacto existente de auditoría de coordenadas en filas listas para
mostrarse. No importan nada de Streamlit y nunca parsean valores raw: los
estados, los minutos tipados, las incidencias de calidad y la provenance
provienen directamente de los registros canónicos; el único reformateo es la
visualización ``H:MM`` (los valores raw siempre se muestran junto a estos).

Aquí no hay mapa, ni decisiones de geometría ni conversión de coordenadas: la
vista de paradas reporta la decisión ``format_unresolved`` de la auditoría y
solo ejemplos raw exactos.
"""

from __future__ import annotations

from app._i18n import FLAG_DESCRIPTIONS, STATUS_LABELS

# Orden determinista de las categorías de ejemplos de la auditoría (refleja el
# orden de COORDINATE_CATEGORIES de la auditoría para legibilidad).
AUDIT_CATEGORY_ORDER = (
    "blank",
    "sentinel",
    "decimal_candidate",
    "decimal_comma_candidate",
    "thousands_separator_candidate",
    "dms_candidate",
    "wkt_or_geometry_candidate",
    "other_text",
    "unknown",
)

# La proporción estilo 68/76 se etiqueta solo como filas limpias del snapshot
# validado: nunca es cobertura geográfica ni de red completa.
CLEAN_ROWS_LABEL = "filas limpias del snapshot validado"


def _line_key(line: str) -> tuple:
    """Clave de ordenamiento determinista con conciencia numérica para líneas."""
    return (int(line) if line.isdigit() else float("inf"), line)


def _route_records(combined: dict) -> list[dict]:
    return [record for record in combined["mobility_network"] if record["element_type"] == "route"]


def _service_row(route: dict, record: dict | None, day_type: str) -> dict:
    """Una fila de visualización que une un registro de ruta con su registro de
    servicio planificado.

    ``flags`` combina las incidencias de calidad de identidad de la fila de ruta
    (por ejemplo ORIGEN/DESTINO sin valor) con las incidencias de calidad del
    horario de la ventana del día, deduplicadas y ordenadas de forma
    determinista. Los valores raw y tipados se conservan intactos.
    """
    route_flags = {f"{flag['field']}={flag['flag']}" for flag in (route.get("quality_flags") or [])}
    record_flags = (
        {f"{flag['field']}={flag['flag']}" for flag in (record.get("quality_flags") or [])}
        if record is not None
        else set()
    )
    flags = sorted(route_flags | record_flags)
    if record is None:
        # Inalcanzable con datos canónicos (cada fila de ruta produce un
        # registro por tipo de día); marcador defensivo para que las filas
        # nunca se descarten en silencio.
        return {
            "line": route["route_line"],
            "company": route["company"],
            "direction": route["direction"],
            "origin": route["origin"],
            "destination": route["destination"],
            "day_type": day_type,
            "start_raw": None,
            "end_raw": None,
            "headway_raw": None,
            "start_minutes": None,
            "end_minutes": None,
            "headway_minutes": None,
            "status": "missing",
            "flags": flags,
            "service_id": None,
            "network_id": route["network_id"],
            "provenance": route.get("provenance"),
        }
    return {
        "line": route["route_line"],
        "company": route["company"],
        "direction": route["direction"],
        "origin": route["origin"],
        "destination": route["destination"],
        "day_type": day_type,
        "start_raw": record.get("planned_start_raw"),
        "end_raw": record.get("planned_end_raw"),
        "headway_raw": record.get("planned_headway_raw"),
        "start_minutes": record.get("planned_start"),
        "end_minutes": record.get("planned_end"),
        "headway_minutes": record.get("planned_headway"),
        "status": record.get("service_status"),
        "flags": flags,
        "service_id": record.get("service_id"),
        "network_id": route["network_id"],
        "provenance": record.get("provenance"),
    }


def route_lines(combined: dict) -> list[str]:
    """Líneas de ruta únicas y ordenadas presentes en el snapshot capturado."""
    lines = {record["route_line"] for record in _route_records(combined)}
    return sorted(lines, key=_line_key)


def day_types(combined: dict) -> list[str]:
    """Tipos de día en orden canónico (weekday, saturday, sunday)."""
    ordered: list[str] = []
    for record in combined["planned_service"]:
        if record["day_type"] not in ordered:
            ordered.append(record["day_type"])
    return ordered


def service_rows(combined: dict, day_type: str) -> list[dict]:
    """Una fila de visualización por ruta para el tipo de día dado (las 76 filas)."""
    service_by_network = {
        record["network_id"]: record for record in combined["planned_service"] if record["day_type"] == day_type
    }
    routes = sorted(
        _route_records(combined),
        key=lambda record: (_line_key(record["route_line"]), record["direction"] or ""),
    )
    return [_service_row(route, service_by_network.get(route["network_id"]), day_type) for route in routes]


def route_rows(combined: dict) -> list[dict]:
    """Una fila de visualización por ruta con los campos de identidad y las
    incidencias de calidad."""
    routes = sorted(
        _route_records(combined),
        key=lambda record: (_line_key(record["route_line"]), record["direction"] or ""),
    )
    return [
        {
            "line": record["route_line"],
            "company": record["company"],
            "direction": record["direction"],
            "origin": record["origin"],
            "destination": record["destination"],
            "flags": sorted(f"{flag['field']}={flag['flag']}" for flag in record["quality_flags"]),
        }
        for record in routes
    ]


def selected_window(combined: dict, line: str, direction: str, day_type: str) -> dict | None:
    """La fila de visualización del servicio planificado para la selección
    exacta, o ``None``.

    ``None`` significa que el snapshot capturado no tiene ningún registro que
    coincida con la selección (por ejemplo un sentido que la fuente no publica
    para esa línea).
    """
    for record in combined["planned_service"]:
        if (record["route_line"], record["direction"], record["day_type"]) == (
            line,
            direction,
            day_type,
        ):
            route = next(
                (item for item in combined["mobility_network"] if item["network_id"] == record["network_id"]),
                None,
            )
            if route is None:
                continue
            return _service_row(route, record, day_type)
    return None


def no_service_window_rows(combined: dict) -> list[dict]:
    """Las ventanas sin servicio que reporta el reporte de calidad de rutas."""
    report = combined["quality_reports"][0]
    return [dict(window) for window in report.get("no_service_windows", [])]


def route_quality_summary(combined: dict) -> dict:
    """Números exactos de calidad de rutas, todos derivados del reporte canónico.

    ``clean_label`` está fijada a la etiqueta de lector en español
    ("filas limpias del snapshot validado"): la proporción limpia nunca
    significa cobertura geográfica ni de red completa.
    """
    report = combined["quality_reports"][0]
    schedule = report.get("schedule") or {}
    sense_counts: dict[str, int] = {"IDA": 0, "RETORNO": 0}
    for record in _route_records(combined):
        sense_counts[record["direction"]] = sense_counts.get(record["direction"], 0) + 1
    return {
        "row_count": report.get("row_count", 0),
        "missing_origen": report.get("missing_fields", {}).get("ORIGEN", 0),
        "missing_destino": report.get("missing_fields", {}).get("DESTINO", 0),
        "sense_counts": sense_counts,
        "schedule_cells": schedule.get("cells_total", 0),
        "schedule_cells_malformed": schedule.get("cells_malformed", 0),
        "interval_cells": schedule.get("interval_cells_total", 0),
        "interval_cells_invalid": schedule.get("interval_cells_invalid", 0),
        "no_service_windows_count": schedule.get("no_service_windows_count", 0),
        "elements_total": report.get("coverage", {}).get("elements_total", 0),
        "elements_clean": report.get("coverage", {}).get("elements_clean", 0),
        "clean_label": CLEAN_ROWS_LABEL,
    }


def stops_quality_summary(combined: dict, audit: dict | None) -> dict:
    """Números exactos de calidad de paradas más la decisión de la auditoría.

    ``geometry_rows`` cuenta los registros de parada cuya geometría de punto
    existe (una geometría solo existe cuando AMBAS coordenadas pasan el parser
    estricto). La decisión de la auditoría (``format_unresolved``) se transmite
    cuando el artefacto está disponible; si no, la decisión es ``None`` (nunca
    se inventa).
    """
    report = combined["quality_reports"][1]
    coordinates = report.get("coordinates") or {}
    stops = [record for record in combined["mobility_network"] if record["element_type"] == "stop"]
    geometry_rows = sum(1 for record in stops if record.get("geometry") is not None)
    return {
        "row_count": report.get("row_count", 0),
        "latitude": coordinates.get("latitude"),
        "longitude": coordinates.get("longitude"),
        "rows_with_both_valid": coordinates.get("rows_with_both_valid", 0),
        "valid_point_coverage": coordinates.get("valid_point_coverage", 0.0),
        "geometry_rows": geometry_rows,
        "audit_decision": audit.get("decision") if audit else None,
        "audit_format_resolved": audit.get("format_resolved") if audit else None,
        "audit_conversion_justified": audit.get("conversion_justified") if audit else None,
        "audit_geometry_generated": audit.get("geometry_generated") if audit else None,
        "audit_raw_sha256": audit.get("raw_sha256") if audit else None,
    }


def audit_example_rows(audit: dict, column: str, category: str, cap: int = 5) -> dict:
    """Ejemplos raw exactos limitados para una columna/categoría de la auditoría.

    Devuelve ``{"total": <count>, "rows": [{"row", "value"}, ...]}`` con las
    primeras ``cap`` ocurrencias en el orden de la auditoría. Los valores son
    las cadenas raw exactas (se conservan los espacios); nada se convierte.
    """
    examples = audit.get("examples", {}).get(column, {}).get(category, [])
    total = audit.get("per_column_counts", {}).get(column, {}).get(category, len(examples))
    return {"total": total, "rows": [dict(example) for example in examples[:cap]]}


def audit_columns_with_examples(audit: dict) -> list[tuple[str, str]]:
    """Pares (column, category) que tienen ejemplos, en orden determinista."""
    pairs: list[tuple[str, str]] = []
    for column in audit.get("columns_audited", []):
        for category in AUDIT_CATEGORY_ORDER:
            if audit.get("examples", {}).get(column, {}).get(category):
                pairs.append((column, category))
    return pairs


def status_label(status: str) -> str:
    """Etiqueta en español para un service_status canónico; los códigos
    desconocidos se mantienen sin cambios."""
    return STATUS_LABELS.get(status, status)


def readable_flags(flags: list[str]) -> str:
    """Códigos canónicos ``field=flag`` -> descripciones legibles en español.

    Los códigos no mapeados conservan su forma técnica; las listas vacías
    producen una cadena vacía. El orden sigue la entrada (ya determinista).
    """
    return ", ".join(FLAG_DESCRIPTIONS.get(flag, flag) for flag in flags)


def service_table_rows(combined: dict, day_type: str) -> list[dict]:
    """Filas de servicio planificado en español para el lector (tabla principal
    de la demo).

    Las claves de columna son los nombres de lector localizados (Línea,
    Empresa, Sentido, Origen, Destino, Inicio, Fin, Intervalo, Estado,
    Incidencias de calidad); las columnas de tiempo llevan los valores raw
    H:MM exactos y la columna de estado la etiqueta de estado en español. Aquí
    no se exponen claves/códigos canónicos.
    """
    rows: list[dict] = []
    for row in service_rows(combined, day_type):
        rows.append(
            {
                "Línea": row["line"],
                "Empresa": row["company"],
                "Sentido": row["direction"],
                "Origen": row["origin"],
                "Destino": row["destination"],
                "Inicio": row["start_raw"],
                "Fin": row["end_raw"],
                "Intervalo": row["headway_raw"],
                "Estado": status_label(row["status"]),
                "Incidencias de calidad": readable_flags(row["flags"]),
            }
        )
    return rows


def route_table_rows(combined: dict) -> list[dict]:
    """Filas de identidad de rutas en español para el lector, en la vista de
    calidad."""
    rows: list[dict] = []
    for row in route_rows(combined):
        rows.append(
            {
                "Línea": row["line"],
                "Empresa": row["company"],
                "Sentido": row["direction"],
                "Origen": row["origin"],
                "Destino": row["destination"],
                "Incidencias de calidad": readable_flags(row["flags"]),
            }
        )
    return rows


def no_service_window_table_rows(combined: dict) -> list[dict]:
    """Ventanas sin servicio en español para el lector, con las etiquetas de día
    localizadas."""
    from app._data import DAY_TYPE_LABELS

    return [
        {
            "Línea": window["route_line"],
            "Sentido": window["direction"],
            "Tipo de día": DAY_TYPE_LABELS.get(window["day_type"], window["day_type"]),
        }
        for window in no_service_window_rows(combined)
    ]


def technical_detail_rows(combined: dict, line: str, direction: str, day_type: str) -> list[dict] | None:
    """Detalles técnicos canónicos de la ventana seleccionada (expander
    técnico).

    Devuelve ``[{"campo", "valor"}, ...]`` con los nombres de campos raw y los
    códigos canónicos: ``service_status``, ``network_id``, ``service_id``,
    minutos tipados del día de servicio, valores raw H:MM, ``quality_flags``
    (códigos canónicos ``field=flag``) y la ``provenance`` aplanada. ``None``
    cuando ningún registro coincide con la selección (nunca se inventa).
    """
    window = selected_window(combined, line, direction, day_type)
    if window is None:
        return None
    details: list[dict] = [
        {"campo": "service_status", "valor": window["status"]},
        {"campo": "network_id", "valor": window["network_id"]},
        {"campo": "service_id", "valor": window["service_id"]},
        {"campo": "planned_start", "valor": window["start_minutes"]},
        {"campo": "planned_end", "valor": window["end_minutes"]},
        {"campo": "planned_headway", "valor": window["headway_minutes"]},
        {"campo": "planned_start_raw", "valor": window["start_raw"]},
        {"campo": "planned_end_raw", "valor": window["end_raw"]},
        {"campo": "planned_headway_raw", "valor": window["headway_raw"]},
        {"campo": "quality_flags", "valor": ", ".join(window["flags"])},
    ]
    provenance = window.get("provenance") or {}
    details.extend({"campo": f"provenance.{key}", "valor": value} for key, value in sorted(provenance.items()))
    return details


def provenance_rows(combined: dict) -> list[dict]:
    """Filas de evidencia de ambos snapshots de fuente (proyección de
    provenance)."""
    rows: list[dict] = []
    for snapshot in combined["source_snapshots"]:
        cutoff = snapshot.get("resource_cutoff") or {}
        rows.append(
            {
                "snapshot_id": snapshot.get("snapshot_id"),
                "dataset_id": snapshot.get("dataset_id"),
                "resource_id": snapshot.get("resource_id"),
                "resource_name": snapshot.get("resource_name"),
                "source_url": snapshot.get("source_url"),
                "raw_file": snapshot.get("raw_file"),
                "content_hash": snapshot.get("content_hash"),
                "collection_timestamp_utc": snapshot.get("collection_timestamp_utc"),
                "source_published_at": snapshot.get("source_published_at"),
                "license_declared": snapshot.get("license_declared"),
                "license_id": snapshot.get("license_id"),
                "license_url": snapshot.get("license_url"),
                "attribution": snapshot.get("attribution"),
                "retrieval_method": snapshot.get("retrieval_method"),
                "row_count": snapshot.get("row_count"),
                "status": snapshot.get("status"),
                "resource_created": cutoff.get("created"),
                "resource_last_modified": cutoff.get("last_modified"),
                "resource_metadata_modified": cutoff.get("metadata_modified"),
                "resource_description": cutoff.get("description"),
            }
        )
    return rows


__all__ = [
    "AUDIT_CATEGORY_ORDER",
    "CLEAN_ROWS_LABEL",
    "route_lines",
    "day_types",
    "service_rows",
    "route_rows",
    "selected_window",
    "no_service_window_rows",
    "route_quality_summary",
    "stops_quality_summary",
    "audit_example_rows",
    "audit_columns_with_examples",
    "provenance_rows",
    "status_label",
    "readable_flags",
    "service_table_rows",
    "route_table_rows",
    "no_service_window_table_rows",
    "technical_detail_rows",
]
