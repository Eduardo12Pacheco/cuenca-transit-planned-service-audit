"""Auditoría sin conexión del formato de coordenadas de la captura de paradas aprobada.

Este módulo clasifica los valores raw exactos de ``Latitud``/``Longitud`` del
snapshot de paradas aprobado en categorías textuales observacionales. Nunca
convierte, nunca interpreta CRS/orden de ejes/WGS84/UTM/DMS, nunca usa
``Ubicacion`` y nunca genera geometría.

Contrato
--------
- VALIDACIÓN ESTRUCTURAL PRIMERO: ``audit_coordinate_formats`` llama a
  ``validate_source_snapshot`` y propaga ``SnapshotValidationError`` ante
  cualquier inconsistencia manifest/raw (fail closed). Además falla cerrado con
  ``CoordinateAuditError`` cuando el snapshot no es la captura de paradas
  aprobada (dataset ``paradas-de-transporte-publico``, resource
  ``ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e``) o cuando ``Latitud``/``Longitud``
  están ausentes del encabezado raw.
- CLASIFICACIÓN SOLO TEXTUAL: cada valor raw exacto se clasifica en exactamente
  una de ``COORDINATE_CATEGORIES`` con la precedencia determinista documentada
  (ver ``classify_coordinate_value``). Las categorías son candidatas y
  observacionales: nunca se afirma que los numerales agrupados *sean*
  separadores de miles, nunca se afirma que una coma *sea* un separador
  decimal, y las formas DMS/WKT solo se reconocen cuando son obvias.
- EJEMPLOS: como máximo 20 por categoría por columna, cada uno ``{"row",
  "value"}`` con el número de fila de datos 1-based y el valor raw exacto
  (espacio preservado). El artefacto nunca contiene el raw completo.
- GUARDA DE CONVERSIÓN: ``convert_coordinate_value`` siempre lanza
  ``CoordinateConversionError`` porque ninguna evidencia local prueba el
  formato de origen, el orden de ejes, el CRS o una conversión segura.
- DECISIÓN: la auditoría siempre reporta ``format_resolved: false`` /
  ``decision: format_unresolved`` / ``conversion_justified: false`` /
  ``geometry_generated: false`` para este snapshot. Una revisión futura que
  agregue evidencia local (p. ej. el diccionario de datos ODS oficial) debe
  actualizar este contrato antes de cambiar la decisión.

Los dos escritores de artefactos producen ``data/quality/coordinate-format-audit.json``
(JSON UTF-8) y ``docs/coordinate-quality-audit.md`` (Markdown orientado al
lector, decisión primero).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from mobility_reliability.validation import validate_source_snapshot

__all__ = [
    "APPROVED_STOPS_DATASET_ID",
    "APPROVED_STOPS_RESOURCE_ID",
    "COORDINATE_CATEGORIES",
    "COORDINATE_COLUMNS",
    "CoordinateAuditError",
    "CoordinateConversionError",
    "MAX_EXAMPLES_PER_CATEGORY",
    "audit_coordinate_formats",
    "classify_coordinate_value",
    "convert_coordinate_value",
    "render_coordinate_audit_markdown",
    "write_coordinate_audit_artifacts",
]

# La auditoría está fijada a la captura de paradas aprobada (CSV 2025Abril).
# Cualquier otro dataset o resource falla cerrado: esta auditoría debe
# re-fijarse explícitamente en el contrato antes de poder ejecutarse sobre
# otra captura.
APPROVED_STOPS_DATASET_ID = "paradas-de-transporte-publico"
APPROVED_STOPS_RESOURCE_ID = "ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e"

COORDINATE_COLUMNS = ("Latitud", "Longitud")
MAX_EXAMPLES_PER_CATEGORY = 20

# Cada resultado de clasificación. El orden también es el orden usado en los
# conteos por columna y en el reporte Markdown.
COORDINATE_CATEGORIES = (
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

# Numerales agrupados canónicos: 2+ separadores de punto/comma con cada grupo
# de exactamente tres dígitos (p. ej. "-2.895.956", "2,895,956"). Solo
# candidato: la auditoría nunca afirma qué significan los separadores.
_GROUPED_THOUSANDS_RE = re.compile(r"^-?\d{1,3}(?:[.,]\d{3}){2,}$", re.ASCII)
# Una sola coma como separador decimal (p. ej. "-2,895956").
_SINGLE_COMMA_DECIMAL_RE = re.compile(r"^-?\d+,\d+$", re.ASCII)
# Sintaxis estricta decimal con punto: entero con signo opcional o decimal de
# un solo punto (refleja la sintaxis de coordenadas de la capa de
# transformación).
_STRICT_DOT_DECIMAL_RE = re.compile(r"^-?\d+(?:\.\d+)?$", re.ASCII)
# Palabras clave obvias de WKT/geometría. Se revisan antes que los patrones
# DMS/numéricos para que texto mixto como "POINT(-2.895.956 -79.014.574)"
# nunca se lea como numerales.
_WKT_KEYWORDS = (
    "POINT",
    "MULTIPOINT",
    "LINESTRING",
    "MULTILINESTRING",
    "POLYGON",
    "MULTIPOLYGON",
    "GEOMETRYCOLLECTION",
    "GEOMETRY COLLECTION",
)
# Texto obvio de WKT/geometría: una palabra clave de geometría (opcionalmente
# después de un prefijo SRID=\d+;) seguida inmediatamente de '(' con espacio
# opcional. Exigir el límite '(' mantiene palabras comunes como "POINTLESS"
# fuera de la categoría WKT.
_WKT_RE = re.compile(
    r"^(?:SRID=\d+;)?\s*(?:"
    + "|".join(re.escape(keyword) for keyword in _WKT_KEYWORDS)
    + r")\s*\(",
    re.IGNORECASE,
)
_DEGREE_MARKERS = ("°", "º")
# Notación obvia de hemisferio DMS: un dígito (más comillas opcionales)
# directamente antes de una letra final N/S/E/W. Anclar a un dígito mantiene
# palabras comunes como "no disponible" (que terminan en 'e'/'w') fuera de la
# categoría DMS.
_HEMISPHERE_RE = re.compile(r"\d\s*[\"'\u2032\u2033]?\s*[NSEWnsew]\s*$")


class CoordinateAuditError(Exception):
    """Se lanza cuando la auditoría no puede ejecutarse sobre el snapshot dado (fail closed)."""


class CoordinateConversionError(Exception):
    """Se lanza cuando se solicita una conversión de coordenadas sin evidencia.

    Ninguna evidencia local prueba el formato de origen, el orden de ejes, el
    CRS o una conversión segura, por lo que la conversión se rechaza
    incondicionalmente (fail closed).
    """


def classify_coordinate_value(value: object) -> str:
    """Clasifica determinísticamente un valor raw de coordenadas en una categoría.

    Clasificación solo textual; el valor nunca se convierte ni se interpreta.
    El espacio se recorta para clasificar, pero los llamadores preservan el
    valor raw exacto para el reporte.

    Precedencia determinista (gana la primera coincidencia):
    1. ``blank`` — vacío o solo espacios.
    2. ``sentinel`` — el valor recortado es exactamente ``?`` (nunca una
       coordenada).
    3. ``wkt_or_geometry_candidate`` — texto obvio de WKT/geometría: una
       palabra clave de geometría seguida de ``(`` (se permite espacio
       opcional), opcionalmente después de un prefijo ``SRID=<n>;``. Se
       revisa antes de DMS/numérico para que los payloads WKT nunca se lean
       como numerales; palabras comunes como ``POINTLESS`` no son WKT.
    4. ``thousands_separator_candidate`` — numerales agrupados canónicos:
       2+ separadores de punto/comma con cada grupo de exactamente tres
       dígitos. Solo candidato; el significado del separador nunca se
       afirma.
    5. ``decimal_comma_candidate`` — una sola coma como separador decimal.
    6. ``decimal_candidate`` — sintaxis estricta decimal con punto (entero
       con signo opcional o decimal de un solo punto).
    7. ``dms_candidate`` — marcadores DMS obvios: un símbolo de grado, o
       una letra de hemisferio N/S/E/W anclada a un dígito (p. ej.
       ``-79.014.574W``).
    8. ``other_text`` — texto no vacío residual que contiene una letra.
    9. ``unknown`` — valores no vacíos residuales que no coinciden con
       ningún patrón reconocido (solo puntuación, grupos de numerales
       malformados, no-cadenas).
    """
    if not isinstance(value, str):
        return "unknown"
    text = value.strip()
    if not text:
        return "blank"
    if text == "?":
        return "sentinel"
    if _WKT_RE.match(text):
        return "wkt_or_geometry_candidate"
    if _GROUPED_THOUSANDS_RE.fullmatch(text):
        return "thousands_separator_candidate"
    if _SINGLE_COMMA_DECIMAL_RE.fullmatch(text):
        return "decimal_comma_candidate"
    if _STRICT_DOT_DECIMAL_RE.fullmatch(text):
        return "decimal_candidate"
    if any(marker in text for marker in _DEGREE_MARKERS) or _HEMISPHERE_RE.search(text):
        return "dms_candidate"
    if any(char.isalpha() for char in text):
        return "other_text"
    return "unknown"


def convert_coordinate_value(value: object) -> None:
    """Rechaza cualquier conversión de coordenadas: ninguna evidencia local la justifica.

    Siempre lanza ``CoordinateConversionError``. Ninguna evidencia local
    prueba el formato de origen, el orden de ejes, el CRS o una conversión
    segura para los valores capturados de ``Latitud``/``Longitud``, por lo
    que la conversión se rechaza incondicionalmente (fail closed) y nunca se
    produce ningún resultado.
    """
    raise CoordinateConversionError(
        f"conversión de coordenadas rechazada para {value!r}: ninguna evidencia local "
        "prueba el formato de origen, el orden de ejes, el CRS o una conversión segura"
    )


def audit_coordinate_formats(manifest_path: str | Path, raw_dir: str | Path) -> dict:
    """Audita los formatos raw exactos de coordenadas de la captura de paradas aprobada.

    Lee solo el manifest/raw local de paradas exitoso a través de
    ``validate_source_snapshot`` (cualquier inconsistencia estructural propaga
    ``SnapshotValidationError``) y falla cerrado con ``CoordinateAuditError``
    cuando el snapshot no es la captura de paradas aprobada o falta una columna
    de coordenadas.

    Devuelve un dict compatible con JSON con ``snapshot_id``, ``dataset_id``,
    ``resource_id``, ``raw_file``, ``raw_sha256`` (el hash de la validación
    estructural), ``row_count``, ``columns_audited``,
    ``total_coordinate_values``, ``rows_with_any_nonblank``/
    ``rows_with_both_nonblank``, conteos por columna para cada
    ``COORDINATE_CATEGORIES``, ejemplos limitados (valor raw exacto + número de
    fila de datos 1-based), ``format_resolved: false``,
    ``decision: "format_unresolved"``, ``conversion_justified: false``,
    ``geometry_generated: false``, ``methodology``, ``evidence`` (campos
    auditados, rutas de evidencia local y los campos de metadatos del
    manifest/resource inspeccionados) y ``recommendation``. Nunca se emiten
    geometría ni resultados de conversión; el raw completo nunca se incluye.

    ``manifest_path``/``raw_dir`` se registran en ``evidence.local_evidence_paths``
    exactamente como se proveen (pase rutas repo-relativas para artefactos
    repo-relativos).
    """
    snapshot = validate_source_snapshot(manifest_path, raw_dir)

    problems: list[str] = []
    if snapshot.dataset_id != APPROVED_STOPS_DATASET_ID:
        problems.append(
            f"el dataset {snapshot.dataset_id!r} no es el dataset de paradas aprobado "
            f"{APPROVED_STOPS_DATASET_ID!r}; la auditoría de formato de coordenadas está "
            "fijada a la captura de paradas aprobada"
        )
    if snapshot.resource_id != APPROVED_STOPS_RESOURCE_ID:
        problems.append(
            f"el resource {snapshot.resource_id!r} no es el CSV de paradas aprobado "
            f"(resource {APPROVED_STOPS_RESOURCE_ID!r})"
        )
    missing_columns = [column for column in COORDINATE_COLUMNS if column not in snapshot.header]
    if missing_columns:
        problems.append(
            "faltan columna(s) de coordenadas requerida(s) en el encabezado raw: "
            + ", ".join(missing_columns)
        )
    if problems:
        raise CoordinateAuditError(
            "la auditoría de formato de coordenadas falló cerrada (fail closed):\n- "
            + "\n- ".join(problems)
        )

    counts = {
        column: {category: 0 for category in COORDINATE_CATEGORIES}
        for column in COORDINATE_COLUMNS
    }
    examples = {
        column: {category: [] for category in COORDINATE_CATEGORIES}
        for column in COORDINATE_COLUMNS
    }
    rows_with_any_nonblank = 0
    rows_with_both_nonblank = 0
    for row_index, row in enumerate(snapshot.rows, start=1):
        values = [row.get(column, "") for column in COORDINATE_COLUMNS]
        nonblank = [value for value in values if value.strip()]
        if nonblank:
            rows_with_any_nonblank += 1
        if len(nonblank) == len(COORDINATE_COLUMNS):
            rows_with_both_nonblank += 1
        for column, value in zip(COORDINATE_COLUMNS, values):
            category = classify_coordinate_value(value)
            counts[column][category] += 1
            if len(examples[column][category]) < MAX_EXAMPLES_PER_CATEGORY:
                examples[column][category].append({"row": row_index, "value": value})

    return {
        "name": "coordinate-format-audit",
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "dataset_id": snapshot.dataset_id,
        "resource_id": snapshot.resource_id,
        "raw_file": snapshot.raw_file,
        "raw_sha256": snapshot.content_hash,
        "row_count": snapshot.row_count,
        "columns_audited": list(COORDINATE_COLUMNS),
        "total_coordinate_values": snapshot.row_count * len(COORDINATE_COLUMNS),
        "rows_with_any_nonblank": rows_with_any_nonblank,
        "rows_with_both_nonblank": rows_with_both_nonblank,
        "per_column_counts": counts,
        "examples": examples,
        "format_resolved": False,
        "decision": "format_unresolved",
        "conversion_justified": False,
        "geometry_generated": False,
        "methodology": (
            "Clasificación solo textual: cada valor raw exacto de Latitud/Longitud se "
            "asigna a exactamente una categoría usando la precedencia determinista "
            "documentada (vacío; centinela '?'; palabra clave obvia de WKT/geometría "
            "seguida de '(' antes de DMS/numérico; "
            "miles agrupados canónicos con 2+ separadores de punto/comma con grupos de "
            "3 dígitos; decimal con coma simple; decimal estricto con punto; marcadores "
            "DMS obvios; texto residual; desconocido). Las candidatas son "
            "observacionales: la auditoría nunca afirma qué significan los "
            "separadores, nunca interpreta CRS/orden de ejes/WGS84/UTM/DMS, nunca "
            "convierte valores y nunca genera geometría. Ubicacion nunca se usa."
        ),
        "evidence": {
            "fields_audited": list(COORDINATE_COLUMNS),
            "local_evidence_paths": [
                str(Path(manifest_path)),
                # Reconstruido a partir del raw_dir provisto + el raw_file relativo
                # del manifest, para que las rutas sigan siendo repo-relativas cuando
                # el llamador pasa rutas repo-relativas (la validación las resuelve
                # internamente).
                str(Path(raw_dir) / snapshot.raw_file),
                "docs/source-contract.md",
                "src/mobility_reliability/validation/source_snapshot.py",
                "src/mobility_reliability/transformation/snapshot.py",
                "tests/test_validation.py",
                "tests/test_transformation.py",
                "tests/test_captured_snapshots.py",
            ],
            # Campos de metadatos del manifest/resource inspeccionados por la
            # validación estructural estricta (validate_source_snapshot) en la que
            # se apoya la auditoría.
            "manifest_metadata_fields_inspected": [
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
            ],
            "source_data_dictionary_present_locally": False,
            "notes": [
                "Los números de fila son filas de datos 1-based (fila 1 = primera fila de datos del CSV).",
                "La clasificación no es sensible al espacio; los ejemplos preservan el valor raw exacto.",
                "Los campos de metadatos del manifest/resource son inspeccionados por la validación "
                "estructural estricta en la que se apoya la auditoría; la auditoría añade las compuertas "
                "de dataset aprobado, resource aprobado y columnas requeridas.",
                "El diccionario de datos ODS referenciado (GADCuenca_ParadasTransporte_DD_2025Abril.ods) "
                "está ausente localmente; ninguna evidencia local prueba la codificación de fuente, el "
                "orden de ejes, el CRS o una conversión segura.",
            ],
        },
        "recommendation": (
            "No convierta, reordene, reproyecte ni construya geometría a partir de "
            "Latitud/Longitud: ninguna evidencia local prueba el formato de origen, el "
            "orden de ejes o el CRS. Resuelva el formato con el diccionario de datos "
            "oficial o la documentación de fuente antes de cualquier interpretación de "
            "coordenadas; hasta entonces cada valor de coordenadas sigue siendo texto "
            "sin resolver."
        ),
    }


def _escape_markdown(value: str) -> str:
    """Hace seguro un valor raw exacto para una celda de tabla Markdown."""
    return value.replace("|", "\\|").replace("\n", " ")


def render_coordinate_audit_markdown(audit: dict) -> str:
    """Renderiza un reporte Markdown orientado al lector de una auditoría de formato de coordenadas.

    Primero la decisión, luego los hechos del snapshot, la metodología, los
    conteos por columna, los ejemplos limitados (valores raw exactos con números
    de fila), la evidencia y la recomendación final.
    """
    lines: list[str] = []
    lines.append(f"# Auditoría de formato de coordenadas — {audit['snapshot_id']}")
    lines.append("")
    lines.append(
        "**Decisión: `format_unresolved`** — ninguna conversión está justificada por la "
        "evidencia local. Cada valor de `Latitud`/`Longitud` sigue siendo texto sin "
        "resolver; nada se convierte y no se genera geometría."
    )
    lines.append("")

    lines.append("## Decisión")
    lines.append("")
    lines.append("| Campo | Valor |")
    lines.append("|---|---|")
    lines.append(f"| decision | `{audit['decision']}` |")
    lines.append(f"| format_resolved | `{audit['format_resolved']}` |")
    lines.append(f"| conversion_justified | `{audit['conversion_justified']}` |")
    lines.append(f"| geometry_generated | `{audit['geometry_generated']}` |")
    lines.append("")

    lines.append("## Snapshot")
    lines.append("")
    lines.append("| Ítem | Valor |")
    lines.append("|---|---|")
    lines.append(f"| snapshot_id | `{audit['snapshot_id']}` |")
    lines.append(f"| dataset_id | `{audit['dataset_id']}` |")
    lines.append(f"| resource_id | `{audit['resource_id']}` |")
    lines.append(f"| raw_file | `{audit['raw_file']}` |")
    lines.append(f"| raw_sha256 | `{audit['raw_sha256']}` |")
    lines.append(f"| row_count | {audit['row_count']} |")
    lines.append(f"| total_coordinate_values | {audit['total_coordinate_values']} |")
    lines.append(f"| filas con cualquier coordenada no vacía | {audit['rows_with_any_nonblank']} |")
    lines.append(f"| filas con ambas coordenadas no vacías | {audit['rows_with_both_nonblank']} |")
    lines.append("")

    lines.append("## Metodología")
    lines.append("")
    lines.append(audit["methodology"])
    lines.append("")
    lines.append("Precedencia (gana la primera coincidencia):")
    lines.append("")
    lines.append(
        "1. `blank` — vacío o solo espacios\n"
        "2. `sentinel` — el valor recortado es exactamente `?` (nunca una coordenada)\n"
        "3. `wkt_or_geometry_candidate` — texto obvio de WKT/geometría, revisado antes de DMS/numérico\n"
        "4. `thousands_separator_candidate` — numerales agrupados canónicos (2+ separadores de punto/comma, grupos de 3 dígitos)\n"
        "5. `decimal_comma_candidate` — una sola coma como separador decimal\n"
        "6. `decimal_candidate` — sintaxis estricta decimal con punto\n"
        "7. `dms_candidate` — marcadores obvios de grado/hemisferio\n"
        "8. `other_text` — texto residual con letras\n"
        "9. `unknown` — valores residuales que no coinciden con ningún patrón"
    )
    lines.append("")
    lines.append(
        "Las candidatas son observacionales: la auditoría **no** afirma qué "
        "significan los separadores y no interpreta CRS, orden de ejes, WGS84, UTM ni DMS."
    )
    lines.append("")

    lines.append("## Conteos por columna")
    lines.append("")
    columns = audit["columns_audited"]
    lines.append("| Categoría | " + " | ".join(columns) + " |")
    lines.append("|---|" + "---|" * len(columns))
    for category in COORDINATE_CATEGORIES:
        cells = [str(audit["per_column_counts"][column][category]) for column in columns]
        lines.append(f"| {category} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Ejemplos")
    lines.append("")
    lines.append(
        "Solo primeras ocurrencias, como máximo 20 por categoría por columna; los "
        "valores son las cadenas raw exactas (los números de fila son filas de datos "
        "1-based)."
    )
    lines.append("")
    for column in columns:
        for category in COORDINATE_CATEGORIES:
            examples = audit["examples"][column][category]
            if not examples:
                continue
            total = audit["per_column_counts"][column][category]
            lines.append(f"### {column} — {category} ({total} valores)")
            lines.append("")
            lines.append("| Fila | Valor raw exacto |")
            lines.append("|---|---|")
            for example in examples:
                lines.append(
                    f"| {example['row']} | `{_escape_markdown(example['value'])}` |"
                )
            lines.append("")

    lines.append("## Evidencia")
    lines.append("")
    lines.append("| Ítem | Valor |")
    lines.append("|---|---|")
    for path in audit["evidence"]["local_evidence_paths"]:
        lines.append(f"| Evidencia local | `{path}` |")
    lines.append("| Campos auditados | " + ", ".join(audit["evidence"]["fields_audited"]) + " |")
    lines.append(
        "| Campos de metadatos del manifest inspeccionados | "
        + ", ".join(audit["evidence"]["manifest_metadata_fields_inspected"])
        + " |"
    )
    lines.append(
        "| Diccionario de datos de fuente presente localmente | "
        f"{audit['evidence']['source_data_dictionary_present_locally']} |"
    )
    lines.append("")
    lines.append("No probado por la evidencia local:")
    lines.append("")
    lines.append("- Codificación de fuente y formato exacto de los valores de coordenadas")
    lines.append("- Orden de ejes (lat/lon vs lon/lat) y CRS (WGS84/UTM u otro)")
    lines.append("- Qué significan los separadores de agrupación/decimales")
    lines.append("- Cualquier regla de conversión segura")
    lines.append("")

    lines.append("## Recomendación")
    lines.append("")
    lines.append(audit["recommendation"])
    lines.append("")
    lines.append("Próximos pasos:")
    lines.append("")
    lines.append(
        "- [ ] Obtener el diccionario de datos oficial / la documentación de fuente "
        "para `Latitud`/`Longitud`."
    )
    lines.append("- [ ] Confirmar formato, orden de ejes y CRS antes de cualquier conversión.")
    lines.append("- [ ] Volver a ejecutar esta auditoría después de cualquier cambio de captura.")

    return "\n".join(lines) + "\n"


def write_coordinate_audit_artifacts(
    audit: dict, json_path: str | Path, markdown_path: str | Path
) -> dict:
    """Escribe el JSON de auditoría y el reporte Markdown orientado al lector.

    El JSON se escribe en UTF-8 (sin BOM) con indentación determinista de 2
    espacios y una nueva línea final. Ambos directorios padre se crean según sea
    necesario. Devuelve las rutas escritas.
    """
    json_path = Path(json_path)
    markdown_path = Path(markdown_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_coordinate_audit_markdown(audit), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path)}
