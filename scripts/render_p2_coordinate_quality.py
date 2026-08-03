#!/usr/bin/env python3
"""Render docs/assets/p2-coordinate-quality.svg from committed audit data.

Deterministic, stdlib-only generator. Reads ONLY the committed audit
data/quality/coordinate-format-audit.json and writes the SVG byte-identically
for identical input. No network, no wall-clock fields.

The chart shows why the demo produces no map: per-column observational
candidate counts from the audit (categories are the audit's own terms) plus
the repo-documented fact that zero rows have both coordinates valid
(0 valid point pairs, coverage 0.0 — fixed by tests/test_captured_snapshots.py
on the approved stops snapshot and stated in the README quality report).
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT = REPO_ROOT / "data/quality/coordinate-format-audit.json"
OUTPUT = REPO_ROOT / "docs" / "assets" / "p2-coordinate-quality.svg"

WIDTH, HEIGHT = 1100, 620

# Derived evidence, NOT an audit field (README "Transformación canónica",
# asserted by tests/test_captured_snapshots.py): no row has both coordinates valid.
VALID_COORDINATE_PAIRS = 0
VALID_POINT_COVERAGE = 0.0


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def main() -> int:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    counts = audit["per_column_counts"]
    examples = audit["examples"]
    rows = audit["row_count"]
    total_values = audit["total_coordinate_values"]

    lat_invalid = counts["Latitud"]["thousands_separator_candidate"]
    lat_decimal = counts["Latitud"]["decimal_candidate"]
    lon_invalid = counts["Longitud"]["thousands_separator_candidate"]
    lon_decimal = counts["Longitud"]["decimal_candidate"]

    # Grouped stacked bars (two columns, same row scale). Geometry is fixed so every bar top and every numeric label stays inside the 0 0 1100 620 viewBox: the tallest stack (all 383 rows) reaches bar_y_base - max_h = 92 and its label sits at 86, below the classification caption at y=70.
    bar_y_base = 200
    max_h = 108
    def bar_height(count: int) -> float:
        return count / rows * max_h

    bar_w = 120
    x_lat, x_lon = 150, 460
    y_inv_lat = bar_y_base - bar_height(lat_invalid)
    y_dec_lat = y_inv_lat - bar_height(lat_decimal)
    y_inv_lon = bar_y_base - bar_height(lon_invalid)
    y_dec_lon = y_inv_lon - bar_height(lon_decimal)

    bars = (
        f'<rect x="{x_lat}" y="{y_inv_lat:.1f}" width="{bar_w}" height="{bar_height(lat_invalid):.1f}" fill="#f59e0b"><title>Latitud: {lat_invalid} candidatos separador de miles (sintaxis invalida)</title></rect>'
        f'<rect x="{x_lat}" y="{y_dec_lat:.1f}" width="{bar_w}" height="{bar_height(lat_decimal):.1f}" fill="#2563eb"><title>Latitud: {lat_decimal} candidatos decimales (fuera de rango o sin resolver)</title></rect>'
        f'<rect x="{x_lon}" y="{y_inv_lon:.1f}" width="{bar_w}" height="{bar_height(lon_invalid):.1f}" fill="#f59e0b"><title>Longitud: {lon_invalid} candidatos separador de miles (sintaxis invalida)</title></rect>'
        f'<rect x="{x_lon}" y="{y_dec_lon:.1f}" width="{bar_w}" height="{bar_height(lon_decimal):.1f}" fill="#2563eb"><title>Longitud: {lon_decimal} candidatos decimales (fuera de rango o sin resolver)</title></rect>'
    )

    labels = (
        f'<text x="{x_lat + bar_w / 2}" y="{(y_inv_lat + bar_y_base) / 2 + 4:.1f}" font-family="sans-serif" font-size="12" fill="#111827" text-anchor="middle" font-weight="bold">{lat_invalid}</text>'
        f'<text x="{x_lat + bar_w / 2}" y="{y_dec_lat - 6:.1f}" font-family="sans-serif" font-size="12" fill="#111827" text-anchor="middle" font-weight="bold">{lat_decimal}</text>'
        f'<text x="{x_lon + bar_w / 2}" y="{(y_inv_lon + bar_y_base) / 2 + 4:.1f}" font-family="sans-serif" font-size="12" fill="#111827" text-anchor="middle" font-weight="bold">{lon_invalid}</text>'
        f'<text x="{x_lon + bar_w / 2}" y="{y_dec_lon - 6:.1f}" font-family="sans-serif" font-size="12" fill="#111827" text-anchor="middle" font-weight="bold">{lon_decimal}</text>'
        f'<text x="{x_lat + bar_w / 2}" y="{bar_y_base + 22}" font-family="sans-serif" font-size="12.5" fill="#111827" text-anchor="middle" font-weight="bold">Latitud (383)</text>'
        f'<text x="{x_lon + bar_w / 2}" y="{bar_y_base + 22}" font-family="sans-serif" font-size="12.5" fill="#111827" text-anchor="middle" font-weight="bold">Longitud (383)</text>'
    )

    legend_y = bar_y_base + 62
    legend = (
        f'<rect x="150" y="{legend_y - 10}" width="12" height="12" fill="#f59e0b"/>'
        f'<text x="168" y="{legend_y}" font-family="sans-serif" font-size="11" fill="#111827">Candidato separador de miles — sintaxis invalida (ej. -2.895.956)</text>'
        f'<rect x="560" y="{legend_y - 10}" width="12" height="12" fill="#2563eb"/>'
        f'<text x="578" y="{legend_y}" font-family="sans-serif" font-size="11" fill="#111827">Candidato decimal — fuera de rango o sin resolver (ej. -290.709)</text>'
    )

    callout_y = legend_y + 46
    callout = (
        f'<rect x="150" y="{callout_y - 34}" width="800" height="74" fill="#fef3c7" stroke="#f59e0b" stroke-width="1"/>'
        f'<text x="170" y="{callout_y}" font-family="sans-serif" font-size="17" font-weight="bold" fill="#111827">Pares de coordenadas simultaneamente validos: {VALID_COORDINATE_PAIRS}</text>'
        f'<text x="170" y="{callout_y + 20}" font-family="sans-serif" font-size="11.5" fill="#374151">Evidencia derivada, no un campo del artefacto de auditoria: las {audit["rows_with_both_nonblank"]} filas tienen ambas columnas no vacias.</text>'
            f'<text x="170" y="{callout_y + 40}" font-family="sans-serif" font-size="11.5" fill="#374151">pero ninguna las tiene ambas validas (fijado por tests/test_captured_snapshots.py; cobertura de puntos {VALID_POINT_COVERAGE:.1f}).</text>'
    )

    decision_y = callout_y + 56
    decision = (
        f'<text x="150" y="{decision_y}" font-family="sans-serif" font-size="13" font-weight="bold" fill="#111827">Decision de auditoria: format_unresolved → la demo NO muestra mapa</text>'
        f'<text x="150" y="{decision_y + 18}" font-family="sans-serif" font-size="11" fill="#374151">conversion_justified: false · geometry_generated: false · los valores nunca se corrigen ni se reinterpretan (sin CRS, sin orden de ejes, sin conversion)</text>'
    )

    examples_y = decision_y + 48
    ex = (
        f'<text x="150" y="{examples_y}" font-family="sans-serif" font-size="11.5" font-weight="bold" fill="#4b5563">Ejemplos raw exactos del auditoria:</text>'
        f'<text x="150" y="{examples_y + 18}" font-family="monospace" font-size="10.5" fill="#6b7280">Latitud  -2.895.956 (separador de miles)  ·  Latitud  -290.709 (decimal fuera de rango)  ·  Longitud  -79.0 (decimal)</text>'
    )

    footer = [
        f"snapshot: {audit['snapshot_id']} | resource: {audit['resource_id']} | rows: {audit['row_count']}",
        f"raw_sha256: {audit['raw_sha256']} | total_coordinate_values: {total_values} | columns: Latitud, Longitud",
        "license declared: CC BY-NC 2.0 (cc-nc) | source: Cuenca en Datos (GAD Cuenca)",
        "method: textual classification only, deterministic precedence; candidates are observational, never interpreted",
        "guardrail: sin mapa, sin puntualidad/AVL/GTFS-Realtime/clima, sin cobertura geografica, coordenadas nunca corregidas",
    ]
    footer_lines = "".join(
        f'<text x="20" y="{HEIGHT - 92 + i * 14}" font-family="monospace" font-size="9.5" fill="#374151">{esc(line)}</text>'
        for i, line in enumerate(footer)
    )

    metadata = {
        "generator": "scripts/render_p2_coordinate_quality.py",
        "input_file": "data/quality/coordinate-format-audit.json",
        "schema_version": audit["schema_version"],
        "decision": audit["decision"],
        "format_resolved": audit["format_resolved"],
        "conversion_justified": audit["conversion_justified"],
        "geometry_generated": audit["geometry_generated"],
        "valid_coordinate_pairs": VALID_COORDINATE_PAIRS,
        "valid_coordinate_pairs_provenance": "derived evidence, not a field of coordinate-format-audit.json: asserted by tests/test_captured_snapshots.py on the approved stops snapshot; stated in README quality report",
        "deterministic": True,
        "no_raw_values_beyond_audit_examples": True,
    }

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}"><rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/><title>Auditoria de formato de coordenadas - paradas de transporte publico de Cuenca</title><text x="20" y="24" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">Auditoria de formato de coordenadas - paradas de transporte publico de Cuenca</text><text x="20" y="42" font-family="sans-serif" font-size="11" fill="#4b5563">383 filas · {total_values} valores auditados (Latitud 383 · Longitud 383) · snapshot {esc(audit["snapshot_id"].split("@")[1])}</text>
<text x="150" y="70" font-family="sans-serif" font-size="11.5" fill="#374151">Clasificacion textual observacional por columna (categorias del propio artefacto de auditoria):</text>
{bars}
{labels}
{legend}
{callout}
{decision}
{ex}
{footer_lines}
<metadata>{esc(json.dumps(metadata, ensure_ascii=True, sort_keys=True))}</metadata></svg>"""

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
