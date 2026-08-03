"""Adaptadores de ingestión para las fuentes aprobadas de Cuenca en Datos.

El único destino de ingestión aprobado hoy es el colector de snapshots CKAN
(``mobility_reliability.ingestion.ckan_snapshot``), que captura un snapshot
actual por dataset aprobado. La geometría de rutas (recorrido), los snapshots
históricos masivos y cualquier otra fuente quedan fuera de alcance.
"""
