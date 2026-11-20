"""Auditoría sin conexión del formato de coordenadas de la captura de paradas
aprobada.

Este paquete clasifica los valores raw exactos de ``Latitud``/``Longitud`` del
snapshot de paradas aprobado en categorías textuales observacionales. Es
totalmente sin conexión, solo lee el manifest/raw local mediante la validación
estructural estricta, y nunca convierte, nunca interpreta CRS/orden de
ejes/WGS84/UTM/DMS, nunca usa ``Ubicacion`` y nunca genera geometría.

Semántica (contrato documentado)
--------------------------------
- FAIL CLOSED: ``audit_coordinate_formats`` propaga
  ``SnapshotValidationError`` desde la validación estructural y lanza
  ``CoordinateAuditError`` cuando el snapshot no es la captura de paradas
  aprobada (dataset ``paradas-de-transporte-publico``, recurso
  ``ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e``) o cuando ``Latitud``/``Longitud``
  están ausentes del encabezado raw.
- CLASIFICADOR TEXTUAL DETERMINISTA: ``classify_coordinate_value`` asigna cada
  valor raw exacto a exactamente una de ``COORDINATE_CATEGORIES`` usando la
  precedencia documentada (vacío; centinela ``?``; WKT/geometría obvio antes
  de DMS/numérico; miles agrupados canónicos; decimal con coma simple; decimal
  estricto con punto; marcadores DMS obvios; texto residual; desconocido). Las
  categorías son candidatas: la auditoría nunca afirma qué significan los
  separadores y nunca interpreta los valores.
- EJEMPLOS: como máximo 20 por categoría por columna, con el número de fila de
  datos 1-based y el valor raw exacto; el artefacto nunca contiene el raw
  completo.
- GUARDA DE CONVERSIÓN: ``convert_coordinate_value`` siempre lanza
  ``CoordinateConversionError`` — ninguna evidencia local prueba el formato,
  el orden de ejes, el CRS o una conversión segura.
- DECISIÓN: la auditoría siempre reporta ``format_resolved: false``,
  ``decision: format_unresolved``, ``conversion_justified: false`` y
  ``geometry_generated: false``, y no emite geometría ni resultado de
  conversión.

API pública
-----------
- ``COORDINATE_CATEGORIES``, ``COORDINATE_COLUMNS``,
  ``MAX_EXAMPLES_PER_CATEGORY``, ``APPROVED_STOPS_DATASET_ID``,
  ``APPROVED_STOPS_RESOURCE_ID``
- ``classify_coordinate_value(value)`` -> una de ``COORDINATE_CATEGORIES``
- ``audit_coordinate_formats(manifest_path, raw_dir)`` -> dict de auditoría
  compatible con JSON (conteos, ejemplos limitados, evidencia, decisión no
  resuelta)
- ``convert_coordinate_value(value)`` -> siempre lanza ``CoordinateConversionError``
- ``render_coordinate_audit_markdown(audit)`` -> Markdown orientado al lector
- ``write_coordinate_audit_artifacts(audit, json_path, markdown_path)`` ->
  escribe el artefacto JSON y el reporte Markdown
"""

from .coordinate_audit import (
    APPROVED_STOPS_DATASET_ID,
    APPROVED_STOPS_RESOURCE_ID,
    COORDINATE_CATEGORIES,
    COORDINATE_COLUMNS,
    MAX_EXAMPLES_PER_CATEGORY,
    CoordinateAuditError,
    CoordinateConversionError,
    audit_coordinate_formats,
    classify_coordinate_value,
    convert_coordinate_value,
    render_coordinate_audit_markdown,
    write_coordinate_audit_artifacts,
)

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
