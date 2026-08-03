"""Pruebas de contrato de la auditoría sin conexión del formato de coordenadas.

API pública bajo prueba
-----------------------
- ``mobility_reliability.quality.COORDINATE_CATEGORIES``
- ``mobility_reliability.quality.classify_coordinate_value(value)``
- ``mobility_reliability.quality.audit_coordinate_formats(manifest_path, raw_dir)``
- ``mobility_reliability.quality.convert_coordinate_value(value)``
- ``mobility_reliability.quality.render_coordinate_audit_markdown(audit)``
- ``mobility_reliability.quality.write_coordinate_audit_artifacts(audit, json_path, markdown_path)``

Semántica bajo prueba
---------------------
- El clasificador es determinista, solo textual y asigna cada valor a
  exactamente una de ``COORDINATE_CATEGORIES``. Precedencia documentada: vacío;
  centinela ``?`` (recortado); WKT/geometría obvio (revisado antes de
  DMS/numérico); miles agrupados canónicos (2+ separadores de punto/comma,
  todos los grupos de 3 dígitos); decimal con coma simple; decimal estricto con
  punto; marcadores DMS obvios; texto residual; desconocido. Las candidatas son
  observacionales: la auditoría nunca afirma qué significan los separadores,
  nunca interpreta CRS/orden/WGS84/UTM/DMS, nunca convierte y nunca genera
  geometría.
- La auditoría lee solo la captura local de paradas exitosa a través de la
  validación estructural estricta (``SnapshotValidationError`` sigue
  propagándose) y falla cerrado cuando el snapshot no es el dataset/resource de
  paradas aprobado o falta una columna de coordenadas.
- Los ejemplos preservan el valor raw exacto con números de fila de datos
  1-based y se limitan a 20 por categoría por columna; el artefacto nunca
  contiene el raw completo.
- ``convert_coordinate_value`` siempre lanza ``CoordinateConversionError``:
  ninguna evidencia local prueba formato/orden/CRS/conversión.
- ``?`` es un centinela, nunca una coordenada; ``Ubicacion`` nunca se usa.

La triangulación con la captura real al final lee el raw de paradas git-ignored
y fija los conteos observados (lat decimal 52 / miles 331; lon decimal 9 /
miles 374; 383 filas con ambas columnas de coordenadas no vacías; sin ``?`` en
las columnas de coordenadas). Esas pruebas se omiten (SKIP) cuando el raw está
ausente.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from mobility_reliability.quality import (
    COORDINATE_CATEGORIES,
    CoordinateAuditError,
    CoordinateConversionError,
    audit_coordinate_formats,
    classify_coordinate_value,
    convert_coordinate_value,
    render_coordinate_audit_markdown,
    write_coordinate_audit_artifacts,
)
from mobility_reliability.validation import SnapshotValidationError

from capture_fixtures import (
    STOPS_DATASET_ID,
    write_snapshot,
)

STOPS_RESOURCE_ID = "ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e"
STOPS_RESOURCE_NAME = "GADCuenca_ParadasTransporte_2025Abril.csv"

# Raw sintético de paradas que ejercita varias categorías: miles agrupados,
# decimales estrictos con punto, un centinela '?' y un valor decimal con coma.
# La fila 5 conserva espacios alrededor para que la preservación del raw exacto
# sea observable.
AUDIT_STOPS_RAW = (
    "N,Ubicacion,Latitud,Longitud,Paleta\n"
    "1,PLACE A,-2.895.956,-79.014.574,SI\n"
    "2,PLACE B,-28.957,-79.0,SI\n"
    "3,PLACE C,?,\"-2,895956\",SI\n"  # el valor con coma está entrecomillado en CSV
    "4,PLACE D,-2.895.956,-79.014.574,SI\n"
    "5,PLACE E,  -2.895.956  ,-79.014.574,SI\n"
)


def _audit(tmp_path, raw_text: str = AUDIT_STOPS_RAW, **write_kwargs) -> dict:
    """Escribe un fixture de paradas aprobado y ejecuta la auditoría contra él."""
    _, manifest_path, raw_dir = write_snapshot(
        tmp_path,
        dataset_id=STOPS_DATASET_ID,
        raw_text=raw_text,
        resource_id=STOPS_RESOURCE_ID,
        resource_name=STOPS_RESOURCE_NAME,
        **write_kwargs,
    )
    return audit_coordinate_formats(manifest_path, raw_dir)


# ---------------------------------------------------------------------------
# Clasificador textual determinista
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # vacío
        ("", "blank"),
        ("   ", "blank"),
        # centinela: exactamente '?' después de recortar, nunca una coordenada
        ("?", "sentinel"),
        (" ? ", "sentinel"),
        # decimal estricto con punto (entero con signo opcional o decimal de un solo punto)
        ("-28.957", "decimal_candidate"),
        ("-79.0", "decimal_candidate"),
        ("0", "decimal_candidate"),
        ("123", "decimal_candidate"),
        ("-290.709", "decimal_candidate"),
        # una sola coma como separador decimal
        ("-2,895956", "decimal_comma_candidate"),
        ("1,5", "decimal_comma_candidate"),
        # numerales agrupados canónicos: 2+ separadores de punto/comma, grupos de 3 dígitos
        ("-2.895.956", "thousands_separator_candidate"),
        ("-79.014.574", "thousands_separator_candidate"),
        ("2,895,956", "thousands_separator_candidate"),
        ("-2.895,956", "thousands_separator_candidate"),
        # marcadores DMS obvios (símbolo de grado o letra de hemisferio final)
        ('2°53\'45.6"S', "dms_candidate"),
        ("79°W", "dms_candidate"),
        ("-79.014.574W", "dms_candidate"),
        # texto obvio de WKT/geometría gana sobre contenido de apariencia numérica
        ("POINT(-79.014574 -2.895956)", "wkt_or_geometry_candidate"),
        ("SRID=4326;POINT(-79.014574 -2.895956)", "wkt_or_geometry_candidate"),
        ("LINESTRING(0 0, 1 1)", "wkt_or_geometry_candidate"),
        # texto residual vs desconocido residual
        ("no disponible", "other_text"),
        ("N/A", "other_text"),
        ("---", "unknown"),
        ("???", "unknown"),
        ("12..34", "unknown"),
        ("-2.89.956", "unknown"),
    ],
    ids=lambda pair: pair[1] if isinstance(pair, tuple) else pair,
)
def test_clasificador_asigna_cada_categoria_de_forma_determinista(value, expected):
    assert classify_coordinate_value(value) == expected
    assert classify_coordinate_value(value) == classify_coordinate_value(value)


def test_clasificador_solo_emite_categorias_documentadas_en_una_bateria():
    battery = [
        "", "   ", "?", " ? ", "-28.957", "-79.0", "0", "-2,895956", "1,5",
        "-2.895.956", "-79.014.574", "2,895,956", '2°53\'45.6"S', "79°W",
        "POINT(-79.014574 -2.895956)", "SRID=4326;POINT(0 0)", "no disponible",
        "N/A", "---", "???", "12..34", "-2.89.956", "x", "1.2.3", "1,2,3",
    ]
    results = {classify_coordinate_value(value) for value in battery}
    assert results <= set(COORDINATE_CATEGORIES)


def test_wkt_precede_a_numerico_y_centinela_precede_a_texto():
    # WKT gana incluso cuando el payload parece numerales agrupados.
    assert classify_coordinate_value("POINT(-2.895.956 -79.014.574)") == "wkt_or_geometry_candidate"
    # El centinela se revisa antes que cualquier patrón de texto/numérico.
    assert classify_coordinate_value(" ? ") == "sentinel"
    # El vacío se revisa primero.
    assert classify_coordinate_value("   ") == "blank"
    # Los numerales agrupados repetidos son candidatos de miles, no decimales con punto.
    assert classify_coordinate_value("-2.895.956") == "thousands_separator_candidate"


def test_wkt_exige_limite_de_palabra_clave_seguido_de_parentesis_abierto():
    # Preservado: palabras clave de geometría obvias seguidas de '(' (se permite
    # espacio opcional) y formas con prefijo SRID.
    for value in (
        "POINT(-79.014574 -2.895956)",
        "POINT ( -79.014574 -2.895956 )",
        "point(-79.014574 -2.895956)",
        "SRID=4326;POINT(-79.014574 -2.895956)",
        "SRID=4326; MULTIPOLYGON (((0 0, 1 1)))",
        "LINESTRING(0 0, 1 1)",
        "GEOMETRYCOLLECTION(EMPTY)",
        "GEOMETRY COLLECTION (EMPTY)",
    ):
        assert classify_coordinate_value(value) == "wkt_or_geometry_candidate", value
    # Límite: palabras comunes que solo empiezan con una palabra clave NO son
    # WKT y caen en las categorías residuales de texto/desconocido.
    for value in (
        "POINTLESS",
        "POINTLESS(0 0)",
        "POINTX(-79.0)",
        "NOTPOINT(-79.0)",
        "SRID=4326;POINTLESS",
        "MULTIPOINTLESS",
    ):
        assert classify_coordinate_value(value) != "wkt_or_geometry_candidate", value
        assert classify_coordinate_value(value) in ("other_text", "unknown")


# ---------------------------------------------------------------------------
# Función de auditoría: captura sintética de paradas aprobada
# ---------------------------------------------------------------------------


def test_auditoria_cuenta_todas_las_categorias_por_columna(tmp_path):
    audit = _audit(tmp_path)

    assert audit["per_column_counts"]["Latitud"] == {
        "blank": 0,
        "sentinel": 1,
        "decimal_candidate": 1,
        "decimal_comma_candidate": 0,
        "thousands_separator_candidate": 3,
        "dms_candidate": 0,
        "wkt_or_geometry_candidate": 0,
        "other_text": 0,
        "unknown": 0,
    }
    assert audit["per_column_counts"]["Longitud"] == {
        "blank": 0,
        "sentinel": 0,
        "decimal_candidate": 1,
        "decimal_comma_candidate": 1,
        "thousands_separator_candidate": 3,
        "dms_candidate": 0,
        "wkt_or_geometry_candidate": 0,
        "other_text": 0,
        "unknown": 0,
    }
    assert audit["row_count"] == 5
    assert audit["rows_with_any_nonblank"] == 5
    assert audit["rows_with_both_nonblank"] == 5
    assert audit["total_coordinate_values"] == 10
    assert audit["columns_audited"] == ["Latitud", "Longitud"]


def test_auditoria_ejemplos_preservan_valores_raw_exactos_con_numeros_de_fila(tmp_path):
    audit = _audit(tmp_path)

    assert audit["examples"]["Latitud"]["thousands_separator_candidate"] == [
        {"row": 1, "value": "-2.895.956"},
        {"row": 4, "value": "-2.895.956"},
        {"row": 5, "value": "  -2.895.956  "},
    ]
    assert audit["examples"]["Longitud"]["thousands_separator_candidate"][0] == {
        "row": 1,
        "value": "-79.014.574",
    }
    # El centinela '?' se registra como ejemplo centinela, nunca como coordenada.
    assert audit["examples"]["Latitud"]["sentinel"] == [{"row": 3, "value": "?"}]
    assert audit["examples"]["Longitud"]["decimal_comma_candidate"] == [
        {"row": 3, "value": "-2,895956"}
    ]


def test_ejemplos_limitados_a_20_y_nunca_incluyen_el_raw_completo(tmp_path):
    lines = ["N,Ubicacion,Latitud,Longitud,Paleta"]
    for index in range(1, 26):
        lines.append(f"{index},PLACE {index},-2.900.{index:03d},-79.014.574,SI")
    audit = _audit(tmp_path, raw_text="\n".join(lines) + "\n")

    examples = audit["examples"]["Latitud"]["thousands_separator_candidate"]
    assert len(examples) == 20
    assert examples[0] == {"row": 1, "value": "-2.900.001"}
    assert examples[-1] == {"row": 20, "value": "-2.900.020"}
    # Las filas más allá del límite se cuentan pero sus valores exactos nunca se
    # filtran al artefacto (sin raw completo en ninguna parte).
    assert audit["per_column_counts"]["Latitud"]["thousands_separator_candidate"] == 25
    dumped = json.dumps(audit)
    assert "-2.900.021" not in dumped
    assert "-2.900.025" not in dumped
    for column_examples in audit["examples"].values():
        for category_examples in column_examples.values():
            assert len(category_examples) <= 20


def test_auditoria_propaga_snapshot_id_resource_id_y_hash_raw(tmp_path):
    audit = _audit(tmp_path)

    assert audit["snapshot_id"] == "paradas-de-transporte-publico@2026-08-02T19-27-36Z"
    assert audit["dataset_id"] == STOPS_DATASET_ID
    assert audit["resource_id"] == STOPS_RESOURCE_ID
    assert audit["raw_sha256"] == hashlib.sha256(AUDIT_STOPS_RAW.encode("utf-8")).hexdigest()
    assert audit["raw_file"] == f"{STOPS_DATASET_ID}/2026-08-02T19-27-36Z.json"
    # Las rutas de evidencia se registran como se proveen: repo-relativas cuando
    # el llamador pasa rutas repo-relativas.
    expected_manifest = tmp_path / "manifests" / STOPS_DATASET_ID / "2026-08-02T19-27-36Z.manifest.json"
    assert audit["evidence"]["local_evidence_paths"][0] == str(expected_manifest)
    assert audit["evidence"]["local_evidence_paths"][1].endswith(audit["raw_file"])


def test_auditoria_queda_sin_resolver_y_no_emite_geometria_ni_conversion(tmp_path):
    audit = _audit(tmp_path)

    assert audit["format_resolved"] is False
    assert audit["decision"] == "format_unresolved"
    assert audit["conversion_justified"] is False
    assert audit["geometry_generated"] is False

    # Ningún campo llamado 'geometry' ni ningún resultado de conversión en
    # ninguna parte del artefacto; 'Ubicacion' nunca se consulta ni se emite.
    keys: list[str] = []

    def collect(obj) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                keys.append(key)
                collect(value)
        elif isinstance(obj, list):
            for item in obj:
                collect(item)

    collect(audit)
    assert "geometry" not in keys
    assert "conversion" not in keys
    # El contenido de 'Ubicacion' nunca aparece en las partes con datos del
    # artefacto (la palabra solo se usa en la prosa de metodología/evidencia).
    assert "Ubicacion" not in json.dumps(audit["examples"])
    assert "Ubicacion" not in json.dumps(audit["per_column_counts"])
    assert audit["evidence"]["fields_audited"] == ["Latitud", "Longitud"]
    assert any("source-contract.md" in path for path in audit["evidence"]["local_evidence_paths"])


def test_auditoria_evidencia_registra_todas_las_rutas_de_evidencia_local_y_campos_de_metadatos(tmp_path):
    audit = _audit(tmp_path)

    # Cada fuente de evidencia local en la que se apoya la auditoría se registra.
    paths = audit["evidence"]["local_evidence_paths"]
    for expected in (
        "docs/source-contract.md",
        "src/mobility_reliability/validation/source_snapshot.py",
        "src/mobility_reliability/transformation/snapshot.py",
        "tests/test_validation.py",
        "tests/test_transformation.py",
        "tests/test_captured_snapshots.py",
    ):
        assert expected in paths
    # Las rutas del manifest y del raw se registran como se proveen.
    assert paths[0].endswith(
        f"manifests/{STOPS_DATASET_ID}/2026-08-02T19-27-36Z.manifest.json"
    )
    assert paths[1].endswith(audit["raw_file"])

    # Los campos de metadatos del manifest/resource inspeccionados por la
    # validación estructural estricta en la que se apoya la auditoría se
    # declaran explícitamente.
    fields = audit["evidence"]["manifest_metadata_fields_inspected"]
    for field in (
        "source_metadata",
        "resource",
        "resource_id",
        "resource_name",
        "resource_format",
        "resource_url",
        "size",
        "description",
        "created",
        "last_modified",
        "metadata_modified",
    ):
        assert field in fields
    # El diccionario de datos ODS referenciado está ausente localmente.
    assert audit["evidence"]["source_data_dictionary_present_locally"] is False


# ---------------------------------------------------------------------------
# Función de auditoría: fail closed
# ---------------------------------------------------------------------------


def test_auditoria_falla_cerrada_para_dataset_distinto_de_paradas(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)  # captura de rutas

    with pytest.raises(CoordinateAuditError, match="paradas-de-transporte-publico"):
        audit_coordinate_formats(manifest_path, raw_dir)


def test_auditoria_falla_cerrada_para_resource_de_paradas_no_aprobado(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(
        tmp_path,
        dataset_id=STOPS_DATASET_ID,
        raw_text=AUDIT_STOPS_RAW,
        resource_id="ffa506af-01c4-4b5b-afe2-e2f63b862ca6",
        resource_name="GADCuenca_ParadasTransporte_2022Septiembre.csv",
    )

    with pytest.raises(CoordinateAuditError, match="resource"):
        audit_coordinate_formats(manifest_path, raw_dir)


def test_auditoria_falla_cerrada_por_columna_de_coordenadas_ausente(tmp_path):
    raw = "N,Ubicacion,Latitud,Paleta\n1,PLACE,-2.895.956,SI\n"
    _, manifest_path, raw_dir = write_snapshot(
        tmp_path,
        dataset_id=STOPS_DATASET_ID,
        raw_text=raw,
        resource_id=STOPS_RESOURCE_ID,
        resource_name=STOPS_RESOURCE_NAME,
    )

    with pytest.raises(CoordinateAuditError, match="Longitud"):
        audit_coordinate_formats(manifest_path, raw_dir)


def test_auditoria_preserva_el_fail_closed_de_la_validacion_estructural(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(
        tmp_path,
        dataset_id=STOPS_DATASET_ID,
        raw_text=AUDIT_STOPS_RAW,
        resource_id=STOPS_RESOURCE_ID,
        resource_name=STOPS_RESOURCE_NAME,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content_hash"] = hashlib.sha256(b"different bytes").hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    # La auditoría nunca omite la validación estructural estricta.
    with pytest.raises(SnapshotValidationError):
        audit_coordinate_formats(manifest_path, raw_dir)


# ---------------------------------------------------------------------------
# Guarda de conversión
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["-2.895.956", "-28.957", "-79.0", "?", ""])
def test_conversion_siempre_se_rechaza_sin_evidencia(value):
    # Ninguna evidencia local prueba formato/orden/CRS, por lo que la conversión
    # se rechaza incondicionalmente y nunca se produce ningún resultado.
    with pytest.raises(CoordinateConversionError):
        convert_coordinate_value(value)


# ---------------------------------------------------------------------------
# Renderer Markdown y escritor de artefactos
# ---------------------------------------------------------------------------


def test_reporte_markdown_orientado_al_lector_y_decision_primero(tmp_path):
    audit = _audit(tmp_path)

    markdown = render_coordinate_audit_markdown(audit)

    assert markdown.startswith("# Auditoría de formato de coordenadas")
    assert "format_unresolved" in markdown
    for section in (
        "## Decisión",
        "## Snapshot",
        "## Metodología",
        "## Conteos por columna",
        "## Ejemplos",
        "## Evidencia",
        "## Recomendación",
    ):
        assert section in markdown
    # Los valores raw exactos de ejemplo aparecen con sus números de fila.
    assert "| 1 | `-2.895.956` |" in markdown
    assert "| 3 | `?` |" in markdown
    assert "nunca afirma qué significan los separadores" in markdown
    # La sección de Evidencia declara los campos de metadatos del manifest/resource
    # inspeccionados.
    assert "Campos de metadatos del manifest inspeccionados" in markdown


def test_escritor_emite_json_y_markdown_validos_en_utf8(tmp_path):
    audit = _audit(tmp_path)
    json_path = tmp_path / "quality" / "coordinate-format-audit.json"
    markdown_path = tmp_path / "coordinate-quality-audit.md"

    written = write_coordinate_audit_artifacts(audit, json_path, markdown_path)

    assert json_path.is_file()
    assert markdown_path.is_file()
    raw_bytes = json_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf")  # UTF-8 sin BOM
    parsed = json.loads(raw_bytes.decode("utf-8"))
    assert parsed["decision"] == "format_unresolved"
    assert parsed["snapshot_id"] == audit["snapshot_id"]
    assert parsed["per_column_counts"] == audit["per_column_counts"]
    assert markdown_path.read_text(encoding="utf-8").startswith("# Auditoría de formato de coordenadas")
    assert written == {"json_path": str(json_path), "markdown_path": str(markdown_path)}


# ---------------------------------------------------------------------------
# Triangulación con la captura real (SKIP cuando el raw git-ignored está ausente)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
STOPS_MANIFEST = (
    REPO_ROOT / "data/manifests/paradas-de-transporte-publico/2026-08-02T19-27-36Z.manifest.json"
)
STOPS_RAW = REPO_ROOT / "data/raw/paradas-de-transporte-publico/2026-08-02T19-27-36Z.json"
RAW_DIR = REPO_ROOT / "data/raw"

requires_stops_raw = pytest.mark.skipif(
    not STOPS_RAW.is_file(),
    reason="el raw de paradas aprobado está git-ignored y ausente en este checkout",
)

# Verdad de campo observada (verificada contra los bytes raw, captura
# 2026-08-02): lat decimal 52 / miles 331; lon decimal 9 / miles 374; todas las
# demás categorías 0; 383 filas con ambas columnas de coordenadas no vacías; sin
# '?' en las columnas de coordenadas ('?' solo aparece en 5 valores de
# Ubicacion, que nunca se usan aquí).
LATITUD_PINNED_COUNTS = {
    "blank": 0,
    "sentinel": 0,
    "decimal_candidate": 52,
    "decimal_comma_candidate": 0,
    "thousands_separator_candidate": 331,
    "dms_candidate": 0,
    "wkt_or_geometry_candidate": 0,
    "other_text": 0,
    "unknown": 0,
}
LONGITUD_PINNED_COUNTS = {
    "blank": 0,
    "sentinel": 0,
    "decimal_candidate": 9,
    "decimal_comma_candidate": 0,
    "thousands_separator_candidate": 374,
    "dms_candidate": 0,
    "wkt_or_geometry_candidate": 0,
    "other_text": 0,
    "unknown": 0,
}


@requires_stops_raw
def test_auditoria_de_formato_de_coordenadas_de_paradas_sobre_el_raw_capturado():
    audit = audit_coordinate_formats(STOPS_MANIFEST, RAW_DIR)

    assert audit["snapshot_id"] == "paradas-de-transporte-publico@2026-08-02T19-27-36Z"
    assert audit["resource_id"] == "ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e"
    assert audit["raw_sha256"] == "20969d2e6dbc4d91338901f88c2805afaf642b757adfa4be97225c7364bdc62c"
    assert audit["row_count"] == 383
    assert audit["total_coordinate_values"] == 766
    assert audit["rows_with_any_nonblank"] == 383
    assert audit["rows_with_both_nonblank"] == 383
    assert audit["per_column_counts"]["Latitud"] == LATITUD_PINNED_COUNTS
    assert audit["per_column_counts"]["Longitud"] == LONGITUD_PINNED_COUNTS

    # Los valores raw exactos se preservan con números de fila de datos 1-based.
    lat_thousands = audit["examples"]["Latitud"]["thousands_separator_candidate"]
    lon_thousands = audit["examples"]["Longitud"]["thousands_separator_candidate"]
    assert {"row": 1, "value": "-2.895.956"} in lat_thousands
    assert {"row": 1, "value": "-79.014.574"} in lon_thousands
    # Primeros candidatos decimales de lat (las filas 10, 18 y 26 son las tres
    # primeras): los valores raw exactos se preservan con sus números de fila.
    lat_decimal = audit["examples"]["Latitud"]["decimal_candidate"]
    assert lat_decimal[:3] == [
        {"row": 10, "value": "-290.709"},
        {"row": 18, "value": "-289.867"},
        {"row": 26, "value": "-290.179"},
    ]
    # '-28.957' (fila 226) está más allá del límite de 20 ejemplos, pero igual
    # se clasifica y se cuenta como candidato decimal.
    assert classify_coordinate_value("-28.957") == "decimal_candidate"
    assert {"row": 75, "value": "-79.0"} in audit["examples"]["Longitud"]["decimal_candidate"]

    # Sin centinela '?' en ninguna columna de coordenadas.
    assert audit["per_column_counts"]["Latitud"]["sentinel"] == 0
    assert audit["per_column_counts"]["Longitud"]["sentinel"] == 0
    assert all(
        "?" not in example["value"]
        for column_examples in audit["examples"].values()
        for category_examples in column_examples.values()
        for example in category_examples
    )

    # Decisión sin resolver; sin conversión, sin geometría.
    assert audit["format_resolved"] is False
    assert audit["decision"] == "format_unresolved"
    assert audit["conversion_justified"] is False
    assert audit["geometry_generated"] is False
    # El contenido de 'Ubicacion' nunca aparece en las partes con datos del
    # artefacto (la palabra solo se usa en la prosa de metodología/evidencia).
    assert "Ubicacion" not in json.dumps(audit["examples"])
    assert "Ubicacion" not in json.dumps(audit["per_column_counts"])
    # La evidencia es repo-relativa para las referencias locales fijas; las
    # rutas del manifest y del raw se registran exactamente como se proveen
    # (absolutas aquí, según la convención de pruebas del repositorio).
    evidence_paths = audit["evidence"]["local_evidence_paths"]
    assert "docs/source-contract.md" in evidence_paths
    assert "src/mobility_reliability/validation/source_snapshot.py" in evidence_paths
    assert "src/mobility_reliability/transformation/snapshot.py" in evidence_paths
    assert all(not path.startswith("/") for path in evidence_paths[2:])


@requires_stops_raw
def test_ejemplos_de_la_auditoria_capturada_limitados_y_sin_el_raw_completo():
    audit = audit_coordinate_formats(STOPS_MANIFEST, RAW_DIR)

    for column_examples in audit["examples"].values():
        for category_examples in column_examples.values():
            assert len(category_examples) <= 20

    # Los 331 valores de lat de miles agrupados conservan solo las primeras 20
    # filas (las filas 10 y 18 son candidatos decimales y no consumen lugares).
    lat_thousands = audit["examples"]["Latitud"]["thousands_separator_candidate"]
    assert len(lat_thousands) == 20
    rows = list(csv.reader(io.StringIO(STOPS_RAW.read_text(encoding="utf-8"))))
    data_rows = rows[1:]
    thousands_rows = [
        index
        for index, row in enumerate(data_rows, start=1)
        if classify_coordinate_value(row[2]) == "thousands_separator_candidate"
    ]
    assert len(thousands_rows) == 331
    assert [example["row"] for example in lat_thousands] == thousands_rows[:20]
    assert lat_thousands[-1]["row"] == thousands_rows[19]

    # El valor 21 de miles agrupados nunca se filtra al artefacto.
    beyond_cap = data_rows[thousands_rows[20] - 1][2]
    dumped = json.dumps(audit)
    assert beyond_cap not in dumped
    assert STOPS_RAW.read_text(encoding="utf-8") not in dumped
