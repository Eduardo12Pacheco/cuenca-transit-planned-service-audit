"""Pruebas de contrato de la transformación canónica del snapshot.

API pública bajo prueba
-----------------------
- ``mobility_reliability.transformation.transform_snapshot(manifest_path, raw_dir)``
- ``mobility_reliability.transformation.transform_captures(route_manifest_path, stops_manifest_path, raw_dir)``

Semántica bajo prueba
---------------------
- La validación estructural se ejecuta primero y lanza ``SnapshotValidationError``
  ante cualquier inconsistencia manifest/raw; los problemas de calidad de datos
  de origen siguen siendo observables como ``quality_flags`` por registro y
  advertencias/conteos del reporte: las filas raw nunca se corrigen ni se
  descartan silenciosamente.
- ``mobility_network``: un registro de ruta/parada por fila raw con mapeo
  exacto de columnas, cada columna de entrada preservada en ``raw``,
  ``network_id`` estable (snapshot + número de fila), provenance y flags de
  calidad estructurados por campo. No se crea geometría de rutas. La geometría
  de paradas es un punto solo cuando AMBAS coordenadas pasan el parser estricto
  y los rangos globales.
- ``planned_service``: un registro por fila de ruta y tipo de día
  (weekday/saturday/sunday) con minutos del día de servicio tipados y
  preservación explícita del H:MM en ``*_raw``; ``0:09`` -> 9; los valores
  superiores a 24:00 se preservan sin conversión de calendario; el centinela
  ``0:00/0:00/0:00`` es ``service_status='no_service'`` (ceros tipados
  conservados, nunca una ventana activa inválida); las ventanas activas exigen
  ``start < end`` y ``headway > 0``; los fallos malformados/de cronología anulan
  los valores tipados afectados con sus flags; ``service_date`` nunca se inventa
  (siempre null).
- Reportes de calidad: conteos de filas/esperadas (esperada solo para los dos
  resource IDs conocidos), campos faltantes, duplicados de fila completa y de
  clave natural, SENTIDO desconocido, conteos de coordenadas inválidas +
  cobertura de puntos válidos, conteos de horario inválido/sin-servicio/
  intervalo, advertencias, errores y cobertura de elementos limpios.

Todos los fixtures son manifests/raws sintéticos pequeños derivados de las
filas capturadas; no ocurre ninguna captura real ni acceso a red.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from capture_fixtures import (
    ROUTES_DATASET_ID,
    STOPS_DATASET_ID,
    write_snapshot,
)

from mobility_reliability.transformation import (
    KNOWN_EXPECTED_ROW_COUNTS,
    transform_captures,
    transform_snapshot,
)
from mobility_reliability.validation import SnapshotValidationError

ROUTES_RESOURCE_ID = "e55af215-4648-4e3b-84c9-d7e929435008"
STOPS_RESOURCE_ID = "ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e"

# Derivado de las filas capturadas: las filas 1 y 21 son filas capturadas
# textuales; la fila 12 conserva el ORIGEN en blanco capturado pero su horario
# es sintético para ejercitar >24:00, violaciones de cronología y celdas
# malformadas (el snapshot capturado no tiene ninguna de esas).
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

# Derivado de las filas capturadas: las filas 5, 26, 226, 75 son filas
# capturadas textuales (incluyen el '?' ASCII literal y los valores de tres
# decimales); la fila 328 combina dos valores de coordenadas válidos reales
# (-2.855 de la fila 328, -78.99 de la fila 299) porque el snapshot capturado
# no tiene ninguna fila con ambas coordenadas válidas — esto ejercita la rama
# de geometría con ambas válidas.
STOPS_RAW = (
    "N,Ubicacion,Latitud,Longitud,Paleta\n"
    "5,AV 10 DE AGOSTO INTERSECCION FEDERICO PROA?O,-2.910.397,-79.010.522,SI\n"
    "26,12 DE ABRIL 5-99 INTERSECCION AV SOLANO,-290.179,-790.064,NO\n"
    "226,CALLE AV. HURTADO DE MENDOZA INTERSECCION CALLE RIO PALORA,-28.957,-78.991.753,SI\n"
    "75,CALLE PRESIDENTE CORDOVA INTERSECCION VARGAS MACHUCA,-2.900.025,-79.0,SI\n"
    "328,AV DE LAS AMERICAS,-2.855,-78.99,NO\n"
)

STOPS_RAW_HEADER = ["N", "Ubicacion", "Latitud", "Longitud", "Paleta"]
ROUTES_RAW_HEADER = [
    "LINEA",
    "COMPANIA",
    "SENTIDO",
    "ORIGEN",
    "DESTINO",
    "LUNES_VIERNES_INICIO",
    "LUNES_VIERNES_FIN",
    "LUNES_VIERNES_INTERVALO",
    "SABADOS_INICIO",
    "SABADOS_FIN",
    "SABADOS_INTERVALO",
    "DOMINGOS_INICIO",
    "DOMINGOS_FIN",
    "DOMINGOS_INTERVALO",
]


def write_capture(
    tmp_path: Path,
    *,
    dataset_id: str,
    raw_text: str,
    resource_id: str,
    resource_name: str,
    resource_url: str,
) -> Path:
    """Escribe un fixture válido de raw+manifest; devuelve la ruta del manifest."""
    _, manifest_path, _ = write_snapshot(
        tmp_path,
        dataset_id=dataset_id,
        raw_text=raw_text,
        resource_id=resource_id,
        resource_name=resource_name,
    )
    return manifest_path


def routes_capture(tmp_path: Path) -> Path:
    return write_capture(
        tmp_path,
        dataset_id=ROUTES_DATASET_ID,
        raw_text=ROUTES_RAW,
        resource_id=ROUTES_RESOURCE_ID,
        resource_name="GADCuenca_RutasTransporte_2025Marzo.csv",
        resource_url="https://fixtures.invalid/rutas.csv",
    )


def stops_capture(tmp_path: Path) -> Path:
    return write_capture(
        tmp_path,
        dataset_id=STOPS_DATASET_ID,
        raw_text=STOPS_RAW,
        resource_id=STOPS_RESOURCE_ID,
        resource_name="GADCuenca_ParadasTransporte_2025Abril.csv",
        resource_url="https://fixtures.invalid/paradas.csv",
    )


def snapshot_for(tmp_path: Path, dataset_id: str) -> dict:
    if dataset_id == ROUTES_DATASET_ID:
        manifest_path = routes_capture(tmp_path)
    else:
        manifest_path = stops_capture(tmp_path)
    return transform_snapshot(manifest_path, tmp_path / "raw")


def route_record(records: list[dict], *, route_line: str) -> dict:
    return next(r for r in records if r["element_type"] == "route" and r["route_line"] == route_line)


# ---------------------------------------------------------------------------
# mobility_network: rutas
# ---------------------------------------------------------------------------


def test_registros_de_rutas_mapean_columnas_exactas_preservan_raw_y_provenance(tmp_path):
    result = snapshot_for(tmp_path, ROUTES_DATASET_ID)

    records = result["mobility_network"]
    assert [r["element_type"] for r in records] == ["route", "route", "route"]
    first = records[0]
    assert first["route_line"] == "1"
    assert first["company"] == "SIT"
    assert first["direction"] == "IDA"
    assert first["origin"] == "LIRIO"
    assert first["destination"] == "KENNEDY"
    # Cada columna de entrada se preserva textual en el mapeo raw.
    assert list(first["raw"]) == ROUTES_RAW_HEADER
    assert first["raw"]["LUNES_VIERNES_INTERVALO"] == "0:09"
    assert first["raw"]["DOMINGOS_INTERVALO"] == "0:15"
    # network_id estable desde snapshot + número de fila.
    assert first["network_id"] == "rutas-de-transporte-publico@2026-08-02T18-51-08Z::route:00001"
    assert records[1]["network_id"].endswith("::route:00002")
    # Provenance vincula el registro con el evento de recolección exacto.
    provenance = first["provenance"]
    assert provenance["source_snapshot_id"] == "rutas-de-transporte-publico@2026-08-02T18-51-08Z"
    assert provenance["source_id"] == "cuenca-en-datos-routes"
    assert provenance["dataset_id"] == ROUTES_DATASET_ID
    assert provenance["resource_id"] == ROUTES_RESOURCE_ID
    assert provenance["raw_file"].startswith("rutas-de-transporte-publico/")
    assert provenance["source_url"].startswith("https://cuencaendatos.cuenca.gob.ec/")


def test_campos_faltantes_de_ruta_se_marcan_sin_descartar_la_fila(tmp_path):
    result = snapshot_for(tmp_path, ROUTES_DATASET_ID)

    line12 = route_record(result["mobility_network"], route_line="12")
    assert line12["origin"] is None  # el blanco se vuelve null
    assert line12["destination"] == "PLATAFORMA ITINERANTE QUINTA CHICA"
    flags = line12["quality_flags"]
    assert {"field": "ORIGEN", "flag": "missing", "value": ""} in flags
    # La fila raw sobrevive textual.
    assert line12["raw"]["ORIGEN"] == ""
    assert line12["raw"]["LINEA"] == "12"


def test_sentido_desconocido_no_vacio_se_marca_y_el_blanco_sigue_missing(tmp_path):
    raw = (
        "LINEA,COMPANIA,SENTIDO,ORIGEN,DESTINO,"
        "LUNES_VIERNES_INICIO,LUNES_VIERNES_FIN,LUNES_VIERNES_INTERVALO,"
        "SABADOS_INICIO,SABADOS_FIN,SABADOS_INTERVALO,"
        "DOMINGOS_INICIO,DOMINGOS_FIN,DOMINGOS_INTERVALO\n"
        "99,EMPRESA X,VUELTA,CENTRO,NORTE,6:00,18:00,0:10,6:00,18:00,0:10,6:00,18:00,0:10\n"
        "98,EMPRESA X,,CENTRO,NORTE,6:00,18:00,0:10,6:00,18:00,0:10,6:00,18:00,0:10\n"
    )
    _, manifest_path, raw_dir = write_snapshot(tmp_path, raw_text=raw, row_count=2)

    result = transform_snapshot(manifest_path, raw_dir)

    records = {r["route_line"]: r for r in result["mobility_network"]}
    # SENTIDO no vacío desconocido: valor tipado y valor raw preservados, marcado.
    vuelta = records["99"]
    assert vuelta["direction"] == "VUELTA"
    assert vuelta["raw"]["SENTIDO"] == "VUELTA"
    assert {"field": "SENTIDO", "flag": "unknown", "value": "VUELTA"} in vuelta["quality_flags"]
    # El SENTIDO en blanco sigue siendo un flag missing, nunca se reporta dos veces como unknown.
    blank = records["98"]
    assert blank["direction"] is None
    assert {"field": "SENTIDO", "flag": "missing", "value": ""} in blank["quality_flags"]
    assert not any(f["field"] == "SENTIDO" and f["flag"] == "unknown" for f in blank["quality_flags"])
    # El reporte cuenta ambos como no IDA/RETORNO (el blanco incluido).
    assert result["quality_report"]["sentido"]["unknown_count"] == 2


def test_los_registros_de_rutas_nunca_crean_geometria(tmp_path):
    result = snapshot_for(tmp_path, ROUTES_DATASET_ID)
    assert all("geometry" not in r for r in result["mobility_network"])


# ---------------------------------------------------------------------------
# mobility_network: paradas y el parser estricto de coordenadas
# ---------------------------------------------------------------------------


def test_los_registros_de_paradas_mapean_columnas_y_preservan_raw(tmp_path):
    result = snapshot_for(tmp_path, STOPS_DATASET_ID)

    records = result["mobility_network"]
    assert [r["element_type"] for r in records] == ["stop"] * 5
    first = records[0]
    assert first["stop_id"] == "5"
    assert first["stop_name"] == "AV 10 DE AGOSTO INTERSECCION FEDERICO PROA?O"
    assert first["palette"] == "SI"
    assert list(first["raw"]) == STOPS_RAW_HEADER
    assert first["raw"]["Latitud"] == "-2.910.397"
    # El '?' ASCII literal se preserva, nunca se corrige.
    assert "?" in first["stop_name"]
    assert first["provenance"]["source_snapshot_id"] == "paradas-de-transporte-publico@2026-08-02T19-27-36Z"
    assert first["provenance"]["resource_id"] == STOPS_RESOURCE_ID


def test_el_parser_estricto_de_coordenadas_rechaza_valores_de_tres_decimales(tmp_path):
    result = snapshot_for(tmp_path, STOPS_DATASET_ID)
    records = {r["stop_id"]: r for r in result["mobility_network"]}

    row5 = records["5"]
    # '-2.910.397' tiene dos puntos decimales: syntax-invalid, null tipado, marcado.
    assert row5["latitude"] is None
    assert row5["longitude"] is None
    flags = {f["field"]: f["flag"] for f in row5["quality_flags"]}
    assert flags == {"Latitud": "syntax_invalid", "Longitud": "syntax_invalid"}

    row26 = records["26"]
    # '-290.179' parsea sintácticamente pero está fuera del rango global de latitud.
    assert row26["latitude"] is None
    assert row26["longitude"] is None
    flags26 = {f["field"]: f["flag"] for f in row26["quality_flags"]}
    assert flags26 == {"Latitud": "out_of_range", "Longitud": "out_of_range"}


def test_coordenadas_validas_tipadas_y_geometria_solo_cuando_ambas_son_validas(tmp_path):
    result = snapshot_for(tmp_path, STOPS_DATASET_ID)
    records = {r["stop_id"]: r for r in result["mobility_network"]}

    # Solo la fila 328 tiene ambas coordenadas válidas -> la única geometría de punto.
    row328 = records["328"]
    assert row328["latitude"] == -2.855
    assert row328["longitude"] == -78.99
    assert row328["geometry"] == {"type": "Point", "coordinates": [-78.99, -2.855]}
    assert row328["quality_flags"] == []

    # Las filas con una sola coordenada válida siguen teniendo registro de parada, sin geometría.
    row226 = records["226"]
    assert row226["latitude"] == -28.957
    assert row226["longitude"] is None
    assert row226["geometry"] is None

    row75 = records["75"]
    assert row75["latitude"] is None
    assert row75["longitude"] == -79.0
    assert row75["geometry"] is None


# ---------------------------------------------------------------------------
# planned_service
# ---------------------------------------------------------------------------


def test_registros_de_servicio_por_tipo_de_dia_con_minutos_tipados_y_texto_raw(tmp_path):
    result = snapshot_for(tmp_path, ROUTES_DATASET_ID)

    services = result["planned_service"]
    assert len(services) == 9  # 3 rows x 3 day types
    by_key = {(s["route_line"], s["day_type"]): s for s in services}
    weekdays = by_key[("1", "weekday")]
    assert weekdays["planned_start"] == 350  # 5:50
    assert weekdays["planned_end"] == 1275  # 21:15
    assert weekdays["planned_headway"] == 9  # 0:09
    assert weekdays["planned_start_raw"] == "5:50"
    assert weekdays["planned_end_raw"] == "21:15"
    assert weekdays["planned_headway_raw"] == "0:09"
    assert weekdays["service_status"] == "active"
    assert weekdays["service_date"] is None  # nunca se inventa
    assert weekdays["network_id"].endswith("::route:00001")
    assert weekdays["service_id"].endswith(":weekday")
    # Los metadatos/cutoff del snapshot se incluyen.
    assert weekdays["snapshot_cutoff"]["resource_name"] == "GADCuenca_RutasTransporte_2025Marzo.csv"
    assert weekdays["snapshot_cutoff"]["resource_description"]
    assert weekdays["provenance"]["source_snapshot_id"].startswith("rutas-de-transporte-publico@")


def test_valores_superiores_a_24h_preservados_sin_conversion_de_calendario(tmp_path):
    result = snapshot_for(tmp_path, ROUTES_DATASET_ID)
    by_key = {(s["route_line"], s["day_type"]): s for s in result["planned_service"]}

    line12_weekday = by_key[("12", "weekday")]
    assert line12_weekday["planned_start"] == 1510  # 25:10 permanece en el día de servicio
    assert line12_weekday["planned_end"] == 1590  # 26:30
    assert line12_weekday["planned_start_raw"] == "25:10"
    assert line12_weekday["service_status"] == "active"


def test_el_centinela_no_service_no_es_una_ventana_activa_invalida(tmp_path):
    result = snapshot_for(tmp_path, ROUTES_DATASET_ID)
    by_key = {(s["route_line"], s["day_type"]): s for s in result["planned_service"]}

    for day_type in ("saturday", "sunday"):
        service = by_key[("21", day_type)]
        assert service["service_status"] == "no_service"
        assert service["planned_start"] == 0
        assert service["planned_end"] == 0
        assert service["planned_headway"] == 0
        assert service["planned_start_raw"] == "0:00"
        assert service["planned_headway_raw"] == "0:00"
        assert service["quality_flags"] == []
    # La ventana weekday de la misma línea sigue activa.
    assert by_key[("21", "weekday")]["service_status"] == "active"


def test_la_violacion_de_cronologia_anula_la_ventana_con_flags(tmp_path):
    result = snapshot_for(tmp_path, ROUTES_DATASET_ID)
    by_key = {(s["route_line"], s["day_type"]): s for s in result["planned_service"]}

    saturday = by_key[("12", "saturday")]
    assert saturday["service_status"] == "invalid"
    assert saturday["planned_start"] is None
    assert saturday["planned_end"] is None
    # El headway en sí parsea bien; solo la ventana es inválida.
    assert saturday["planned_headway"] == 20
    flags = {f["field"]: f["flag"] for f in saturday["quality_flags"]}
    assert flags == {
        "planned_start": "chronology_invalid",
        "planned_end": "chronology_invalid",
    }


def test_la_celda_de_horario_malformada_anula_solo_ese_valor(tmp_path):
    result = snapshot_for(tmp_path, ROUTES_DATASET_ID)
    by_key = {(s["route_line"], s["day_type"]): s for s in result["planned_service"]}

    sunday = by_key[("12", "sunday")]
    assert sunday["service_status"] == "invalid"
    assert sunday["planned_start"] == 480  # 8:00 kept
    assert sunday["planned_end"] == 540  # 9:00 kept
    assert sunday["planned_headway"] is None  # 'bad' tiene formato malformado
    assert sunday["planned_headway_raw"] == "bad"
    assert {"field": "planned_headway", "flag": "malformed", "value": "bad"} in sunday["quality_flags"]


# ---------------------------------------------------------------------------
# reportes de calidad
# ---------------------------------------------------------------------------


def test_metricas_del_reporte_de_calidad_de_rutas(tmp_path):
    report = snapshot_for(tmp_path, ROUTES_DATASET_ID)["quality_report"]

    assert report["dataset_id"] == ROUTES_DATASET_ID
    assert report["row_count"] == 3
    assert report["expected_row_count"] == 76  # resource id conocido -> la verificación aplica
    assert report["row_count_matches_expected"] is False  # el conteo de filas del fixture difiere
    assert report["missing_fields"] == {"ORIGEN": 1}
    assert report["duplicates"]["full_row"] == {"duplicated_keys": 0, "duplicate_rows": 0}
    natural = report["duplicates"]["natural_key"]
    assert natural["duplicated_keys"] == 0
    assert natural["duplicate_rows"] == 0
    assert natural["key_fields"] == ["LINEA", "COMPANIA", "SENTIDO", "ORIGEN", "DESTINO"]
    assert report["sentido"] == {"allowed": ["IDA", "RETORNO"], "unknown_count": 0}
    assert report["coordinates"] is None  # no aplica a rutas
    schedule = report["schedule"]
    assert schedule["cells_total"] == 27
    assert schedule["cells_malformed"] == 1
    assert schedule["cells_over_24h"] == 2
    assert schedule["active_windows_total"] == 9
    assert schedule["active_windows_invalid"] == 2
    assert schedule["interval_cells_total"] == 9
    assert schedule["interval_cells_invalid"] == 1
    assert schedule["no_service_windows_count"] == 2
    assert report["no_service_windows"] == [
        {"route_line": "21", "direction": "IDA", "day_type": "saturday"},
        {"route_line": "21", "direction": "IDA", "day_type": "sunday"},
    ]
    assert report["coverage"] == {"elements_total": 3, "elements_clean": 2}
    assert report["errors"] == []
    assert any("ORIGEN" in w for w in report["warnings"])


def test_metricas_del_reporte_de_calidad_de_paradas(tmp_path):
    report = snapshot_for(tmp_path, STOPS_DATASET_ID)["quality_report"]

    assert report["row_count"] == 5
    assert report["expected_row_count"] == 383
    assert report["row_count_matches_expected"] is False
    assert report["missing_fields"] == {}
    assert report["duplicates"]["full_row"]["duplicate_rows"] == 0
    assert report["duplicates"]["natural_key"]["key_fields"] == ["N"]
    assert report["sentido"] is None  # no aplica a paradas
    assert report["schedule"] is None  # no aplica a paradas
    coordinates = report["coordinates"]
    assert coordinates["latitude"] == {"syntax_invalid": 2, "out_of_range": 1, "valid": 2}
    assert coordinates["longitude"] == {"syntax_invalid": 2, "out_of_range": 1, "valid": 2}
    assert coordinates["rows_with_both_valid"] == 1
    assert coordinates["valid_point_coverage"] == 0.2
    assert report["coverage"] == {"elements_total": 5, "elements_clean": 1}
    assert report["no_service_windows"] == []
    assert report["errors"] == []


def test_expected_row_count_solo_para_resource_ids_conocidos(tmp_path):
    # Se reconstruye la misma captura con un resource id desconocido.
    _, other_manifest, _ = write_snapshot(
        tmp_path / "unknown",
        dataset_id=ROUTES_DATASET_ID,
        raw_text=ROUTES_RAW,
        resource_id="unknown-resource-id",
        resource_name="other.csv",
    )

    report = transform_snapshot(other_manifest, tmp_path / "unknown" / "raw")["quality_report"]
    assert report["resource_id"] == "unknown-resource-id"
    assert report["expected_row_count"] is None
    assert report["row_count_matches_expected"] is None
    # El mapa conocido se exporta para documentación.
    assert KNOWN_EXPECTED_ROW_COUNTS == {
        ROUTES_RESOURCE_ID: 76,
        STOPS_RESOURCE_ID: 383,
    }


def test_las_advertencias_del_manifest_aparecen_en_las_advertencias_del_reporte(tmp_path):
    _, manifest_with_warning, _ = write_snapshot(
        tmp_path / "warn",
        dataset_id=ROUTES_DATASET_ID,
        raw_text=ROUTES_RAW,
        warnings=["CKAN license title is generic ('X'); compatibility is decided by license id"],
    )

    report = transform_snapshot(manifest_with_warning, tmp_path / "warn" / "raw")["quality_report"]
    assert any(w.startswith("manifest:") for w in report["warnings"])


# ---------------------------------------------------------------------------
# fallos estructurales y capturas combinadas
# ---------------------------------------------------------------------------


def test_el_fallo_estructural_se_propaga_a_traves_de_la_transformacion(tmp_path):
    manifest_path = routes_capture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "failed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="status"):
        transform_snapshot(manifest_path, tmp_path / "raw")


def test_la_salida_de_la_transformacion_es_serializable_a_json(tmp_path):
    for dataset_id in (ROUTES_DATASET_ID, STOPS_DATASET_ID):
        result = snapshot_for(tmp_path, dataset_id)
        json.dumps(result)


# ---------------------------------------------------------------------------
# mapeo fuente por tipo de día (documentado en docs/source-to-canonical-mapping.md)
# ---------------------------------------------------------------------------


def test_las_familias_de_columnas_por_tipo_de_dia_mapean_a_valores_canonicos(tmp_path):
    """Las tres familias de columnas fuente mapean exactamente a weekday/saturday/sunday.

    La fuente no publica ninguna columna ``day_type``: cada fila de ruta lleva
    tres familias de columnas (``LUNES_VIERNES_*``, ``SABADOS_*``, ``DOMINGOS_*``)
    y el modelo canónico deriva un registro ``planned_service`` por familia.
    Esta prueba fija ese mapeo solo a través de la salida de transformación
    pública existente (aquí no se cambia código de transformación).
    """
    from mobility_reliability.transformation.snapshot import DAY_TYPES

    assert DAY_TYPES == (
        ("weekday", "LUNES_VIERNES_INICIO", "LUNES_VIERNES_FIN", "LUNES_VIERNES_INTERVALO"),
        ("saturday", "SABADOS_INICIO", "SABADOS_FIN", "SABADOS_INTERVALO"),
        ("sunday", "DOMINGOS_INICIO", "DOMINGOS_FIN", "DOMINGOS_INTERVALO"),
    )

    result = snapshot_for(tmp_path, ROUTES_DATASET_ID)
    by_day = {record["day_type"]: record for record in result["planned_service"] if record["route_line"] == "1"}
    assert set(by_day) == {"weekday", "saturday", "sunday"}

    # LUNES_VIERNES_INICIO/FIN/INTERVALO -> weekday (texto raw y minutos tipados).
    weekday = by_day["weekday"]
    assert (
        weekday["planned_start_raw"],
        weekday["planned_end_raw"],
        weekday["planned_headway_raw"],
    ) == ("5:50", "21:15", "0:09")
    assert (weekday["planned_start"], weekday["planned_end"], weekday["planned_headway"]) == (
        350,
        1275,
        9,
    )
    # SABADOS_INICIO/FIN/INTERVALO -> saturday.
    saturday = by_day["saturday"]
    assert (
        saturday["planned_start_raw"],
        saturday["planned_end_raw"],
        saturday["planned_headway_raw"],
    ) == ("5:50", "20:30", "0:12")
    assert (
        saturday["planned_start"],
        saturday["planned_end"],
        saturday["planned_headway"],
    ) == (350, 1230, 12)
    # DOMINGOS_INICIO/FIN/INTERVALO -> sunday.
    sunday = by_day["sunday"]
    assert (
        sunday["planned_start_raw"],
        sunday["planned_end_raw"],
        sunday["planned_headway_raw"],
    ) == ("6:00", "20:00", "0:15")
    assert (sunday["planned_start"], sunday["planned_end"], sunday["planned_headway"]) == (
        360,
        1200,
        15,
    )
    # El valor canónico del día se deriva de la familia de columnas fuente; la
    # fuente en sí no tiene columna day_type.
    assert all(record["day_type"] == day for day, record in by_day.items())


def test_transform_captures_combina_ambos_snapshots(tmp_path):
    combined = transform_captures(routes_capture(tmp_path), stops_capture(tmp_path), tmp_path / "raw")

    assert len(combined["source_snapshots"]) == 2
    assert {s["dataset_id"] for s in combined["source_snapshots"]} == {
        ROUTES_DATASET_ID,
        STOPS_DATASET_ID,
    }
    assert len(combined["mobility_network"]) == 8  # 3 routes + 5 stops
    assert [r["element_type"] for r in combined["mobility_network"]] == [
        "route",
        "route",
        "route",
        "stop",
        "stop",
        "stop",
        "stop",
        "stop",
    ]
    assert len(combined["planned_service"]) == 9  # solo rutas: las paradas no tienen
    assert len(combined["quality_reports"]) == 2
    assert combined["transformation"]["name"] == "canonical-planned-service-transformation"
    json.dumps(combined)
