"""Pruebas de contrato de la validación estricta de snapshots de fuente.

API pública bajo prueba
-----------------------
- ``mobility_reliability.validation.validate_source_snapshot(manifest_path, raw_dir)``
- ``mobility_reliability.validation.SnapshotValidationError``
- ``mobility_reliability.validation.SourceSnapshot``

Semántica bajo prueba
---------------------
- Los fallos estructurales de provenance LANZAN ``SnapshotValidationError``
  (fail closed): manifest que no es un objeto JSON, status distinto de
  ``success``, campos obligatorios ausentes/vacíos, URL de dataset/fuente no
  aprobada, metadatos de resource inconsistentes, huella de licencia distinta
  (``license_id=cc-nc`` más la URL oficial CC BY-NC 2.0), marcas de tiempo UTC
  de recopilación inválidas, ``schema_version`` inválida, ``raw_file``
  absoluto/con traversal/ausente, SHA-256 malformado o que no coincide,
  UTF-8/CSV inválido, filas CSV desalineadas (ragged) y desajuste de
  ``row_count`` contra las filas de datos del CSV.
- El resource seleccionado debe ser CSV y no geométrico: los formatos ZIP/ODS
  y los resources que identifican datos geometry/recorrido/geoespaciales se
  rechazan.
- Se verifican la atribución y el ID del resource; la proyección de resource
  de nivel superior debe coincidir con los metadatos anidados ``resource``.
- En caso de éxito la función devuelve un ``SourceSnapshot`` con la proyección
  ``source_snapshot`` compatible con JSON (``as_dict()``) más el manifest, la
  ruta raw, el encabezado CSV y las filas raw analizadas que necesitan las
  transformaciones.

Todos los fixtures son manifests/raws sintéticos pequeños derivados de las
filas capturadas; no ocurre ninguna captura real ni acceso a red.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from capture_fixtures import (
    LICENSE_ID_APPROVED,
    LICENSE_URL_APPROVED,
    ROUTES_DATASET_ID,
    STOPS_DATASET_ID,
    write_snapshot,
)

from mobility_reliability.ingestion.ckan_snapshot import (
    CKAN_PACKAGE_SHOW_URLS,
)
from mobility_reliability.validation import (
    SnapshotValidationError,
    SourceSnapshot,
    validate_source_snapshot,
)

# ---------------------------------------------------------------------------
# Camino feliz
# ---------------------------------------------------------------------------


def test_valida_snapshot_aprobado_de_rutas_y_devuelve_la_proyeccion(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)

    snapshot = validate_source_snapshot(manifest_path, raw_dir)

    assert isinstance(snapshot, SourceSnapshot)
    assert snapshot.snapshot_id == "rutas-de-transporte-publico@2026-08-02T18-51-08Z"
    assert snapshot.dataset_id == ROUTES_DATASET_ID
    assert snapshot.source_url == CKAN_PACKAGE_SHOW_URLS[ROUTES_DATASET_ID]
    assert snapshot.resource_id == "e55af215-4648-4e3b-84c9-d7e929435008"
    assert snapshot.license_id == LICENSE_ID_APPROVED
    assert snapshot.license_url == LICENSE_URL_APPROVED
    assert snapshot.row_count == 2
    assert snapshot.status == "success"
    assert snapshot.schema_version == 1
    # La proyección es compatible con JSON.
    projection = snapshot.as_dict()
    json.dumps(projection)
    assert projection["snapshot_id"] == snapshot.snapshot_id
    assert projection["resource_cutoff"]["created"] == "2025-04-01T20:12:35.950235"


def test_snapshot_validado_lleva_manifest_raw_y_filas_para_transformaciones(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)

    snapshot = validate_source_snapshot(manifest_path, raw_dir)

    assert snapshot.manifest["status"] == "success"
    assert snapshot.raw_path == raw_dir / snapshot.raw_file
    assert snapshot.header == tuple(
        [
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
    )
    assert len(snapshot.rows) == 2
    assert snapshot.rows[0]["LINEA"] == "1"
    assert snapshot.rows[1]["DOMINGOS_INTERVALO"] == "0:00"


def test_valida_snapshot_aprobado_de_paradas(tmp_path):
    stops_raw = (
        "N,Ubicacion,Latitud,Longitud,Paleta\n"
        "1,AV 3 DE NOVIEMBRE INTERSECCION RAMON BORRERO,-2.895.956,-79.014.574,SI\n"
    )
    _, manifest_path, raw_dir = write_snapshot(
        tmp_path,
        dataset_id=STOPS_DATASET_ID,
        raw_text=stops_raw,
        resource_id="ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e",
        resource_name="GADCuenca_ParadasTransporte_2025Abril.csv",
        row_count=1,
    )

    snapshot = validate_source_snapshot(manifest_path, raw_dir)

    assert snapshot.dataset_id == STOPS_DATASET_ID
    assert snapshot.source_url == CKAN_PACKAGE_SHOW_URLS[STOPS_DATASET_ID]
    assert snapshot.rows[0]["N"] == "1"


# ---------------------------------------------------------------------------
# Fail closed: los fallos estructurales de provenance lanzan SnapshotValidationError
# ---------------------------------------------------------------------------


def test_falta_el_archivo_manifest_y_lanza_error(tmp_path):
    _, _, raw_dir = write_snapshot(tmp_path)
    missing = tmp_path / "manifests" / ROUTES_DATASET_ID / "missing.manifest.json"

    with pytest.raises(SnapshotValidationError, match="manifest"):
        validate_source_snapshot(missing, raw_dir)


@pytest.mark.parametrize("payload", ["[]", '"not an object"', "null", "42"], ids=["lista", "cadena", "nulo", "numero"])
def test_manifest_no_es_objeto_json_y_lanza_error(tmp_path, payload):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest_path.write_text(payload, encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="objeto JSON"):
        validate_source_snapshot(manifest_path, raw_dir)


@pytest.mark.parametrize("status", ["partial", "failed"])
def test_status_distinto_de_success_lanza_error(tmp_path, status):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    raw_bytes = manifest_path.read_bytes()
    manifest = json.loads(raw_bytes)
    manifest["status"] = status
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match=status):
        validate_source_snapshot(manifest_path, raw_dir)


@pytest.mark.parametrize(
    "field",
    [
        "snapshot_id",
        "source_id",
        "dataset_id",
        "source_url",
        "resource_id",
        "resource_name",
        "resource_url",
        "resource_format",
        "license_declared",
        "license_id",
        "license_url",
        "attribution",
        "content_hash",
        "raw_file",
        "collection_timestamp_utc",
    ],
    ids=lambda f: f.replace("_", "-"),
)
def test_falta_un_campo_obligatorio_y_lanza_error(tmp_path, field):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = None
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match=field):
        validate_source_snapshot(manifest_path, raw_dir)


def test_campo_obligatorio_vacio_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["attribution"] = "   "
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="attribution"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_source_url_no_aprobada_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_url"] = "https://example.invalid/package_show?id=other"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="source_url"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_desajuste_de_source_url_del_dataset_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # dataset_id indica rutas pero source_url apunta al paquete de paradas.
    manifest["source_url"] = CKAN_PACKAGE_SHOW_URLS[STOPS_DATASET_ID]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="source_url"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_dataset_id_desconocido_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dataset_id"] = "recorrido-de-las-rutas-de-transporte-publico"
    manifest["source_url"] = "https://fixtures.invalid/recorrido"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="dataset_id"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_desajuste_de_source_id_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_id"] = "some-other-source"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="source_id"):
        validate_source_snapshot(manifest_path, raw_dir)


@pytest.mark.parametrize(
    "overrides",
    [
        {"license_id": "cc-by"},
        {"license_url": "https://creativecommons.org/licenses/by/4.0/"},
        {"license_url": None},
        {"license_declared": "CC BY 4.0"},
    ],
    ids=["id-incorrecto", "url-incorrecta", "url-ausente", "declaracion-incorrecta"],
)
def test_desajuste_de_huella_de_licencia_lanza_error(tmp_path, overrides):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(overrides)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="license"):
        validate_source_snapshot(manifest_path, raw_dir)


@pytest.mark.parametrize(
    "collection_timestamp_utc",
    ["2026-08-02T18:51:08", "2026-08-02T18:51:08+05:00", "not-a-timestamp", "2026-13-99T99:99:99Z"],
    ids=["ingenua", "offset-incorrecto", "basura", "imposible"],
)
def test_collection_timestamp_utc_invalida_lanza_error(tmp_path, collection_timestamp_utc):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["collection_timestamp_utc"] = collection_timestamp_utc
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="collection_timestamp_utc"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_source_published_at_invalido_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_published_at"] = "yesterday-ish"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="source_published_at"):
        validate_source_snapshot(manifest_path, raw_dir)


@pytest.mark.parametrize("value", [None, "", "   "], ids=["nulo", "vacio", "en-blanco"])
def test_source_published_at_vacio_o_ausente_lanza_error(tmp_path, value):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if value is None:
        del manifest["source_published_at"]
    else:
        manifest["source_published_at"] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="source_published_at"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_se_acepta_source_published_at_ingenua(tmp_path):
    # El portal publica metadata_modified sin zona horaria; se acepta la forma
    # ISO ingenua para source_published_at mientras collection_timestamp_utc
    # sigue siendo UTC estricto.
    _, manifest_path, raw_dir = write_snapshot(tmp_path)

    snapshot = validate_source_snapshot(manifest_path, raw_dir)

    assert snapshot.source_published_at == "2025-04-01T20:57:30.236543"


# ---------------------------------------------------------------------------
# Fail closed: consistencia de los metadatos del paquete (source_metadata)
# ---------------------------------------------------------------------------


def test_source_metadata_ausente_o_no_objeto_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_metadata"] = None
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="source_metadata"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_desajuste_de_identidad_de_dataset_en_source_metadata_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_metadata"]["name"] = "some-other-dataset"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="source_metadata"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_source_metadata_resources_sin_el_recurso_seleccionado_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_metadata"]["resources"] = [{"id": "some-other-resource"}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="source_metadata"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_source_metadata_resources_no_es_una_lista_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_metadata"]["resources"] = "not-a-list"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="source_metadata"):
        validate_source_snapshot(manifest_path, raw_dir)


@pytest.mark.parametrize("schema_version", [0, -1, "1", True, None])
def test_schema_version_invalida_lanza_error(tmp_path, schema_version):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = schema_version
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="schema_version"):
        validate_source_snapshot(manifest_path, raw_dir)


@pytest.mark.parametrize(
    "raw_file",
    ["/etc/passwd", "../escape.json", "other/../../escape.json", ""],
    ids=["absoluta", "traversal", "traversal-anidada", "vacia"],
)
def test_raw_file_inseguro_lanza_error(tmp_path, raw_file):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["raw_file"] = raw_file
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="raw_file"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_falta_el_archivo_raw_y_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    (tmp_path / "raw" / ROUTES_DATASET_ID / "2026-08-02T18-51-08Z.json").unlink()

    with pytest.raises(SnapshotValidationError, match="raw"):
        validate_source_snapshot(manifest_path, raw_dir)


@pytest.mark.parametrize(
    "content_hash",
    ["abc", "Z" * 64, "ab" * 31 + "xy"],
    ids=["corto", "no-hex", "hex-no-minusculas"],
)
def test_content_hash_malformado_lanza_error(tmp_path, content_hash):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content_hash"] = content_hash
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="content_hash"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_desajuste_de_content_hash_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content_hash"] = hashlib.sha256(b"different bytes").hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="content_hash"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_raw_con_utf8_invalido_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    raw_path = tmp_path / "raw" / ROUTES_DATASET_ID / "2026-08-02T18-51-08Z.json"
    bad_bytes = b"LINEA,COMPANIA\n1,\xff\xfe broken\n"
    raw_path.write_bytes(bad_bytes)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content_hash"] = hashlib.sha256(bad_bytes).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="UTF-8"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_filas_csv_desalineadas_lanzan_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    raw_path = tmp_path / "raw" / ROUTES_DATASET_ID / "2026-08-02T18-51-08Z.json"
    ragged = "LINEA,COMPANIA,SENTIDO\n1,SIT,IDA,EXTRA\n"
    raw_path.write_bytes(ragged.encode("utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content_hash"] = hashlib.sha256(ragged.encode("utf-8")).hexdigest()
    manifest["row_count"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="CSV"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_desajuste_de_row_count_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["row_count"] = 99  # el raw tiene 2 filas de datos
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="row_count"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_se_rechaza_recurso_de_geometria(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(
        tmp_path,
        resource_id="5643def7-6f5e-40c8-b942-6c5f6c6f21fb",
        resource_name="GADCuenca_RutasTransporteGeo_2022Septiembre.zip",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resource"]["name"] = "GADCuenca_RutasTransporteGeo_2022Septiembre.zip"
    manifest["resource"]["format"] = "ZIP"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="(geometry|CSV|format)"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_se_rechaza_recurso_en_formato_zip(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resource_format"] = "ZIP"
    manifest["resource"]["format"] = "ZIP"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="CSV"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_se_rechaza_descripcion_recorrido(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resource"]["description"] = "Recorrido (geometría) de rutas con corte a abril"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="geometry"):
        validate_source_snapshot(manifest_path, raw_dir)


@pytest.mark.parametrize(
    "overrides",
    [
        {"resource_id": "different-id"},
        {"resource_name": "different-name.csv"},
        {"resource_format": "JSON"},
        {"resource_url": "https://fixtures.invalid/different.csv"},
    ],
    ids=["desajuste-id", "desajuste-name", "desajuste-format", "desajuste-url"],
)
def test_metadatos_de_resource_inconsistentes_lanzan_error(tmp_path, overrides):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(overrides)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="resource"):
        validate_source_snapshot(manifest_path, raw_dir)


def test_falta_el_objeto_resource_y_lanza_error(tmp_path):
    _, manifest_path, raw_dir = write_snapshot(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resource"] = None
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="resource"):
        validate_source_snapshot(manifest_path, raw_dir)
