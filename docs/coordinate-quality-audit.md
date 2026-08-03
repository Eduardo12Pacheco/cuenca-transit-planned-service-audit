# Auditoría de formato de coordenadas — paradas-de-transporte-publico@2026-08-02T19-27-36Z

**Decisión: `format_unresolved`** — ninguna conversión está justificada por la evidencia local. Cada valor de `Latitud`/`Longitud` permanece como texto sin resolver; nada se convierte y no se genera ninguna geometría.

## Decisión

| Campo | Valor |
|---|---|
| decision | `format_unresolved` |
| format_resolved | `False` |
| conversion_justified | `False` |
| geometry_generated | `False` |

## Instantánea

| Elemento | Valor |
|---|---|
| snapshot_id | `paradas-de-transporte-publico@2026-08-02T19-27-36Z` |
| dataset_id | `paradas-de-transporte-publico` |
| resource_id | `ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e` |
| raw_file | `paradas-de-transporte-publico/2026-08-02T19-27-36Z.json` |
| raw_sha256 | `20969d2e6dbc4d91338901f88c2805afaf642b757adfa4be97225c7364bdc62c` |
| row_count | 383 |
| total_coordinate_values | 766 |
| filas con cualquier coordenada no vacía | 383 |
| filas con ambas coordenadas no vacías | 383 |

## Metodología

Solo clasificación textual: cada valor raw exacto de Latitud/Longitud se asigna exactamente a una categoría usando la precedencia determinista documentada (blank; centinela '?'; keyword obvia de WKT/geometría seguida de '(' antes de DMS/numérico; miles agrupados canónicos con 2+ separadores de punto/comilla de grupos de 3 dígitos; decimal con coma única; decimal estricto con punto; marcadores obvios de DMS; texto residual; unknown). Los candidatos son observacionales: la auditoría nunca afirma qué significan los separadores, nunca interpreta CRS/orden de ejes/WGS84/UTM/DMS, nunca convierte valores y nunca genera geometría. Ubicacion nunca se usa.

Precedencia (gana la primera coincidencia):

1. `blank` — vacío o solo espacios en blanco
2. `sentinel` — el valor recortado es exactamente `?` (nunca una coordenada)
3. `wkt_or_geometry_candidate` — texto obvio de WKT/geometría, verificado antes de DMS/numérico
4. `thousands_separator_candidate` — numerales agrupados canónicos (2+ separadores de punto/comilla, grupos de 3 dígitos)
5. `decimal_comma_candidate` — coma única como separador decimal
6. `decimal_candidate` — sintaxis decimal estricta con punto
7. `dms_candidate` — marcadores obvios de grados/hemisferio
8. `other_text` — texto residual con letras
9. `unknown` — valores residuales que no coinciden con ningún patrón

Los candidatos son observacionales: la auditoría **no** afirma qué significan los separadores y no interpreta CRS, orden de ejes, WGS84, UTM ni DMS.

## Conteos por columna

| Categoría | Latitud | Longitud |
|---|---|---|
| blank | 0 | 0 |
| sentinel | 0 | 0 |
| decimal_candidate | 52 | 9 |
| decimal_comma_candidate | 0 | 0 |
| thousands_separator_candidate | 331 | 374 |
| dms_candidate | 0 | 0 |
| wkt_or_geometry_candidate | 0 | 0 |
| other_text | 0 | 0 |
| unknown | 0 | 0 |

## Ejemplos

Solo primeras apariciones, como máximo 20 por categoría y por columna; los valores son las cadenas raw exactas (los números de fila son filas de datos con base 1).

### Latitud — decimal_candidate (52 valores)

| Fila | Valor raw exacto |
|---|---|
| 10 | `-290.709` |
| 18 | `-289.867` |
| 26 | `-290.179` |
| 42 | `-291.137` |
| 46 | `-290.685` |
| 54 | `-291.429` |
| 63 | `-289.418` |
| 83 | `-289.626` |
| 111 | `-288.138` |
| 119 | `-288.124` |
| 136 | `-280.162` |
| 146 | `-288.842` |
| 149 | `-288.832` |
| 154 | `-288.499` |
| 159 | `-291.553` |
| 160 | `-291.552` |
| 167 | `-289.285` |
| 179 | `-291.601` |
| 187 | `-285.892` |
| 191 | `-290.819` |

### Latitud — thousands_separator_candidate (331 valores)

| Fila | Valor raw exacto |
|---|---|
| 1 | `-2.895.956` |
| 2 | `-2.908.987` |
| 3 | `-2.908.728` |
| 4 | `-2.911.547` |
| 5 | `-2.910.397` |
| 6 | `-2.910.711` |
| 7 | `-2.906.378` |
| 8 | `-2.906.159` |
| 9 | `-2.914.142` |
| 11 | `-2.908.374` |
| 12 | `-2.908.251` |
| 13 | `-2.895.498` |
| 14 | `-2.895.227` |
| 15 | `-2.910.479` |
| 16 | `-2.910.521` |
| 17 | `-2.898.906` |
| 19 | `-2.903.575` |
| 20 | `-2.894.167` |
| 21 | `-2.909.518` |
| 22 | `-2.907.428` |

### Longitud — decimal_candidate (9 valores)

| Fila | Valor raw exacto |
|---|---|
| 26 | `-790.064` |
| 75 | `-79.0` |
| 76 | `-79.0` |
| 299 | `-78.99` |
| 322 | `-789.295` |
| 325 | `-79.037` |
| 326 | `-78.971` |
| 329 | `-789.084` |
| 362 | `-789.759` |

### Longitud — thousands_separator_candidate (374 valores)

| Fila | Valor raw exacto |
|---|---|
| 1 | `-79.014.574` |
| 2 | `-79.015.701` |
| 3 | `-79.015.773` |
| 4 | `-79.007.121` |
| 5 | `-79.010.522` |
| 6 | `-79.010.061` |
| 7 | `-79.023.371` |
| 8 | `-79.023.488` |
| 9 | `-78.996.122` |
| 10 | `-79.021.045` |
| 11 | `-79.017.546` |
| 12 | `-79.017.391` |
| 13 | `-79.016.888` |
| 14 | `-79.017.383` |
| 15 | `-78.996.205` |
| 16 | `-78.994.406` |
| 17 | `-79.011.234` |
| 18 | `-79.011.019` |
| 19 | `-79.003.034` |
| 20 | `-79.021.063` |

## Evidencia

| Elemento | Valor |
|---|---|
| Evidencia local | `data/manifests/paradas-de-transporte-publico/2026-08-02T19-27-36Z.manifest.json` |
| Evidencia local | `data/raw/paradas-de-transporte-publico/2026-08-02T19-27-36Z.json` |
| Evidencia local | `docs/source-contract.md` |
| Evidencia local | `src/mobility_reliability/validation/source_snapshot.py` |
| Evidencia local | `src/mobility_reliability/transformation/snapshot.py` |
| Evidencia local | `tests/test_validation.py` |
| Evidencia local | `tests/test_transformation.py` |
| Evidencia local | `tests/test_captured_snapshots.py` |
| Campos auditados | Latitud, Longitud |
| Campos de metadatos del manifest inspeccionados | source_metadata, resource, resource_id, resource_name, resource_format, resource_url, size, description, created, last_modified, metadata_modified |
| Diccionario de datos de la fuente presente localmente | False |

No probado por la evidencia local:

- La codificación de la fuente y el formato exacto de los valores de coordenadas
- El orden de ejes (lat/lon vs lon/lat) y el CRS (WGS84/UTM u otro)
- Qué significan los separadores de agrupación/decimales
- Cualquier regla de conversión segura

## Recomendación

No convertir, reordenar, reproyectar ni construir geometría a partir de Latitud/Longitud: ninguna evidencia local prueba el formato de la fuente, el orden de ejes o el CRS. Resolver el formato con el diccionario de datos oficial o la documentación de la fuente antes de cualquier interpretación de coordenadas; hasta entonces, cada valor de coordenada permanece como texto sin resolver.

Próximos pasos:

- [ ] Obtener el diccionario de datos oficial / documentación de la fuente para `Latitud`/`Longitud`.
- [ ] Confirmar formato, orden de ejes y CRS antes de cualquier conversión.
- [ ] Volver a ejecutar esta auditoría después de cualquier cambio de captura.
