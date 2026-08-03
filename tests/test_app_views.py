"""Pruebas de contrato de los helpers puros de datos/modelos de vista de la demo sin conexión.

API pública bajo prueba
-----------------------
- ``app._data.load_combined``, ``app._data.load_coordinate_audit``,
  ``app._data.format_service_minutes``, ``app._data.load_failure_message``,
  el cargador con modos ``load_demo_payload`` / ``load_synthetic_combined``
  / ``load_fixture_failure_message`` / ``SyntheticFixtureError`` y las
  constantes fijadas ``PLANNED_ONLY_BOUNDARY`` / ``NO_MAP_DECISION`` /
  ``SYNTHETIC_MODE_BANNER``.
- ``app._views`` modelos de vista puros: ``route_lines``, ``day_types``,
  ``service_rows``, ``selected_window``, ``no_service_window_rows``,
  ``route_quality_summary``, ``stops_quality_summary``,
  ``audit_example_rows``, ``provenance_rows``.

Semántica bajo prueba
---------------------
- La capa de la app nunca vuelve a implementar parsing: solo consume la
  salida canónica de ``transform_captures`` y el artefacto existente de
  auditoría del formato de coordenadas.
- La selección (línea + IDA/RETORNO + tipo de día) es un filtro determinista
  sobre los registros canónicos ``planned_service``; las representaciones
  active / no_service / invalid provienen directo de ``service_status``.
- La provenance de los registros canónicos se propaga a cada fila de vista.
- La vista de paradas reporta los conteos de coordenadas de la transformación,
  la decisión ``format_unresolved`` de la auditoría y ejemplos raw exactos —
  nunca coordenadas convertidas y nunca un mapa.
- Los manifests/raws ausentes fallan de forma estricta mediante
  ``SnapshotValidationError`` y la demo renderiza un cartel claro, nunca un
  traceback.
- Las pruebas de captura real (raws presentes) fijan los números observados:
  76 rutas, 68/76 limpias, 8 ventanas sin servicio, 383 paradas, 0 geometrías
  de punto válidas.

Los fixtures sintéticos raw/manifest se escriben con
``capture_fixtures.write_snapshot``; el fixture de demo versionado con forma
canónica ``data/demo/synthetic-combined.json`` se lee tal cual.
No ocurre ningún acceso a red.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from capture_fixtures import ROUTES_DATASET_ID, STOPS_DATASET_ID, write_snapshot
from mobility_reliability.transformation import transform_captures
from mobility_reliability.validation import SnapshotValidationError

ROUTES_RESOURCE_ID = "e55af215-4648-4e3b-84c9-d7e929435008"
STOPS_RESOURCE_ID = "ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e"

from app import _data as data  # noqa: E402
from app import _views as views  # noqa: E402

# Derivado de las filas capturadas (ver tests/test_transformation.py para la
# misma semántica): la línea 1 activa todos los tipos de día; la línea 12 tiene
# una ventana de >24:00 entre semana, una cronología inválida el sábado y un
# intervalo malformado el domingo; la línea 21 es el centinela sin servicio el
# sábado/domingo.
ROUTES_RAW = (
    "LINEA,COMPANIA,SENTIDO,ORIGEN,DESTINO,"
    "LUNES_VIERNES_INICIO,LUNES_VIERNES_FIN,LUNES_VIERNES_INTERVALO,"
    "SABADOS_INICIO,SABADOS_FIN,SABADOS_INTERVALO,"
    "DOMINGOS_INICIO,DOMINGOS_FIN,DOMINGOS_INTERVALO\n"
    "1,SIT,IDA,LIRIO,KENNEDY,5:50,21:15,0:09,5:50,20:30,0:12,6:00,20:00,0:15\n"
    "12,RICAURTESA,IDA,,PLATAFORMA ITINERANTE QUINTA CHICA,"
    "25:10,26:30,0:15,7:00,7:00,0:20,8:00,9:00,bad\n"
    "21,URBA10,IDA,TARQUI,VADO,5:40,19:40,0:30,0:00,0:00,0:00,0:00,0:00,0:00\n"
)

# Fixture de paradas: fila 5 valores de tres decimales (sintaxis inválida),
# fila 26 valores fuera de rango, fila 75 una longitud válida, fila 328 ambas
# válidas (la única fila del fixture con geometría de punto — ejercita el
# reporte honesto).
STOPS_RAW = (
    "N,Ubicacion,Latitud,Longitud,Paleta\n"
    "5,AV 10 DE AGOSTO INTERSECCION FEDERICO PROA?O,-2.910.397,-79.010.522,SI\n"
    "26,12 DE ABRIL 5-99 INTERSECCION AV SOLANO,-290.179,-790.064,NO\n"
    "75,CALLE PRESIDENTE CORDOVA INTERSECCION VARGAS MACHUCA,-2.900.025,-79.0,SI\n"
    "328,AV DE LAS AMERICAS,-2.855,-78.99,NO\n"
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_ROUTES_MANIFEST = (
    REPO_ROOT / "data/manifests/rutas-de-transporte-publico/2026-08-02T18-51-08Z.manifest.json"
)
REAL_STOPS_MANIFEST = (
    REPO_ROOT / "data/manifests/paradas-de-transporte-publico/2026-08-02T19-27-36Z.manifest.json"
)
REAL_RAW_DIR = REPO_ROOT / "data/raw"
REAL_AUDIT_JSON = REPO_ROOT / "data/quality/coordinate-format-audit.json"

REAL_RAWS_PRESENT = (
    (REAL_RAW_DIR / "rutas-de-transporte-publico/2026-08-02T18-51-08Z.json").is_file()
    and (REAL_RAW_DIR / "paradas-de-transporte-publico/2026-08-02T19-27-36Z.json").is_file()
)

REQUIRES_REAL_RAWS = pytest.mark.skipif(
    not REAL_RAWS_PRESENT,
    reason="las capturas raw aprobadas están en .gitignore y ausentes en este checkout",
)


def write_combined(tmp_path: Path) -> dict:
    """Escribe capturas sintéticas de rutas+paradas y devuelve transform_captures()."""
    _, routes_manifest, raw_dir = write_snapshot(
        tmp_path,
        dataset_id=ROUTES_DATASET_ID,
        raw_text=ROUTES_RAW,
        resource_id=ROUTES_RESOURCE_ID,
        resource_name="GADCuenca_RutasTransporte_2025Marzo.csv",
    )
    _, stops_manifest, _ = write_snapshot(
        tmp_path,
        dataset_id=STOPS_DATASET_ID,
        raw_text=STOPS_RAW,
        resource_id=STOPS_RESOURCE_ID,
        resource_name="GADCuenca_ParadasTransporte_2025Abril.csv",
    )
    return transform_captures(routes_manifest, stops_manifest, raw_dir)


def synthetic_audit() -> dict:
    """Un artefacto de auditoría mínimo con la forma de ``coordinate-format-audit.json``."""
    examples = [
        {"row": 1, "value": "-2.895.956"},
        {"row": 2, "value": "-2.908.987"},
        {"row": 3, "value": "-2.908.728"},
        {"row": 4, "value": "-2.907.012"},
        {"row": 5, "value": "-2.909.105"},
        {"row": 6, "value": "-2.907.489"},
        {"row": 7, "value": "-2.908.082"},
        {"row": 8, "value": "-2.905.351"},
    ]
    return {
        "decision": "format_unresolved",
        "format_resolved": False,
        "conversion_justified": False,
        "geometry_generated": False,
        "raw_sha256": "0" * 64,
        "row_count": 4,
        "columns_audited": ["Latitud", "Longitud"],
        "per_column_counts": {
            "Latitud": {"thousands_separator_candidate": 8},
            "Longitud": {"thousands_separator_candidate": 8},
        },
        "examples": {
            "Latitud": {"thousands_separator_candidate": list(examples)},
            "Longitud": {"thousands_separator_candidate": list(examples)},
        },
    }


# ---------------------------------------------------------------------------
# carga de datos y constantes fijadas
# ---------------------------------------------------------------------------


def test_load_combined_devuelve_ambos_snapshots(tmp_path):
    result = write_combined(tmp_path)
    assert len(result["source_snapshots"]) == 2
    assert {s["dataset_id"] for s in result["source_snapshots"]} == {
        ROUTES_DATASET_ID,
        STOPS_DATASET_ID,
    }
    assert len(result["mobility_network"]) == 7  # 3 routes + 4 stops
    assert len(result["planned_service"]) == 9  # 3 routes x 3 day types
    assert len(result["quality_reports"]) == 2


def test_load_combined_con_rutas_explicitas(tmp_path):
    """load_combined acepta rutas explícitas y usa por defecto las constantes del repo."""
    _, routes_manifest, raw_dir = write_snapshot(tmp_path, dataset_id=ROUTES_DATASET_ID)
    _, stops_manifest, _ = write_snapshot(tmp_path, dataset_id=STOPS_DATASET_ID)
    combined = data.load_combined(routes_manifest, stops_manifest, raw_dir)
    assert len(combined["source_snapshots"]) == 2
    assert combined["planned_service"][0]["provenance"]["source_snapshot_id"].startswith(
        "rutas-de-transporte-publico@"
    )


def test_manifest_ausente_lanza_error_y_el_mensaje_es_claro(tmp_path):
    missing = tmp_path / "missing" / "does-not-exist.manifest.json"
    with pytest.raises(SnapshotValidationError):
        data.load_combined(missing, missing, tmp_path / "raw")

    exc = SnapshotValidationError("no se encontró el archivo manifest: boom")
    message = data.load_failure_message(
        exc, route_manifest=str(missing), stops_manifest=str(missing), raw_dir=str(tmp_path / "raw")
    )
    assert "no pudo cargar" in message
    assert str(missing) in message
    assert "Traceback" not in message
    assert "raw" in message  # se conserva la identidad de la raíz raw


def test_load_coordinate_audit_degradacion_controlada(tmp_path):
    missing = tmp_path / "audit.json"
    assert data.load_coordinate_audit(missing) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert data.load_coordinate_audit(bad) is None
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"decision": "format_unresolved"}), encoding="utf-8")
    assert data.load_coordinate_audit(good) == {"decision": "format_unresolved"}


def test_format_service_minutes_solo_visualizacion():
    assert data.format_service_minutes(350) == "5:50"
    assert data.format_service_minutes(1510) == "25:10"
    assert data.format_service_minutes(0) == "0:00"
    assert data.format_service_minutes(None) is None


def test_constantes_fijadas():
    assert data.PLANNED_ONLY_BOUNDARY == (
        "Esta demo muestra únicamente servicio planificado.\n"
        "No representa puntualidad, retrasos, frecuencia observada,\n"
        "GTFS-Realtime, AVL ni cobertura geográfica."
    )
    assert data.NO_MAP_DECISION == (
        "No se muestra un mapa porque el formato de las coordenadas,\n"
        "el orden de los ejes y el sistema de referencia CRS no están resueltos."
    )
    assert data.DIRECTION_VALUES == ("IDA", "RETORNO")
    assert data.DAY_TYPE_LABELS == {
        "weekday": "Entre semana",
        "saturday": "Sábado",
        "sunday": "Domingo",
    }


# ---------------------------------------------------------------------------
# modelo de vista de servicio planificado: selección y representación de estado
# ---------------------------------------------------------------------------


def test_route_lines_y_day_types_deterministas(tmp_path):
    combined = write_combined(tmp_path)
    assert views.route_lines(combined) == ["1", "12", "21"]
    assert views.day_types(combined) == ["weekday", "saturday", "sunday"]
    # Determinista: las llamadas repetidas devuelven resultados idénticos.
    assert views.route_lines(combined) == views.route_lines(combined)


def test_service_rows_cubren_toda_fila_de_ruta_del_dia(tmp_path):
    combined = write_combined(tmp_path)
    rows = views.service_rows(combined, "weekday")
    assert [r["line"] for r in rows] == ["1", "12", "21"]
    assert all(r["direction"] == "IDA" for r in rows)
    first = rows[0]
    assert first["start_raw"] == "5:50"
    assert first["start_minutes"] == 350
    assert first["end_minutes"] == 1275
    assert first["headway_raw"] == "0:09"
    assert first["headway_minutes"] == 9
    assert first["status"] == "active"
    assert first["flags"] == []
    # Los minutos tipados Y el H:MM raw están ambos presentes (sin pérdida de información).
    assert rows[1]["start_minutes"] == 1510  # 25:10 preserved
    assert rows[1]["start_raw"] == "25:10"


def test_selected_window_activa_sin_servicio_e_invalida(tmp_path):
    combined = write_combined(tmp_path)

    active = views.selected_window(combined, "1", "IDA", "weekday")
    assert active["status"] == "active"
    assert active["start_raw"] == "5:50"
    assert active["end_raw"] == "21:15"
    assert active["headway_raw"] == "0:09"

    no_service = views.selected_window(combined, "21", "IDA", "saturday")
    assert no_service["status"] == "no_service"
    assert no_service["start_minutes"] == 0
    assert no_service["end_minutes"] == 0
    assert no_service["headway_minutes"] == 0
    assert no_service["start_raw"] == "0:00"
    assert no_service["flags"] == []

    invalid = views.selected_window(combined, "12", "IDA", "sunday")
    assert invalid["status"] == "invalid"
    assert invalid["headway_raw"] == "bad"
    assert invalid["headway_minutes"] is None
    assert "planned_headway=malformed" in invalid["flags"]

    # Filtrado por sentido: el fixture no tiene filas RETORNO.
    assert views.selected_window(combined, "21", "RETORNO", "weekday") is None


def test_route_rows_identidad_e_incidencias(tmp_path):
    combined = write_combined(tmp_path)
    rows = views.route_rows(combined)
    assert [r["line"] for r in rows] == ["1", "12", "21"]
    assert rows[0]["origin"] == "LIRIO"
    assert rows[1]["origin"] is None  # ORIGEN vacío tipado a null, marcado
    assert "ORIGEN=missing" in rows[1]["flags"]
    assert rows[2]["flags"] == []


def test_service_rows_combinan_identidad_de_ruta_e_incidencias_de_ventana(tmp_path):
    """Las incidencias de identidad (p. ej. ORIGEN ausente) viajan en cada fila de día de esa
    ruta, combinadas con las incidencias de la ventana del día, ordenadas de forma determinista."""
    combined = write_combined(tmp_path)
    weekday = {row["line"]: row for row in views.service_rows(combined, "weekday")}

    # La línea 12 tiene un ORIGEN vacío y una ventana activa de >24:00 entre semana.
    line12 = weekday["12"]
    assert line12["origin"] is None
    assert "ORIGEN=missing" in line12["flags"]
    assert line12["status"] == "active"  # la propia ventana permanece activa
    assert line12["start_minutes"] == 1510
    assert line12["start_raw"] == "25:10"  # se conservan los valores raw y tipados

    # La ventana seleccionada expone las mismas incidencias combinadas.
    selected = views.selected_window(combined, "12", "IDA", "weekday")
    assert selected is not None
    assert selected["flags"] == line12["flags"]
    assert "ORIGEN=missing" in selected["flags"]

    # Orden determinista: las incidencias de identidad y de ventana se ordenan juntas.
    sunday = views.selected_window(combined, "12", "IDA", "sunday")
    assert sunday is not None
    assert sunday["flags"] == ["ORIGEN=missing", "planned_headway=malformed"]

    # Las rutas sin incidencias siguen sin incidencias; la representación no_service no cambia.
    assert views.selected_window(combined, "1", "IDA", "weekday")["flags"] == []
    no_service = views.selected_window(combined, "21", "IDA", "saturday")
    assert no_service["flags"] == []
    assert no_service["status"] == "no_service"


def test_service_rows_llevan_la_incidencia_de_destino_ausente(tmp_path):
    """Un DESTINO vacío también se marca en las filas de servicio de la ruta."""
    from mobility_reliability.transformation import transform_snapshot

    raw = (
        "LINEA,COMPANIA,SENTIDO,ORIGEN,DESTINO,"
        "LUNES_VIERNES_INICIO,LUNES_VIERNES_FIN,LUNES_VIERNES_INTERVALO,"
        "SABADOS_INICIO,SABADOS_FIN,SABADOS_INTERVALO,"
        "DOMINGOS_INICIO,DOMINGOS_FIN,DOMINGOS_INTERVALO\n"
        "55,EMPRESA X,IDA,CENTRO,,6:00,18:00,0:10,6:00,18:00,0:10,6:00,18:00,0:10\n"
    )
    _, manifest, raw_dir = write_snapshot(
        tmp_path / "destino", dataset_id=ROUTES_DATASET_ID, raw_text=raw
    )
    result = transform_snapshot(manifest, raw_dir)
    combined = {
        "source_snapshots": [result["source_snapshot"]],
        "mobility_network": result["mobility_network"],
        "planned_service": result["planned_service"],
        "quality_reports": [result["quality_report"]],
    }

    row = views.selected_window(combined, "55", "IDA", "weekday")
    assert row is not None
    assert row["destination"] is None
    assert "DESTINO=missing" in row["flags"]
    assert row["status"] == "active"
    assert row["start_raw"] == "6:00"


def test_service_rows_con_registro_ausente_conservan_incidencias_de_ruta(tmp_path):
    """El camino defensivo de registro ausente devuelve status 'missing' con las incidencias
    de identidad de la ruta en lugar de lanzar (sin AttributeError)."""
    combined = write_combined(tmp_path)
    # Se quita el registro de la línea 12 entre semana para ejercitar el fallback a través
    # de service_rows (los datos canónicos siempre tienen el registro; es defensivo).
    combined["planned_service"] = [
        record
        for record in combined["planned_service"]
        if not (record["route_line"] == "12" and record["day_type"] == "weekday")
    ]
    rows = {row["line"]: row for row in views.service_rows(combined, "weekday")}

    missing = rows["12"]
    assert missing["status"] == "missing"
    assert "ORIGEN=missing" in missing["flags"]  # route identity flags kept
    assert missing["start_minutes"] is None
    assert missing["headway_raw"] is None
    # Las filas no afectadas conservan su representación canónica.
    assert rows["1"]["status"] == "active"
    assert rows["21"]["status"] == "active"


# ---------------------------------------------------------------------------
# modelos de vista en español para el lector (UI localizada, datos canónicos sin cambios)
# ---------------------------------------------------------------------------


def test_service_table_rows_columnas_de_lector_en_espanol(tmp_path):
    combined = write_combined(tmp_path)
    rows = views.service_table_rows(combined, "weekday")
    assert [row["Línea"] for row in rows] == ["1", "12", "21"]
    assert list(rows[0]) == [
        "Línea",
        "Empresa",
        "Sentido",
        "Origen",
        "Destino",
        "Inicio",
        "Fin",
        "Intervalo",
        "Estado",
        "Incidencias de calidad",
    ]
    first = rows[0]
    # Los valores raw H:MM se conservan en las columnas del lector.
    assert first["Inicio"] == "5:50"
    assert first["Fin"] == "21:15"
    assert first["Intervalo"] == "0:09"
    assert first["Empresa"] == "SIT"
    assert first["Estado"] == "Activo"
    assert first["Incidencias de calidad"] == ""
    # La tabla principal nunca expone claves/códigos canónicos.
    serialized = json.dumps(rows)
    for key in ("start_raw", "planned_start", "service_status", "network_id", "service_id"):
        assert key not in serialized


def test_service_table_rows_estados_e_incidencias_en_espanol(tmp_path):
    combined = write_combined(tmp_path)
    sunday = {row["Línea"]: row for row in views.service_table_rows(combined, "sunday")}
    assert sunday["1"]["Estado"] == "Activo"
    assert sunday["12"]["Estado"] == "Inválido"
    assert "Origen sin valor" in sunday["12"]["Incidencias de calidad"]
    assert "Intervalo planificado malformado" in sunday["12"]["Incidencias de calidad"]

    saturday = {row["Línea"]: row for row in views.service_table_rows(combined, "saturday")}
    assert saturday["21"]["Estado"] == "Sin servicio"
    assert saturday["21"]["Inicio"] == "0:00"
    assert saturday["21"]["Fin"] == "0:00"
    assert saturday["21"]["Intervalo"] == "0:00"
    assert saturday["21"]["Incidencias de calidad"] == ""


def test_status_label_mapeo_y_fallback():
    assert views.status_label("active") == "Activo"
    assert views.status_label("no_service") == "Sin servicio"
    assert views.status_label("invalid") == "Inválido"
    assert views.status_label("missing") == "Sin registro"
    assert views.status_label("other_code") == "other_code"  # unknown stays canonical


def test_technical_detail_rows_muestran_codigos_canonicos(tmp_path):
    combined = write_combined(tmp_path)
    details = views.technical_detail_rows(combined, "21", "IDA", "saturday")
    assert details is not None
    values = {detail["campo"]: detail["valor"] for detail in details}
    assert values["service_status"] == "no_service"
    assert values["planned_start"] == 0
    assert values["planned_end"] == 0
    assert values["planned_headway"] == 0
    assert values["planned_start_raw"] == "0:00"
    assert values["planned_end_raw"] == "0:00"
    assert values["planned_headway_raw"] == "0:00"
    assert values["quality_flags"] == ""
    assert values["service_id"].endswith(":saturday")
    assert values["network_id"].endswith("::route:00003")
    assert values["provenance.source_snapshot_id"].startswith("rutas-de-transporte-publico@")
    assert values["provenance.resource_id"] == ROUTES_RESOURCE_ID
    # La ventana del domingo de la línea 12 lleva sus incidencias técnicas como códigos canónicos.
    invalid = views.technical_detail_rows(combined, "12", "IDA", "sunday")
    values_invalid = {detail["campo"]: detail["valor"] for detail in invalid}
    assert values_invalid["service_status"] == "invalid"
    assert values_invalid["quality_flags"] == "ORIGEN=missing, planned_headway=malformed"
    # Sin registro para la selección -> None (nunca se inventa).
    assert views.technical_detail_rows(combined, "21", "RETORNO", "weekday") is None


def test_no_service_window_table_rows_en_espanol(tmp_path):
    combined = write_combined(tmp_path)
    rows = views.no_service_window_table_rows(combined)
    assert rows == [
        {"Línea": "21", "Sentido": "IDA", "Tipo de día": "Sábado"},
        {"Línea": "21", "Sentido": "IDA", "Tipo de día": "Domingo"},
    ]


def test_route_table_rows_en_espanol(tmp_path):
    combined = write_combined(tmp_path)
    rows = views.route_table_rows(combined)
    assert list(rows[0]) == [
        "Línea",
        "Empresa",
        "Sentido",
        "Origen",
        "Destino",
        "Incidencias de calidad",
    ]
    assert rows[1]["Origen"] is None
    assert "Origen sin valor" in rows[1]["Incidencias de calidad"]
    assert rows[2]["Incidencias de calidad"] == ""


def test_no_service_window_rows_del_reporte_de_calidad(tmp_path):
    combined = write_combined(tmp_path)
    assert views.no_service_window_rows(combined) == [
        {"route_line": "21", "direction": "IDA", "day_type": "saturday"},
        {"route_line": "21", "direction": "IDA", "day_type": "sunday"},
    ]


def test_service_rows_propagan_la_provenance(tmp_path):
    combined = write_combined(tmp_path)
    for row in views.service_rows(combined, "weekday"):
        provenance = row["provenance"]
        assert provenance["source_snapshot_id"] == "rutas-de-transporte-publico@2026-08-02T18-51-08Z"
        assert provenance["resource_id"] == ROUTES_RESOURCE_ID
        assert provenance["dataset_id"] == ROUTES_DATASET_ID
        assert provenance["raw_file"].startswith("rutas-de-transporte-publico/")


# ---------------------------------------------------------------------------
# modelo de vista de calidad de rutas
# ---------------------------------------------------------------------------


def test_route_quality_summary_deriva_conteos_de_la_transformacion(tmp_path):
    combined = write_combined(tmp_path)
    summary = views.route_quality_summary(combined)
    assert summary["row_count"] == 3
    assert summary["missing_origen"] == 1
    assert summary["missing_destino"] == 0  # la fixture deja vacío únicamente ORIGEN
    assert summary["sense_counts"] == {"IDA": 3, "RETORNO": 0}
    assert summary["schedule_cells"] == 27
    assert summary["schedule_cells_malformed"] == 1
    assert summary["interval_cells"] == 9
    assert summary["interval_cells_invalid"] == 1
    assert summary["no_service_windows_count"] == 2
    assert summary["elements_total"] == 3
    assert summary["elements_clean"] == 2
    # La proporción estilo 68/76 se etiqueta SOLO como filas limpias del snapshot validado.
    assert summary["clean_label"] == "filas limpias del snapshot validado"
    assert summary["clean_label"] != "cobertura geográfica"


# ---------------------------------------------------------------------------
# modelo de vista de calidad de paradas: coordenadas sin resolver, sin mapa, sin conversión
# ---------------------------------------------------------------------------


def test_stops_quality_summary_reporta_conteos_y_decision_de_auditoria(tmp_path):
    combined = write_combined(tmp_path)
    summary = views.stops_quality_summary(combined, synthetic_audit())
    assert summary["row_count"] == 4
    assert summary["latitude"] == {"syntax_invalid": 2, "out_of_range": 1, "valid": 1}
    assert summary["longitude"] == {"syntax_invalid": 1, "out_of_range": 1, "valid": 2}
    assert summary["rows_with_both_valid"] == 1
    assert summary["geometry_rows"] == 1  # honesto: el fixture tiene una fila con ambas válidas
    assert summary["valid_point_coverage"] == 0.25
    assert summary["audit_decision"] == "format_unresolved"
    assert summary["audit_format_resolved"] is False
    assert summary["audit_conversion_justified"] is False
    assert summary["audit_geometry_generated"] is False


def test_stops_quality_summary_sin_artefacto_de_auditoria(tmp_path):
    combined = write_combined(tmp_path)
    summary = views.stops_quality_summary(combined, None)
    assert summary["audit_decision"] is None
    assert summary["row_count"] == 4  # los conteos de la transformación siguen disponibles


def test_audit_example_rows_limitados_con_valores_raw_exactos():
    audit = synthetic_audit()
    result = views.audit_example_rows(audit, "Latitud", "thousands_separator_candidate", cap=5)
    assert result["total"] == 8
    assert len(result["rows"]) == 5
    assert result["rows"][0] == {"row": 1, "value": "-2.895.956"}
    # Las cadenas raw exactas pasan intactas — nunca se convierten.
    assert all(isinstance(row["value"], str) for row in result["rows"])
    assert "-2.895.956" in {row["value"] for row in result["rows"]}


def test_sin_conversion_heuristica_en_el_modelo_de_vista(tmp_path):
    """La capa de vista expone solo cadenas raw y conteos — sin coordenadas convertidas y sin parser."""
    combined = write_combined(tmp_path)
    audit = synthetic_audit()
    summary = views.stops_quality_summary(combined, audit)
    # El resumen no lleva valores de coordenadas analizados/convertidos.
    serialized = json.dumps(summary)
    assert "-2.895956" not in serialized
    assert "-2.855" not in serialized
    assert audit["conversion_justified"] is False
    assert audit["geometry_generated"] is False


# ---------------------------------------------------------------------------
# modelo de vista de provenance
# ---------------------------------------------------------------------------


def test_provenance_rows_cubren_ambos_snapshots(tmp_path):
    combined = write_combined(tmp_path)
    rows = views.provenance_rows(combined)
    assert [r["dataset_id"] for r in rows] == [ROUTES_DATASET_ID, STOPS_DATASET_ID]
    for row in rows:
        for key in (
            "snapshot_id",
            "resource_id",
            "resource_name",
            "raw_file",
            "content_hash",
            "collection_timestamp_utc",
            "source_published_at",
            "license_declared",
            "license_id",
            "license_url",
            "attribution",
            "retrieval_method",
            "row_count",
            "source_url",
            "resource_created",
            "resource_last_modified",
            "resource_metadata_modified",
            "resource_description",
            "status",
        ):
            assert key in row
        assert row["license_id"] == "cc-nc"
        assert row["license_url"].startswith("http://creativecommons.org/licenses/by-nc/2.0")


# ---------------------------------------------------------------------------
# triangulación contra los raw capturados reales (se omite si faltan los raw ignorados por git)
# ---------------------------------------------------------------------------


@REQUIRES_REAL_RAWS
def test_numeros_de_calidad_reales_de_rutas_fijados():
    combined = data.load_combined(REAL_ROUTES_MANIFEST, REAL_STOPS_MANIFEST, REAL_RAW_DIR)
    summary = views.route_quality_summary(combined)
    assert summary["row_count"] == 76
    assert summary["missing_origen"] == 4
    assert summary["missing_destino"] == 4
    assert summary["sense_counts"] == {"IDA": 38, "RETORNO": 38}
    assert summary["schedule_cells"] == 684
    assert summary["schedule_cells_malformed"] == 0
    assert summary["interval_cells"] == 228
    assert summary["interval_cells_invalid"] == 0
    assert summary["no_service_windows_count"] == 8
    assert summary["elements_total"] == 76
    assert summary["elements_clean"] == 68
    assert len(views.service_rows(combined, "weekday")) == 76


@REQUIRES_REAL_RAWS
def test_calidad_real_de_paradas_y_sin_geometria():
    combined = data.load_combined(REAL_ROUTES_MANIFEST, REAL_STOPS_MANIFEST, REAL_RAW_DIR)
    audit = data.load_coordinate_audit(REAL_AUDIT_JSON)
    assert audit is not None
    summary = views.stops_quality_summary(combined, audit)
    assert summary["row_count"] == 383
    assert summary["latitude"] == {"syntax_invalid": 331, "out_of_range": 48, "valid": 4}
    assert summary["longitude"] == {"syntax_invalid": 374, "out_of_range": 4, "valid": 5}
    assert summary["rows_with_both_valid"] == 0
    assert summary["geometry_rows"] == 0
    assert summary["valid_point_coverage"] == 0.0
    assert summary["audit_decision"] == "format_unresolved"
    assert summary["audit_conversion_justified"] is False
    assert summary["audit_geometry_generated"] is False


@REQUIRES_REAL_RAWS
def test_seleccion_real_sin_servicio_y_ventanas_activas():
    combined = data.load_combined(REAL_ROUTES_MANIFEST, REAL_STOPS_MANIFEST, REAL_RAW_DIR)
    no_service = views.selected_window(combined, "21", "IDA", "saturday")
    assert no_service["status"] == "no_service"
    assert no_service["start_raw"] == "0:00"
    active = views.selected_window(combined, "1", "IDA", "weekday")
    assert active["status"] == "active"
    assert active["start_raw"] == "5:50"


def test_el_artefacto_real_de_auditoria_esta_sin_resolver():
    """El artefacto de auditoría versionado fija la decisión de no-mapa en todas partes."""
    audit = data.load_coordinate_audit(REAL_AUDIT_JSON)
    assert audit is not None
    assert audit["decision"] == "format_unresolved"
    assert audit["format_resolved"] is False
    assert audit["conversion_justified"] is False
    assert audit["geometry_generated"] is False
    assert audit["raw_sha256"] == "20969d2e6dbc4d91338901f88c2805afaf642b757adfa4be97225c7364bdc62c"
    assert audit["row_count"] == 383
    for column in audit["columns_audited"]:
        for category, examples in audit["examples"][column].items():
            assert len(examples) <= 20
            for example in examples:
                assert isinstance(example["value"], str)


@REQUIRES_REAL_RAWS
def test_hashes_reales_de_provenance_fijados():
    combined = data.load_combined(REAL_ROUTES_MANIFEST, REAL_STOPS_MANIFEST, REAL_RAW_DIR)
    rows = {r["dataset_id"]: r for r in views.provenance_rows(combined)}
    assert rows[ROUTES_DATASET_ID]["content_hash"] == (
        "dc3082ad1312e7f9c7127fef316b4b70d8b452dcd94025d471f0b417f88ee07a"
    )
    assert rows[STOPS_DATASET_ID]["content_hash"] == (
        "20969d2e6dbc4d91338901f88c2805afaf642b757adfa4be97225c7364bdc62c"
    )
    assert rows[STOPS_DATASET_ID]["snapshot_id"] == "paradas-de-transporte-publico@2026-08-02T19-27-36Z"


# ---------------------------------------------------------------------------
# cargador de la demo con modos: camino real estricto vs fixture sintético versionado
# ---------------------------------------------------------------------------

SYNTHETIC_STOPS_HASH = (
    "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
)


def test_load_demo_payload_modo_real_con_fixtures_capturados(tmp_path):
    """Ambos archivos raw aprobados presentes -> camino real estricto, nunca el fixture."""
    _, routes_manifest, raw_dir = write_snapshot(tmp_path, dataset_id=ROUTES_DATASET_ID)
    _, stops_manifest, _ = write_snapshot(tmp_path, dataset_id=STOPS_DATASET_ID)
    payload = data.load_demo_payload(routes_manifest, stops_manifest, raw_dir)
    assert payload["mode"] == data.DATA_MODE_REAL
    combined = payload["combined"]
    assert len(combined["source_snapshots"]) == 2
    assert combined["quality_reports"][0]["row_count"] == 2  # fixture de dos filas
    # El modo real conserva el artefacto de auditoría de coordenadas versionado (nunca sintético).
    assert payload["audit"]["decision"] == "format_unresolved"
    assert payload["audit"]["raw_sha256"] != SYNTHETIC_STOPS_HASH


def test_load_demo_payload_modo_sintetico_sin_raws(tmp_path):
    """Ningún archivo raw aprobado -> fixture sintético versionado + auditoría sintética."""
    payload = data.load_demo_payload(raw_dir=tmp_path / "no-raw-root")
    assert payload["mode"] == data.DATA_MODE_SYNTHETIC
    combined = payload["combined"]
    assert data.SYNTHETIC_COMBINED_JSON.is_file()  # el fixture versionado está presente
    assert views.route_lines(combined) == ["DEMO-01", "DEMO-02", "DEMO-03"]
    assert views.day_types(combined) == ["weekday", "saturday", "sunday"]
    # El payload sintético de auditoría es format_unresolved con un hash ficticio
    # (nunca el hash real de paradas).
    audit = payload["audit"]
    assert audit["decision"] == "format_unresolved"
    assert audit["format_resolved"] is False
    assert audit["raw_sha256"] == SYNTHETIC_STOPS_HASH
    assert audit["raw_sha256"] != (
        "20969d2e6dbc4d91338901f88c2805afaf642b757adfa4be97225c7364bdc62c"
    )


def test_load_demo_payload_fixture_sintetico_cubre_el_contrato(tmp_path):
    """El fixture cubre los tres tipos de día, un servicio activo, un centinela exacto sin
    servicio y ninguna geometría de parada (texto de coordenadas sin resolver)."""
    payload = data.load_demo_payload(raw_dir=tmp_path / "no-raw-root")
    combined = payload["combined"]
    day_types = {record["day_type"] for record in combined["planned_service"]}
    assert day_types == {"weekday", "saturday", "sunday"}
    statuses = {record["service_status"] for record in combined["planned_service"]}
    assert "active" in statuses and "no_service" in statuses
    # Los casos sin servicio son el centinela exacto 0:00/0:00/0:00.
    no_service = [
        record
        for record in combined["planned_service"]
        if record["service_status"] == "no_service"
    ]
    assert len(no_service) == 3
    assert all(
        (
            record["planned_start_raw"],
            record["planned_end_raw"],
            record["planned_headway_raw"],
        )
        == ("0:00", "0:00", "0:00")
        for record in no_service
    )
    stops = [r for r in combined["mobility_network"] if r["element_type"] == "stop"]
    assert len(stops) == 4
    assert all(record["geometry"] is None for record in stops)
    assert all(record["latitude"] is None and record["longitude"] is None for record in stops)
    assert combined["quality_reports"][1]["coordinates"]["rows_with_both_valid"] == 0
    assert combined["quality_reports"][1]["coordinates"]["valid_point_coverage"] == 0.0


def test_load_demo_payload_integridad_del_join_sintetico(tmp_path):
    """Cada registro planned_service une un registro de ruta por network_id."""
    payload = data.load_demo_payload(raw_dir=tmp_path / "no-raw-root")
    combined = payload["combined"]
    route_ids = {
        record["network_id"]
        for record in combined["mobility_network"]
        if record["element_type"] == "route"
    }
    assert {record["network_id"] for record in combined["planned_service"]} == route_ids


def test_fixture_sintetico_con_forma_canonica_y_sin_evidencia_oficial():
    """El fixture versionado está marcado como synthetic, tiene forma canónica y está libre de
    hashes/IDs de resource/URLs/afirmaciones de licencia/sellos de captura oficiales."""
    loaded = json.loads(data.SYNTHETIC_COMBINED_JSON.read_text(encoding="utf-8"))
    text = json.dumps(loaded)
    for official in (
        "dc3082ad",
        "20969d2e",
        "e55af215",
        "ed2f1b0f",
        "cuencaendatos",
        "creativecommons",
        "CC BY-NC",
        "GAD Municipal",
        "2026-08-02T18-51-08Z",
        "2026-08-02T19-27-36Z",
    ):
        assert official not in text
    assert loaded["fixture"]["synthetic"] is True
    assert loaded["coordinate_audit"]["decision"] == "format_unresolved"
    assert loaded["transformation"]["name"] == "synthetic-demo-fixture"


def test_load_demo_payload_raw_parcial_falla_de_forma_estricta(tmp_path):
    """Exactamente un raw aprobado -> fail closed; el fixture nunca se usa."""
    raw_dir = tmp_path / "raw"
    routes_raw = raw_dir / data.ROUTES_RAW_FILE
    routes_raw.parent.mkdir(parents=True)
    routes_raw.write_text("dummy", encoding="utf-8")
    with pytest.raises(SnapshotValidationError, match="evidencia parcial"):
        data.load_demo_payload(raw_dir=raw_dir)


def test_load_demo_payload_raw_real_corrupto_no_recurre_al_fixture(tmp_path):
    """Ambos raw presentes pero evidencia real inválida -> el fallo estricto se propaga;
    el fixture sintético nunca se usa."""
    routes_raw_path, routes_manifest, raw_dir = write_snapshot(
        tmp_path, dataset_id=ROUTES_DATASET_ID
    )
    _, stops_manifest, _ = write_snapshot(tmp_path, dataset_id=STOPS_DATASET_ID)
    routes_raw_path.write_bytes(b"corrupted bytes")  # el content_hash ya no coincide
    with pytest.raises(SnapshotValidationError, match="content_hash"):
        data.load_demo_payload(routes_manifest, stops_manifest, raw_dir)


def test_load_demo_payload_fixture_ausente_falla_de_forma_estricta(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "SYNTHETIC_COMBINED_JSON", tmp_path / "missing.json")
    with pytest.raises(data.SyntheticFixtureError, match="no se encontró"):
        data.load_demo_payload(raw_dir=tmp_path / "no-raw-root")


def test_load_demo_payload_fixture_malformado_falla_de_forma_estricta(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(data, "SYNTHETIC_COMBINED_JSON", bad)
    with pytest.raises(data.SyntheticFixtureError, match="JSON legible"):
        data.load_demo_payload(raw_dir=tmp_path / "no-raw-root")


def test_load_demo_payload_fixture_con_forma_invalida_falla_de_forma_estricta(tmp_path, monkeypatch):
    """Un fixture estructuralmente incompleto falla de forma estricta con los problemas nombrados."""
    fixture = json.loads(data.SYNTHETIC_COMBINED_JSON.read_text(encoding="utf-8"))
    del fixture["planned_service"]
    invalid = tmp_path / "shape-invalid.json"
    invalid.write_text(json.dumps(fixture), encoding="utf-8")
    monkeypatch.setattr(data, "SYNTHETIC_COMBINED_JSON", invalid)
    with pytest.raises(data.SyntheticFixtureError, match="planned_service"):
        data.load_demo_payload(raw_dir=tmp_path / "no-raw-root")


def test_load_fixture_failure_message_claro(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "SYNTHETIC_COMBINED_JSON", tmp_path / "missing.json")
    exc = data.SyntheticFixtureError("no se encontró el fixture sintético de demostración: boom")
    message = data.load_fixture_failure_message(exc)
    assert "no pudo cargar" in message
    assert "sintético" in message
    assert "Traceback" not in message
