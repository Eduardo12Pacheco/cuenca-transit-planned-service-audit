"""Fixtures sintéticos compartidos para las pruebas de validación y transformación.

Todas las fixtures son manifests/raw pequeños derivados de filas capturadas (los
archivos raw ignorados por Git nunca se copian a fixtures versionadas). ``write_snapshot``
escribe un par raw + manifest bajo un directorio temporal y devuelve sus rutas;
cada prueba fail-closed modifica el manifest o el raw devuelto para construir un
defecto estructural específico.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mobility_reliability.ingestion.ckan_snapshot import (
    CKAN_PACKAGE_SHOW_URLS,
    DATASET_SPECS,
)

ROUTES_DATASET_ID = "rutas-de-transporte-publico"
STOPS_DATASET_ID = "paradas-de-transporte-publico"

LICENSE_DECLARED = "CC BY-NC 2.0"
LICENSE_ID_APPROVED = "cc-nc"
LICENSE_URL_APPROVED = "http://creativecommons.org/licenses/by-nc/2.0/"

# CSV sintético pequeño de rutas derivado de filas capturadas: las dos filas son
# las filas reales capturadas para las líneas 1 (IDA) y 21 (IDA; sin servicio los
# fines de semana).
ROUTES_RAW_TWO_ROWS = (
    "LINEA,COMPANIA,SENTIDO,ORIGEN,DESTINO,"
    "LUNES_VIERNES_INICIO,LUNES_VIERNES_FIN,LUNES_VIERNES_INTERVALO,"
    "SABADOS_INICIO,SABADOS_FIN,SABADOS_INTERVALO,"
    "DOMINGOS_INICIO,DOMINGOS_FIN,DOMINGOS_INTERVALO\n"
    "1,SIT,IDA,LIRIO,KENNEDY,5:50,21:15,0:09,5:50,20:30,0:12,6:00,20:00,0:15\n"
    "21,URBA10,IDA,TARQUI,VADO,5:40,19:40,0:30,0:00,0:00,0:00,0:00,0:00,0:00\n"
)


def write_snapshot(
    tmp_path: Path,
    *,
    dataset_id: str = ROUTES_DATASET_ID,
    raw_text: str = ROUTES_RAW_TWO_ROWS,
    resource_id: str = "e55af215-4648-4e3b-84c9-d7e929435008",
    resource_name: str = "GADCuenca_RutasTransporte_2025Marzo.csv",
    raw_file: str | None = None,
    row_count: int | None = None,
    **manifest_overrides,
) -> tuple[Path, Path, Path]:
    """Escribe una fixture raw + manifest bajo tmp_path y devuelve (raw, manifest, raw_dir)."""
    raw_dir = tmp_path / "raw"
    manifest_dir = tmp_path / "manifests"
    # Las dos capturas aprobadas se recopilaron con marcas de tiempo distintas;
    # las fixtures conservan esas mismas marcas que las capturas reales para
    # mantener la autenticidad de la prueba.
    stamp = "2026-08-02T19-27-36Z" if dataset_id == STOPS_DATASET_ID else "2026-08-02T18-51-08Z"
    collection_timestamp_utc = (
        "2026-08-02T19:27:36Z" if dataset_id == STOPS_DATASET_ID else "2026-08-02T18:51:08Z"
    )
    if raw_file is None:
        raw_file = f"{dataset_id}/{stamp}.json"
    raw_bytes = raw_text.encode("utf-8")
    raw_path = raw_dir / raw_file
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw_bytes)
    if row_count is None:
        data_rows = [line for line in raw_text.splitlines()[1:] if line.strip()]
        row_count = len(data_rows)

    source_url = CKAN_PACKAGE_SHOW_URLS[dataset_id]
    manifest = {
        "snapshot_id": f"{dataset_id}@{stamp}",
        "source_id": DATASET_SPECS[dataset_id]["source_id"],
        "dataset_id": dataset_id,
        "collection_timestamp_utc": collection_timestamp_utc,
        "source_published_at": "2025-04-01T20:57:30.236543",
        "source_url": source_url,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "resource_url": "https://fixtures.invalid/resource.csv",
        "resource_format": "CSV",
        "license_declared": LICENSE_DECLARED,
        "license_published": "Creative Commons Non-Commercial (Cualquiera)",
        "license_id": LICENSE_ID_APPROVED,
        "license_url": LICENSE_URL_APPROVED,
        "isopen": False,
        "restrictions": ["NonCommercial"],
        "attribution": "GAD Municipal del cantón Cuenca",
        "content_hash": hashlib.sha256(raw_bytes).hexdigest(),
        "raw_file": raw_file,
        "row_count": row_count,
        "status": "success",
        "schema_version": 1,
        "retrieval_method": "public documented CKAN API",
        "warnings": [],
        "notes": "",
        "resource": {
            "id": resource_id,
            "name": resource_name,
            "format": "CSV",
            "url": "https://fixtures.invalid/resource.csv",
            "description": "Rutas de transporte público con corte a marzo del 2025",
            "created": "2025-04-01T20:12:35.950235",
            "last_modified": "2025-04-01T20:24:50.630382",
            "metadata_modified": "2025-04-01T20:40:43.075903",
        },
        "source_metadata": {
            "id": f"pkg-{dataset_id}",
            "name": dataset_id,
            "title": "Fixture dataset",
            "metadata_modified": "2025-04-01T20:57:30.236543",
            "resources": [
                {
                    "id": resource_id,
                    "name": resource_name,
                    "format": "CSV",
                    "url": "https://fixtures.invalid/resource.csv",
                }
            ],
        },
    }
    manifest.update(manifest_overrides)
    manifest_path = manifest_dir / dataset_id / f"{stamp}.manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return raw_path, manifest_path, raw_dir
