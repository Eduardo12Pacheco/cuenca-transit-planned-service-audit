"""Validación estructural de los snapshots de fuente capturados.

Este paquete valida una captura CKAN aprobada (manifest + bytes raw exactos)
de forma estricta y sin conexión, y expone la proyección validada que usan las
transformaciones.

Semántica (contrato documentado)
--------------------------------
- FAIL CLOSED: cualquier inconsistencia estructural de provenance lanza
  ``SnapshotValidationError``. Los fallos estructurales nunca se degradan a
  advertencias: un manifest que no es un objeto JSON, un estado distinto de
  ``success``, campos obligatorios ausentes/vacíos, una URL de dataset/fuente
  no aprobada, metadatos de recurso inconsistentes, una huella de licencia
  distinta de ``license_id=cc-nc`` más la URL oficial CC BY-NC 2.0, un
  ``collection_timestamp_utc`` inválido en UTC estricto o un
  ``source_published_at`` ausente/vacío/inválido (obligatorio; se acepta la
  forma ISO ingenua del portal), un ``schema_version`` inválido, un
  ``raw_file`` absoluto/con traversal/ausente, un SHA-256 malformado o que no
  coincide, UTF-8/CSV inválido, filas CSV desalineadas (ragged), un recurso
  seleccionado no-CSV o geométrico, un ``row_count`` del manifest que difiere
  de las filas CSV reales, o metadatos de paquete (``source_metadata``) que
  no son un objeto, cuyo ``name`` no coincide con el dataset, o cuya lista
  ``resources`` no contiene el id del recurso seleccionado — todo rechaza el
  snapshot.
- Solo se aceptan los dos datasets aprobados (rutas y paradas); su
  ``source_url`` debe ser la URL exacta aprobada de CKAN ``package_show``.
- Los problemas de calidad de datos de fuente (campos en blanco, coordenadas
  inválidas, anomalías de horario) NO son estructurales: los reporta la capa
  de transformación como ``quality_flags`` por registro y como
  conteos/advertencias del reporte. Nada se corrige ni se descarta en
  silencio.
- El recurso seleccionado debe ser CSV y no geométrico. ZIP/ODS y los recursos
  que identifican geometry, datos geoespaciales, geometría de rutas (recorrido)
  o shapes se rechazan.
- Se verifican la atribución y el ID del recurso; la proyección de recurso de
  nivel superior debe coincidir con los metadatos anidados ``resource``.

API pública
-----------
- ``validate_source_snapshot(manifest_path, raw_dir)`` -> ``SourceSnapshot``
- ``SnapshotValidationError``
- ``SourceSnapshot`` (dataclass; ``as_dict()`` devuelve la proyección
  ``source_snapshot`` compatible con JSON; también lleva ``manifest``,
  ``raw_path``, ``header`` y ``rows`` para la capa de transformación)
"""

from .source_snapshot import (
    OFFICIAL_CC_BY_NC_2_0_URL,
    SnapshotValidationError,
    SourceSnapshot,
    validate_source_snapshot,
)

__all__ = [
    "OFFICIAL_CC_BY_NC_2_0_URL",
    "SnapshotValidationError",
    "SourceSnapshot",
    "validate_source_snapshot",
]
