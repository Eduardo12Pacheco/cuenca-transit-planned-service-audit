"""Textos de interfaz en español para la demo local sin conexión.

Cadenas visibles para el lector de la app de Streamlit. Los valores
canónicos, los nombres de campos y los códigos técnicos (``service_status``,
``quality_flags``, ``raw``, ``snapshot``, CRS, GTFS-Realtime, AVL,
``provenance``, SHA-256, ``resource_id``) permanecen intactos en la capa de
datos; este módulo solo los mapea a español para la visualización. La app
sigue siendo de solo lectura y reutiliza la salida de la transformación
canónica y el artefacto de auditoría de coordenadas.
"""

from __future__ import annotations

APP_TITLE = "Auditoría del servicio planificado de transporte público de Cuenca"

SIDEBAR_SELECTION = "Selección"
SIDEBAR_LINE = "Línea"
SIDEBAR_DIRECTION = "Sentido"
SIDEBAR_DAY_TYPE = "Tipo de día"
SIDEBAR_EVIDENCE = "Evidencia del snapshot"
SIDEBAR_EVIDENCE_HINT = (
    "Todos los valores provienen de estos dos snapshots y de nada más."
)

TAB_PLANNED = "Servicio planificado"
TAB_ROUTE_QUALITY = "Calidad de rutas"
TAB_STOPS_QUALITY = "Calidad de paradas"
TAB_EVIDENCE = "Evidencia y provenance"

# Etiquetas en español para los valores canónicos de service_status. Los
# códigos desconocidos se mantienen sin cambios (solo aparecen en contextos
# técnicos).
STATUS_LABELS = {
    "active": "Activo",
    "no_service": "Sin servicio",
    "invalid": "Inválido",
    "missing": "Sin registro",
}

# Descripciones legibles en español para las incidencias de calidad
# canónicas ("field=flag"). Las incidencias no mapeadas conservan su código
# técnico "field=flag".
FLAG_DESCRIPTIONS = {
    "LINEA=missing": "Línea sin valor",
    "COMPANIA=missing": "Empresa sin valor",
    "SENTIDO=missing": "Sentido sin valor",
    "SENTIDO=unknown": "Sentido desconocido",
    "ORIGEN=missing": "Origen sin valor",
    "DESTINO=missing": "Destino sin valor",
    "planned_start=malformed": "Inicio planificado malformado",
    "planned_start=chronology_invalid": "Inicio planificado incoherente",
    "planned_end=malformed": "Fin planificado malformado",
    "planned_end=chronology_invalid": "Fin planificado incoherente",
    "planned_headway=malformed": "Intervalo planificado malformado",
    "planned_headway=zero_or_negative": "Intervalo planificado cero o negativo",
}

EXPANDER_TECHNICAL = "Ver valores raw y códigos técnicos"
EXPANDER_TECHNICAL_HINT = (
    "Los valores raw son los textos H:MM exactos publicados por la fuente; "
    "los códigos técnicos (service_status, quality_flags, service_id, "
    "network_id, provenance) son los del modelo canónico, sin traducir."
)

# Glosas en español para las categorías de la auditoría (los identificadores
# permanecen canónicos).
CATEGORY_GLOSSES = {
    "blank": "vacío",
    "sentinel": "centinela",
    "decimal_candidate": "candidato decimal con punto",
    "decimal_comma_candidate": "candidato decimal con coma",
    "thousands_separator_candidate": "candidato a separador de miles",
    "dms_candidate": "candidato DMS",
    "wkt_or_geometry_candidate": "candidato WKT/geometría",
    "other_text": "otro texto",
    "unknown": "desconocido",
}

__all__ = [
    "APP_TITLE",
    "SIDEBAR_SELECTION",
    "SIDEBAR_LINE",
    "SIDEBAR_DIRECTION",
    "SIDEBAR_DAY_TYPE",
    "SIDEBAR_EVIDENCE",
    "SIDEBAR_EVIDENCE_HINT",
    "TAB_PLANNED",
    "TAB_ROUTE_QUALITY",
    "TAB_STOPS_QUALITY",
    "TAB_EVIDENCE",
    "STATUS_LABELS",
    "FLAG_DESCRIPTIONS",
    "EXPANDER_TECHNICAL",
    "EXPANDER_TECHNICAL_HINT",
    "CATEGORY_GLOSSES",
]
