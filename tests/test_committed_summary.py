"""Headline counts pinned against the artifacts committed to the repository.

The raw CKAN captures live under the git-ignored ``data/raw/`` directory, so
most evidence tests are skipped on a clean clone. This module covers the
headline claims that can be checked with committed files only:

- 76 routes and 383 stops from the successful manifests;
- 0 valid coordinate pairs from the committed coordinate audit, which never
  converts or generates geometry;
- 68/76 clean route rows and 0 valid coordinate pairs as frozen in the
  committed source contract (the transformation-derived value cannot be
  recomputed without the raw captures; ``tests/test_captured_snapshots.py``
  verifies it against the raws when they are present).

No raw file, network access or optional dependency is required.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ROUTES_MANIFEST = REPO_ROOT / "data/manifests/rutas-de-transporte-publico/2026-08-02T18-51-08Z.manifest.json"
STOPS_MANIFEST = REPO_ROOT / "data/manifests/paradas-de-transporte-publico/2026-08-02T19-27-36Z.manifest.json"
COORDINATE_AUDIT = REPO_ROOT / "data/quality/coordinate-format-audit.json"
SOURCE_CONTRACT = REPO_ROOT / "docs/source-contract.md"
README = REPO_ROOT / "README.md"

HEADLINE_ROUTE_ROWS = 76
HEADLINE_STOP_ROWS = 383
HEADLINE_CLEAN_ROUTE_ROWS = 68
HEADLINE_VALID_COORDINATE_PAIRS = 0


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_manifests_pin_headline_row_counts() -> None:
    routes = _load_json(ROUTES_MANIFEST)
    stops = _load_json(STOPS_MANIFEST)

    assert routes["status"] == "success"
    assert stops["status"] == "success"
    assert routes["dataset_id"] == "rutas-de-transporte-publico"
    assert stops["dataset_id"] == "paradas-de-transporte-publico"
    assert routes["row_count"] == HEADLINE_ROUTE_ROWS
    assert stops["row_count"] == HEADLINE_STOP_ROWS
    assert routes["resource_id"] == "e55af215-4648-4e3b-84c9-d7e929435008"
    assert stops["resource_id"] == "ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e"
    assert routes["content_hash"].startswith("dc3082ad")
    assert stops["content_hash"].startswith("20969d2e")


def test_committed_coordinate_audit_pins_stop_quality_headline() -> None:
    audit = _load_json(COORDINATE_AUDIT)

    assert audit["row_count"] == HEADLINE_STOP_ROWS
    assert audit["total_coordinate_values"] == HEADLINE_STOP_ROWS * 2
    assert audit["rows_with_any_nonblank"] == HEADLINE_STOP_ROWS
    assert audit["rows_with_both_nonblank"] == HEADLINE_STOP_ROWS
    assert audit["per_column_counts"]["Latitud"]["thousands_separator_candidate"] == 331
    assert audit["per_column_counts"]["Latitud"]["decimal_candidate"] == 52
    assert audit["per_column_counts"]["Longitud"]["thousands_separator_candidate"] == 374
    assert audit["per_column_counts"]["Longitud"]["decimal_candidate"] == 9

    # The audit resolves no format and never converts or emits geometry, so it
    # supports zero simultaneously valid coordinate pairs.
    assert audit["format_resolved"] is False
    assert audit["conversion_justified"] is False
    assert audit["geometry_generated"] is False
    assert audit["decision"] == "format_unresolved"
    assert HEADLINE_VALID_COORDINATE_PAIRS == 0
    for column_counts in audit["per_column_counts"].values():
        assert sum(column_counts.values()) == HEADLINE_STOP_ROWS


def test_committed_contract_and_readme_record_headline_claims() -> None:
    contract = SOURCE_CONTRACT.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    # The transformation-derived 68/76 clean rows are frozen in the committed
    # source contract; the raw-based test verifies them when raws are present.
    assert f"{HEADLINE_CLEAN_ROUTE_ROWS}/{HEADLINE_ROUTE_ROWS} registros limpios" in contract
    assert "0 filas con ambas coordenadas válidas" in contract

    assert f"{HEADLINE_CLEAN_ROUTE_ROWS}/{HEADLINE_ROUTE_ROWS}" in readme
    assert "0 pares de coordenadas simultáneamente válidos" in readme
    assert "(76 filas)" in readme
    assert "(383 filas)" in readme
