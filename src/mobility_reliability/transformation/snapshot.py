"""Implementación de la transformación canónica del servicio planificado.

Ver ``mobility_reliability.transformation`` para el contrato público y la
semántica documentada. Este módulo no lee nada más que el snapshot validado:
sin red, sin escrituras, sin clima/GTFS-RT/AVL, sin geometría de rutas, sin
dashboards.
"""

from __future__ import annotations

import re
from decimal import Decimal

from mobility_reliability.validation import SourceSnapshot, validate_source_snapshot

__all__ = [
    "KNOWN_EXPECTED_ROW_COUNTS",
    "SENTIDO_VALUES",
    "transform_captures",
    "transform_snapshot",
]

# Los dos IDs de recurso aprobados y sus conteos de filas observados. El
# conteo esperado es una verificación NO UNIVERSAL del reporte: solo se aplica
# cuando el resource_id del snapshot es uno de estos dos; los recursos
# desconocidos reportan null.
KNOWN_EXPECTED_ROW_COUNTS = {
    "e55af215-4648-4e3b-84c9-d7e929435008": 76,  # rutas 2025Marzo
    "ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e": 383,  # paradas 2025Abril
}

ROUTES_DATASET_ID = "rutas-de-transporte-publico"
STOPS_DATASET_ID = "paradas-de-transporte-publico"

ROUTES_IDENTITY_FIELDS = ("LINEA", "COMPANIA", "SENTIDO", "ORIGEN", "DESTINO")
ROUTES_NATURAL_KEY = ROUTES_IDENTITY_FIELDS
STOPS_NATURAL_KEY = ("N",)
SENTIDO_VALUES = ("IDA", "RETORNO")

# (day_type, columna de inicio, columna de fin, columna de intervalo)
DAY_TYPES = (
    ("weekday", "LUNES_VIERNES_INICIO", "LUNES_VIERNES_FIN", "LUNES_VIERNES_INTERVALO"),
    ("saturday", "SABADOS_INICIO", "SABADOS_FIN", "SABADOS_INTERVALO"),
    ("sunday", "DOMINGOS_INICIO", "DOMINGOS_FIN", "DOMINGOS_INTERVALO"),
)

# H:MM estricto: dígitos ASCII no negativos, exactamente dos dígitos de
# minutos 00-59; las horas pueden superar 24 (los valores relativos al día de
# servicio se conservan).
_HHMM_RE = re.compile(r"^(\d+):(\d{2})$", re.ASCII)
# Sintaxis decimal estricta de coordenadas: signo opcional, dígitos ASCII,
# como máximo un punto decimal. Los valores de tres decimales como
# "-2.895.956" son sintaxis inválida.
_COORDINATE_RE = re.compile(r"^-?\d+(?:\.\d+)?$", re.ASCII)

_LATITUDE_RANGE = (-90, 90)
_LONGITUDE_RANGE = (-180, 180)
_MINUTES_PER_DAY = 24 * 60


def _typed(value: object) -> str | None:
    """Cadena tipada con espacios recortados; el blanco se vuelve null."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _hhmm(value: object) -> int | None:
    """H:MM estricto -> minutos totales del día de servicio; malformado/vacío
    -> None.

    ``0:09`` -> 9; ``25:10`` -> 1510 (se conserva, nunca se convierte a
    calendario); ``24:00`` -> 1440; los valores estrictamente superiores a
    24:00 exceden un día de servicio y siguen siendo válidos. Los minutos
    deben ser exactamente dos dígitos 00-59.
    """
    if not isinstance(value, str):
        return None
    match = _HHMM_RE.fullmatch(value.strip())
    if match is None:
        return None
    hours = int(match.group(1))
    minutes = int(match.group(2))
    return hours * 60 + minutes


def _coordinate(value: object, bounds: tuple[int, int]) -> tuple[str, Decimal | None]:
    """Validación estricta de sintaxis + rango global de coordenadas.

    Devuelve ``("valid", Decimal)`` cuando el valor coincide con la sintaxis
    decimal estricta Y está dentro de ``bounds``; si no,
    ``("syntax_invalid" | "out_of_range", None)``. Sin heurísticas, sin
    separadores de miles, sin bounding box más allá del rango global, sin
    corregir valores raw.
    """
    if not isinstance(value, str):
        return "syntax_invalid", None
    text = value.strip()
    if _COORDINATE_RE.fullmatch(text) is None:
        return "syntax_invalid", None
    try:
        decimal = Decimal(text)
    except ArithmeticError:
        return "syntax_invalid", None
    low, high = bounds
    if not (Decimal(low) <= decimal <= Decimal(high)):
        return "out_of_range", None
    return "valid", decimal


def _flag(field: str, flag: str, value: object = None) -> dict:
    return {"field": field, "flag": flag, "value": value}


def _provenance(snapshot: SourceSnapshot) -> dict:
    return {
        "source_snapshot_id": snapshot.snapshot_id,
        "source_id": snapshot.source_id,
        "dataset_id": snapshot.dataset_id,
        "source_url": snapshot.source_url,
        "resource_id": snapshot.resource_id,
        "raw_file": snapshot.raw_file,
    }


# ---------------------------------------------------------------------------
# mobility_network
# ---------------------------------------------------------------------------


def _route_record(snapshot: SourceSnapshot, index: int, row: dict) -> dict:
    flags: list[dict] = []
    mapped: dict[str, str | None] = {}
    for field in ROUTES_IDENTITY_FIELDS:
        raw_value = row.get(field, "")
        mapped[field] = _typed(raw_value)
        if mapped[field] is None:
            flags.append(_flag(field, "missing", raw_value))
    # Los valores SENTIDO no vacíos y desconocidos se marcan 'unknown'
    # conservando el valor raw; el SENTIDO en blanco ya se marca como missing
    # arriba.
    if mapped["SENTIDO"] is not None and mapped["SENTIDO"] not in SENTIDO_VALUES:
        flags.append(_flag("SENTIDO", "unknown", row.get("SENTIDO", "")))
    return {
        "network_id": f"{snapshot.snapshot_id}::route:{index:05d}",
        "snapshot_id": snapshot.snapshot_id,
        "element_type": "route",
        "route_line": mapped["LINEA"],
        "company": mapped["COMPANIA"],
        "direction": mapped["SENTIDO"],
        "origin": mapped["ORIGEN"],
        "destination": mapped["DESTINO"],
        # Cada columna de entrada se conserva textualmente (nunca se
        # recorta ni reescribe).
        "raw": {key: row.get(key, "") for key in snapshot.header},
        "quality_flags": flags,
        "provenance": _provenance(snapshot),
    }


def _stop_record(snapshot: SourceSnapshot, index: int, row: dict) -> dict:
    flags: list[dict] = []
    raw_n, raw_name, raw_palette = (
        row.get("N", ""),
        row.get("Ubicacion", ""),
        row.get("Paleta", ""),
    )
    stop_id, stop_name, palette = _typed(raw_n), _typed(raw_name), _typed(raw_palette)
    for field, raw_value in (("N", raw_n), ("Ubicacion", raw_name), ("Paleta", raw_palette)):
        if _typed(raw_value) is None:
            flags.append(_flag(field, "missing", raw_value))

    lat_status, lat = _coordinate(row.get("Latitud", ""), _LATITUDE_RANGE)
    lon_status, lon = _coordinate(row.get("Longitud", ""), _LONGITUDE_RANGE)
    if lat_status != "valid":
        flags.append(_flag("Latitud", lat_status, row.get("Latitud", "")))
    if lon_status != "valid":
        flags.append(_flag("Longitud", lon_status, row.get("Longitud", "")))

    geometry = None
    if lat is not None and lon is not None:
        # La geometría es un punto solo cuando AMBAS coordenadas pasan.
        geometry = {"type": "Point", "coordinates": [float(lon), float(lat)]}
    return {
        "network_id": f"{snapshot.snapshot_id}::stop:{index:05d}",
        "snapshot_id": snapshot.snapshot_id,
        "element_type": "stop",
        "stop_id": stop_id,
        "stop_name": stop_name,
        "palette": palette,
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lon) if lon is not None else None,
        "geometry": geometry,
        "raw": {key: row.get(key, "") for key in snapshot.header},
        "quality_flags": flags,
        "provenance": _provenance(snapshot),
    }


# ---------------------------------------------------------------------------
# planned_service
# ---------------------------------------------------------------------------


def _service_records(
    snapshot: SourceSnapshot, index: int, row: dict, route_network_id: str
) -> list[dict]:
    route_line = _typed(row.get("LINEA", ""))
    direction = _typed(row.get("SENTIDO", ""))
    records: list[dict] = []
    for day_type, start_col, end_col, interval_col in DAY_TYPES:
        raw_start = row.get(start_col, "")
        raw_end = row.get(end_col, "")
        raw_headway = row.get(interval_col, "")
        start = _hhmm(raw_start)
        end = _hhmm(raw_end)
        headway = _hhmm(raw_headway)

        flags: list[dict] = []
        no_service = start == 0 and end == 0 and headway == 0
        if no_service:
            # Centinela exacto 0:00/0:00/0:00: los ceros tipados se conservan y
            # la ventana se marca no_service, nunca una ventana activa inválida.
            status = "no_service"
        else:
            status = "active"
            if start is None:
                status = "invalid"
                flags.append(_flag("planned_start", "malformed", raw_start))
            if end is None:
                status = "invalid"
                flags.append(_flag("planned_end", "malformed", raw_end))
            if headway is None:
                status = "invalid"
                flags.append(_flag("planned_headway", "malformed", raw_headway))
            elif headway <= 0:
                status = "invalid"
                flags.append(_flag("planned_headway", "zero_or_negative", raw_headway))
            if start is not None and end is not None and start >= end:
                status = "invalid"
                flags.append(_flag("planned_start", "chronology_invalid", raw_start))
                flags.append(_flag("planned_end", "chronology_invalid", raw_end))
                start = None
                end = None

        records.append(
            {
                "service_id": f"{route_network_id}:{day_type}",
                "snapshot_id": snapshot.snapshot_id,
                "network_id": route_network_id,
                "route_line": route_line,
                "direction": direction,
                "day_type": day_type,
                "planned_start": start,
                "planned_end": end,
                "planned_headway": headway,
                "planned_start_raw": raw_start,
                "planned_end_raw": raw_end,
                "planned_headway_raw": raw_headway,
                "service_status": status,
                # service_date nunca se inventa: la fuente no publica ninguno.
                "service_date": None,
                "snapshot_cutoff": {
                    "resource_name": snapshot.resource_name,
                    "resource_description": snapshot.resource_cutoff.get("description"),
                    "resource_created": snapshot.resource_cutoff.get("created"),
                    "resource_last_modified": snapshot.resource_cutoff.get("last_modified"),
                    "resource_metadata_modified": snapshot.resource_cutoff.get("metadata_modified"),
                },
                "quality_flags": flags,
                "provenance": _provenance(snapshot),
            }
        )
    return records


# ---------------------------------------------------------------------------
# reporte de calidad
# ---------------------------------------------------------------------------


def _duplicate_counts(rows: list[dict], natural_key_fields: tuple[str, ...]) -> dict:
    from collections import Counter

    full = Counter(tuple(row.values()) for row in rows)
    natural = Counter(tuple(row.get(field, "") for field in natural_key_fields) for row in rows)
    return {
        "full_row": {
            "duplicated_keys": sum(1 for count in full.values() if count > 1),
            "duplicate_rows": sum(count - 1 for count in full.values() if count > 1),
        },
        "natural_key": {
            "duplicated_keys": sum(1 for count in natural.values() if count > 1),
            "duplicate_rows": sum(count - 1 for count in natural.values() if count > 1),
            "key_fields": list(natural_key_fields),
        },
    }


def _quality_report(
    snapshot: SourceSnapshot, network_records: list[dict], service_records: list[dict]
) -> dict:
    rows = snapshot.rows
    is_routes = snapshot.dataset_id == ROUTES_DATASET_ID
    warnings = [f"manifest: {warning}" for warning in snapshot.warnings]
    errors: list[str] = []

    # Campos faltantes: celdas en blanco por columna (los blancos de horario
    # también cuentan como celdas de horario malformadas abajo).
    missing_fields: dict[str, int] = {}
    for field in snapshot.header:
        count = sum(1 for row in rows if _typed(row.get(field, "")) is None)
        if count:
            missing_fields[field] = count
    for field, count in missing_fields.items():
        warnings.append(f"{field} está en blanco en {count} filas")

    duplicates = (
        _duplicate_counts(rows, ROUTES_NATURAL_KEY) if is_routes else _duplicate_counts(rows, STOPS_NATURAL_KEY)
    )
    for kind, counts in (("full-row", duplicates["full_row"]), ("natural-key", duplicates["natural_key"])):
        if counts["duplicate_rows"]:
            warnings.append(
                f"{counts['duplicate_rows']} filas duplicadas {kind} en "
                f"{counts['duplicated_keys']} claves"
            )

    # SENTIDO (solo rutas). unknown_count cuenta las filas cuyo SENTIDO
    # recortado no es IDA/RETORNO (filas en blanco incluidas; el blanco además
    # se marca como missing en el registro).
    sentido: dict | None = None
    if is_routes:
        unknown = sum(1 for row in rows if _typed(row.get("SENTIDO", "")) not in SENTIDO_VALUES)
        sentido = {"allowed": list(SENTIDO_VALUES), "unknown_count": unknown}
        if unknown:
            warnings.append(f"{unknown} filas tienen un valor SENTIDO desconocido")

    # Coordenadas (solo paradas).
    coordinates: dict | None = None
    if not is_routes:
        lat_counts = {"syntax_invalid": 0, "out_of_range": 0, "valid": 0}
        lon_counts = {"syntax_invalid": 0, "out_of_range": 0, "valid": 0}
        both_valid = 0
        for row in rows:
            lat_status, _ = _coordinate(row.get("Latitud", ""), _LATITUDE_RANGE)
            lon_status, _ = _coordinate(row.get("Longitud", ""), _LONGITUDE_RANGE)
            lat_counts[lat_status] += 1
            lon_counts[lon_status] += 1
            if lat_status == "valid" and lon_status == "valid":
                both_valid += 1
        coordinates = {
            "latitude": lat_counts,
            "longitude": lon_counts,
            "rows_with_both_valid": both_valid,
            "valid_point_coverage": both_valid / len(rows) if rows else 0.0,
        }
        if lat_counts["syntax_invalid"] or lat_counts["out_of_range"]:
            warnings.append(
                f"latitude: {lat_counts['syntax_invalid']} valores con sintaxis "
                f"inválida y {lat_counts['out_of_range']} fuera de rango"
            )
        if lon_counts["syntax_invalid"] or lon_counts["out_of_range"]:
            warnings.append(
                f"longitude: {lon_counts['syntax_invalid']} valores con sintaxis "
                f"inválida y {lon_counts['out_of_range']} fuera de rango"
            )
        if both_valid == 0:
            warnings.append(
                f"ninguna fila de paradas tiene ambas coordenadas válidas "
                f"(cobertura de puntos válidos {both_valid}/{len(rows)})"
            )

    # Horario (solo rutas).
    schedule: dict | None = None
    no_service_windows: list[dict] = []
    if is_routes:
        schedule_cells = 0
        malformed_cells = 0
        over_24h_cells = 0
        for row in rows:
            for _, start_col, end_col, interval_col in DAY_TYPES:
                for column in (start_col, end_col, interval_col):
                    minutes = _hhmm(row.get(column, ""))
                    schedule_cells += 1
                    if minutes is None:
                        malformed_cells += 1
                    elif minutes > _MINUTES_PER_DAY:
                        over_24h_cells += 1
        invalid_windows = sum(1 for s in service_records if s["service_status"] == "invalid")
        no_service_records = [s for s in service_records if s["service_status"] == "no_service"]
        # Una celda de intervalo es inválida cuando está malformada o es
        # cero/negativa en una ventana que no es sin-servicio (los centinelas
        # 0:00 de sin-servicio siguen siendo válidos).
        interval_invalid = sum(
            1
            for s in service_records
            if s["service_status"] != "no_service"
            and (s["planned_headway"] is None or s["planned_headway"] <= 0)
        )
        schedule = {
            "cells_total": schedule_cells,
            "cells_malformed": malformed_cells,
            "cells_over_24h": over_24h_cells,
            "active_windows_total": len(service_records),
            "active_windows_invalid": invalid_windows,
            "interval_cells_total": len(service_records),
            "interval_cells_invalid": interval_invalid,
            "no_service_windows_count": len(no_service_records),
        }
        no_service_windows = [
            {
                "route_line": s["route_line"],
                "direction": s["direction"],
                "day_type": s["day_type"],
            }
            for s in no_service_records
        ]
        if malformed_cells:
            warnings.append(f"{malformed_cells} celdas de horario están malformadas")
        if over_24h_cells:
            warnings.append(
                f"{over_24h_cells} celdas de horario superan 24:00 "
                "(relativas al día de servicio)"
            )
        if invalid_windows:
            warnings.append(f"{invalid_windows} ventanas de horario activas son inválidas")
        if interval_invalid:
            warnings.append(f"{interval_invalid} celdas de intervalo son inválidas")

    # Cobertura: proporción de elementos sin incidencias de calidad. Las
    # ventanas sin servicio y los centinelas válidos nunca ensucian un
    # elemento.
    elements_clean = sum(1 for record in network_records if not record["quality_flags"])

    report = {
        "snapshot_id": snapshot.snapshot_id,
        "dataset_id": snapshot.dataset_id,
        "resource_id": snapshot.resource_id,
        "row_count": snapshot.row_count,
        # Verificación no universal: solo se aplica para los dos IDs de
        # recurso aprobados conocidos (rutas 76, paradas 383); null en caso
        # contrario.
        "expected_row_count": KNOWN_EXPECTED_ROW_COUNTS.get(snapshot.resource_id),
        "row_count_matches_expected": None,
        "missing_fields": missing_fields,
        "duplicates": duplicates,
        "sentido": sentido,
        "coordinates": coordinates,
        "schedule": schedule,
        "no_service_windows": no_service_windows,
        "coverage": {"elements_total": len(network_records), "elements_clean": elements_clean},
        "warnings": warnings,
        "errors": errors,
    }
    expected = report["expected_row_count"]
    if expected is not None:
        report["row_count_matches_expected"] = snapshot.row_count == expected
    return report


# ---------------------------------------------------------------------------
# puntos de entrada públicos
# ---------------------------------------------------------------------------


def transform_snapshot(manifest_path, raw_dir) -> dict:
    """Valida y transforma un snapshot capturado en entidades canónicas.

    La validación estructural se ejecuta primero: ``SnapshotValidationError``
    se propaga ante cualquier inconsistencia manifest/raw (fail closed).
    Devuelve un dict compatible con JSON con ``source_snapshot``,
    ``mobility_network``, ``planned_service`` (solo rutas; vacío para paradas)
    y ``quality_report``.
    """
    snapshot = validate_source_snapshot(manifest_path, raw_dir)
    if snapshot.dataset_id == ROUTES_DATASET_ID:
        network_records: list[dict] = []
        service_records: list[dict] = []
        for index, row in enumerate(snapshot.rows, start=1):
            record = _route_record(snapshot, index, row)
            network_records.append(record)
            service_records.extend(_service_records(snapshot, index, row, record["network_id"]))
    else:
        network_records = [
            _stop_record(snapshot, index, row)
            for index, row in enumerate(snapshot.rows, start=1)
        ]
        service_records = []
    return {
        "source_snapshot": snapshot.as_dict(),
        "mobility_network": network_records,
        "planned_service": service_records,
        "quality_report": _quality_report(snapshot, network_records, service_records),
    }


def transform_captures(route_manifest_path, stops_manifest_path, raw_dir) -> dict:
    """Transforma las dos capturas aprobadas y combina sus registros canónicos.

    Devuelve ``source_snapshots`` (ambas proyecciones), la ``mobility_network``
    combinada (rutas primero, luego paradas), los registros ``planned_service``
    de rutas (las paradas no tienen), los ``quality_reports`` por snapshot y
    los metadatos de ``transformation``. Sin clima, sin GTFS-RT/AVL, sin
    geometría de rutas, sin dashboards.
    """
    routes = transform_snapshot(route_manifest_path, raw_dir)
    stops = transform_snapshot(stops_manifest_path, raw_dir)
    return {
        "source_snapshots": [routes["source_snapshot"], stops["source_snapshot"]],
        "mobility_network": routes["mobility_network"] + stops["mobility_network"],
        "planned_service": routes["planned_service"],
        "quality_reports": [routes["quality_report"], stops["quality_report"]],
        "transformation": {
            "name": "canonical-planned-service-transformation",
            "schema_version": 1,
            "notes": (
                "Solo servicio planificado: rutas, paradas, ventanas e intervalos "
                "planificados. Sin clima, sin GTFS-Realtime/AVL, sin geometría de "
                "rutas, sin dashboards y sin afirmaciones de movilidad observada."
            ),
        },
    }
