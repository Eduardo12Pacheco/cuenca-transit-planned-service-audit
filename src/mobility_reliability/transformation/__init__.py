"""Transformación canónica de los snapshots de fuente validados.

Este paquete convierte una captura validada (o las dos capturas aprobadas
juntas) en las entidades canónicas de servicio planificado:

- ``source_snapshot`` — proyección de provenance del evento de recopilación;
- ``mobility_network`` — un elemento ``route``/``stop`` por fila raw, con el
  mapeo exacto de columnas, cada columna de entrada preservada en un mapeo
  ``raw``, ``network_id`` estable, provenance e incidencias de calidad
  estructuradas por campo (los campos en blanco son ``missing``; un SENTIDO
  no vacío fuera de IDA/RETORNO es ``unknown``; las coordenadas inválidas son
  ``syntax_invalid`` u ``out_of_range``);
- ``planned_service`` — un registro por fila de ruta y tipo de día
  (weekday/saturday/sunday) con minutos tipados del día de servicio más el
  texto H:MM explícito en ``*_raw``;
- ``quality_report`` — métricas de calidad de datos por snapshot.

Semántica documentada
---------------------
- VALIDACIÓN ESTRUCTURAL PRIMERO: ``transform_snapshot`` llama a
  ``validate_source_snapshot`` y propaga ``SnapshotValidationError``. La
  inconsistencia manifest/raw lanza error; nunca advierte.
- LA CALIDAD DE DATOS DE FUENTE permanece observable: campos faltantes,
  coordenadas inválidas, celdas de horario malformadas, violaciones de
  cronología y valores SENTIDO desconocidos se convierten en ``quality_flags``
  por registro y en conteos/advertencias del reporte. Las filas raw nunca se
  corrigen ni se descartan en silencio.
- LAS VENTANAS SIN SERVICIO son el centinela exacto ``0:00``/``0:00``/``0:00``:
  los ceros tipados se conservan, ``service_status='no_service'``, y nunca se
  cuentan como ventanas activas inválidas.
- LAS COORDENADAS se validan sintácticamente (``^-?\\d+(?:\\.\\d+)?$``,
  dígitos ASCII, como máximo un punto decimal, conversión Decimal) más los
  rangos globales (latitud [-90, 90], longitud [-180, 180]). Sin heurísticas,
  sin separadores de miles, sin bounding box de Cuenca, sin corregir valores
  raw. Un punto de ``geometry`` de parada existe solo cuando AMBAS coordenadas
  pasan; nunca se crea geometría de rutas.
- LOS HORARIOS son minutos del día de servicio; los valores superiores a
  24:00 se conservan sin conversión de calendario; ``service_date`` nunca se
  inventa (null).
- SOLO PLANIFICADO: sin clima, sin GTFS-RT/AVL, sin dashboards, sin
  afirmaciones de movilidad observada.

API pública
-----------
- ``transform_snapshot(manifest_path, raw_dir)`` -> dict con
  ``source_snapshot``, ``mobility_network``, ``planned_service``,
  ``quality_report``.
- ``transform_captures(route_manifest_path, stops_manifest_path, raw_dir)``
  -> dict combinado con ``source_snapshots``, ``mobility_network``,
  ``planned_service``, ``quality_reports``, ``transformation``.
- ``KNOWN_EXPECTED_ROW_COUNTS``: conteos de filas esperados para los dos IDs de
  recurso aprobados conocidos (se usa solo como verificación no universal del
  reporte).
"""

from .snapshot import (
    KNOWN_EXPECTED_ROW_COUNTS,
    transform_captures,
    transform_snapshot,
)

__all__ = [
    "KNOWN_EXPECTED_ROW_COUNTS",
    "transform_captures",
    "transform_snapshot",
]
