"""Triangulación de la transformación canónica contra los raws capturados reales.

Estas pruebas leen las capturas aprobadas exactas bajo ``data/`` (los manifests
están versionados; los bytes raw viven en el ``data/raw/`` ignorado por git). Se
OMITEN cuando los archivos raw están ausentes (p. ej. en un checkout fresco) y,
en caso contrario, fijan las métricas de calidad observadas de los dos
snapshots aprobados para que cualquier deriva futura del parseo sea detectada.
No ocurre ninguna captura ni acceso a red: la validación y la transformación
son totalmente offline.

Verdad de tierra observada (verificada contra los bytes raw, capturas 2026-08-02):
- Rutas: 76 filas, 14 columnas, ORIGEN en blanco en 4 filas, DESTINO en blanco
  en las mismas 4 filas, SENTIDO IDA 38 / RETORNO 38, 0 celdas de horario
  malformadas, 0 ventanas activas inválidas, 8 ventanas sin servicio (líneas 21
  y 23, ambos sentidos, Sábado y Domingo), 0 celdas por encima de 24:00,
  0 duplicados.
- Paradas: 383 filas, todos los campos no vacíos, 0 duplicados; latitud
  syntax-invalid 331 / out-of-range 48 / valid 4; longitud syntax-invalid
  374 / out-of-range 4 / valid 5; 0 filas con ambas coordenadas válidas; el '?'
  ASCII literal aparece en 5 valores de Ubicacion (filas 5, 6, 46, 47, 115).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mobility_reliability.transformation import transform_captures, transform_snapshot

REPO_ROOT = Path(__file__).resolve().parents[1]

ROUTES_MANIFEST = REPO_ROOT / "data/manifests/rutas-de-transporte-publico/2026-08-02T18-51-08Z.manifest.json"
ROUTES_RAW = REPO_ROOT / "data/raw/rutas-de-transporte-publico/2026-08-02T18-51-08Z.json"
STOPS_MANIFEST = REPO_ROOT / "data/manifests/paradas-de-transporte-publico/2026-08-02T19-27-36Z.manifest.json"
STOPS_RAW = REPO_ROOT / "data/raw/paradas-de-transporte-publico/2026-08-02T19-27-36Z.json"
RAW_DIR = REPO_ROOT / "data/raw"

REQUIRE_RAWS = ROUTES_RAW.is_file() and STOPS_RAW.is_file()

pytestmark = pytest.mark.skipif(
    not REQUIRE_RAWS,
    reason="las capturas raw aprobadas están en git-ignored y ausentes en este checkout",
)


def test_metricas_del_snapshot_de_rutas_sobre_el_raw_capturado():
    result = transform_snapshot(ROUTES_MANIFEST, RAW_DIR)

    network = result["mobility_network"]
    assert len(network) == 76
    assert all(r["element_type"] == "route" for r in network)
    assert [r["route_line"] for r in network].count("21") == 2
    assert [r["route_line"] for r in network].count("23") == 2

    services = result["planned_service"]
    assert len(services) == 76 * 3
    report = result["quality_report"]
    assert report["row_count"] == 76
    assert report["expected_row_count"] == 76
    assert report["row_count_matches_expected"] is True
    assert report["missing_fields"] == {"ORIGEN": 4, "DESTINO": 4}
    assert report["sentido"]["unknown_count"] == 0
    assert report["duplicates"]["full_row"]["duplicate_rows"] == 0
    assert report["duplicates"]["natural_key"]["duplicate_rows"] == 0
    assert report["schedule"]["cells_total"] == 684
    assert report["schedule"]["cells_malformed"] == 0
    assert report["schedule"]["cells_over_24h"] == 0
    assert report["schedule"]["interval_cells_total"] == 228
    assert report["schedule"]["interval_cells_invalid"] == 0
    assert report["schedule"]["active_windows_total"] == 228
    assert report["schedule"]["active_windows_invalid"] == 0
    assert report["schedule"]["no_service_windows_count"] == 8
    # Las 8 ventanas sin servicio son las líneas 21 y 23, ambos sentidos,
    # Sábado y Domingo.
    windows = {(w["route_line"], w["direction"], w["day_type"]) for w in report["no_service_windows"]}
    assert windows == {
        ("21", "IDA", "saturday"),
        ("21", "IDA", "sunday"),
        ("21", "RETORNO", "saturday"),
        ("21", "RETORNO", "sunday"),
        ("23", "IDA", "saturday"),
        ("23", "IDA", "sunday"),
        ("23", "RETORNO", "saturday"),
        ("23", "RETORNO", "sunday"),
    }
    # Las ventanas sin servicio no son ventanas activas inválidas.
    assert report["schedule"]["active_windows_invalid"] == 0
    # Filas con flags de campos de identidad: las 4 filas con ORIGEN/DESTINO en blanco.
    assert report["coverage"] == {"elements_total": 76, "elements_clean": 68}
    assert report["errors"] == []


def test_metricas_del_snapshot_de_paradas_sobre_el_raw_capturado():
    result = transform_snapshot(STOPS_MANIFEST, RAW_DIR)

    network = result["mobility_network"]
    assert len(network) == 383
    assert all(r["element_type"] == "stop" for r in network)
    report = result["quality_report"]
    assert report["row_count"] == 383
    assert report["expected_row_count"] == 383
    assert report["row_count_matches_expected"] is True
    assert report["missing_fields"] == {}
    assert report["duplicates"]["full_row"]["duplicate_rows"] == 0
    assert report["duplicates"]["natural_key"]["duplicate_rows"] == 0
    coords = report["coordinates"]
    assert coords["latitude"] == {"syntax_invalid": 331, "out_of_range": 48, "valid": 4}
    assert coords["longitude"] == {"syntax_invalid": 374, "out_of_range": 4, "valid": 5}
    assert coords["rows_with_both_valid"] == 0
    assert coords["valid_point_coverage"] == 0.0
    assert report["coverage"] == {"elements_total": 383, "elements_clean": 0}
    assert report["errors"] == []

    # El '?' ASCII literal se preserva en exactamente los 5 valores Ubicacion
    # capturados (filas 5, 6, 46, 47, 115); los valores raw nunca se corrigen.
    with_question_mark = [r for r in network if "?" in r["stop_name"]]
    assert len(with_question_mark) == 5
    assert sorted(r["stop_id"] for r in with_question_mark) == ["115", "46", "47", "5", "6"]


def test_los_hashes_capturados_pasan_la_validacion_estructural():
    from mobility_reliability.validation import validate_source_snapshot

    routes = validate_source_snapshot(ROUTES_MANIFEST, RAW_DIR)
    stops = validate_source_snapshot(STOPS_MANIFEST, RAW_DIR)

    assert routes.content_hash == "dc3082ad1312e7f9c7127fef316b4b70d8b452dcd94025d471f0b417f88ee07a"
    assert stops.content_hash == "20969d2e6dbc4d91338901f88c2805afaf642b757adfa4be97225c7364bdc62c"
    assert routes.row_count == 76
    assert stops.row_count == 383
    # Los resource IDs y URLs aprobados exactos se conservan en la proyección.
    assert routes.resource_id == "e55af215-4648-4e3b-84c9-d7e929435008"
    assert stops.resource_id == "ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e"
    assert routes.dataset_id == "rutas-de-transporte-publico"
    assert stops.dataset_id == "paradas-de-transporte-publico"


def test_transform_captures_combina_los_dos_snapshots_aprobados():
    combined = transform_captures(ROUTES_MANIFEST, STOPS_MANIFEST, RAW_DIR)

    assert len(combined["source_snapshots"]) == 2
    assert len(combined["mobility_network"]) == 76 + 383
    assert len(combined["planned_service"]) == 76 * 3
    assert len(combined["quality_reports"]) == 2
    assert combined["source_snapshots"][0]["row_count"] == 76
    assert combined["source_snapshots"][1]["row_count"] == 383
