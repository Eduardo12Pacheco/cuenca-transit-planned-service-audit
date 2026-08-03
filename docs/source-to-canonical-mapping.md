# Mapeo fuente → modelo canónico (`day_type`)

Este documento fija, con evidencia, cómo las columnas del dataset fuente de
rutas se interpretan como el valor canónico `day_type` del modelo
`planned_service`. Es la interpretación a nivel de aplicación usada por el
modelo canónico implementado; **no modifica** `docs/source-contract.md`.

## Mapeo fuente → modelo canónico

La fuente de rutas no publica ninguna columna `day_type`. En su lugar, cada
fila de ruta publica **tres familias de columnas** de horario planificado
(inicio, fin e intervalo), una por tipo de día. La transformación canónica
deriva **un** registro `planned_service` por fila × familia, con el valor
canónico de la tabla:

| Familia de columnas fuente (rutas) | Columnas fuente exactas | Valor canónico `day_type` |
| --- | --- | --- |
| LUNES_VIERNES | `LUNES_VIERNES_INICIO`, `LUNES_VIERNES_FIN`, `LUNES_VIERNES_INTERVALO` | `weekday` |
| SABADOS | `SABADOS_INICIO`, `SABADOS_FIN`, `SABADOS_INTERVALO` | `saturday` |
| DOMINGOS | `DOMINGOS_INICIO`, `DOMINGOS_FIN`, `DOMINGOS_INTERVALO` | `sunday` |

Los valores de las tres columnas de cada familia se conservan sin pérdida:
los textos H:MM exactos en `planned_start_raw` / `planned_end_raw` /
`planned_headway_raw` y los minutos tipados relativos al día de servicio en
`planned_start` / `planned_end` / `planned_headway`.

## Semántica: horas relativas al día de servicio

- Todos los horarios son **relativos al día de servicio** (service-day-relative)
  y pueden superar 24:00 (p. ej. `25:10` = 01:10 del día siguiente del día de
  servicio). El modelo conserva el valor tal como lo publica la fuente y nunca
  lo convierte a un timestamp de calendario de forma ingenua.
- El centinela exacto `0:00/0:00/0:00` en las tres columnas de una familia
  significa **sin servicio** (`service_status='no_service'`): la fuente publica
  el centinela, y el modelo lo conserva como tal — nunca como una ventana
  activa inválida.
- `service_date` nunca se inventa: la fuente no publica fecha de servicio, por
  lo que el campo canónico es siempre `null`.

## Evidencia

- **Implementación**: `src/mobility_reliability/transformation/snapshot.py`
  (constante `DAY_TYPES` con las tres tripletas `(day_type, columna_inicio,
  columna_fin, columna_intervalo)` y la derivación de un registro por familia
  en `_service_records`). No se modificó código de transformación para este
  documento.
- **Pruebas**: `tests/test_transformation.py`
  (`test_day_type_column_families_map_to_canonical_values`), que fija la
  tripleta exacta de columnas y los valores canónicos a través de la salida
  pública de la transformación; y los reportes de calidad observados en
  `tests/test_captured_snapshots.py` (8 ventanas sin servicio en Sábado/Domingo
  para las líneas 21 y 23).
- **Semántica contractual**: `docs/source-contract.md` §14.2 describe la
  transformación raw-preserving con los valores canónicos
  `weekday/saturday/sunday`.

### Sobre la discrepancia `weekday/weekend` en `docs/source-contract.md`

La sección 10.3 de `docs/source-contract.md` todavía dice `day_type`
(`weekday`/`weekend`), mientras que su sección 14.2 y el código implementado
usan `weekday`/`saturday`/`sunday`. **Ese archivo está protegido y no se
reescribe en silencio**: esta pasada de publicación tiene prohibido modificar el
contrato, y la frase existente permanece byte por byte. Este documento es la
interpretación explícita y vinculante a nivel de aplicación que usa el modelo
canónico implementado: las tres familias de columnas de la fuente se mapean a
`weekday`, `saturday` y `sunday`, de modo que el mapeo es inequívoco incluso
mientras el contrato mantenga la discrepancia. La resolución definitiva del
wording del contrato queda pendiente de una decisión del propio contrato.

## Referencias

- Contrato de fuente (protegido, sin cambios): `docs/source-contract.md`.
- Auditoría de coordenadas (decisión `format_unresolved`): `docs/coordinate-quality-audit.md`.
- Demo y fixture sintético: `data/demo/README.md`.
