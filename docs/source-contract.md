# Contrato de fuentes y alcance

**Estado:** autoritativo para el límite del MVP. Este contrato es la única fuente de verdad sobre qué datos puede usar este proyecto, qué puede afirmar y qué puede construir. El README enlaza aquí; cualquier cambio de alcance, fuentes, entidades o métricas exige una revisión documentada de este contrato antes de realizar cambios de implementación.

**Alcance en una frase:** el MVP es una auditoría reproducible del servicio de transporte público **planificado** de Cuenca — rutas, paradas, headways planificados (intervalos de paso), ventanas de servicio, cobertura, instantáneas históricas y contexto meteorológico. NO es un producto de retraso real ni de puntualidad real.

## 1. Decisión y límite del MVP

| Pregunta | Decisión |
| --- | --- |
| ¿Qué mide el MVP? | Solo servicio planificado: rutas, paradas, ventanas de servicio, headways planificados, cobertura, cambios entre instantáneas, frescura/integridad, distancias estación–corredor. |
| ¿Qué NO mide el MVP? | Retraso observado, puntualidad/porcentaje a tiempo, cancelaciones reales, posiciones de vehículos, fiabilidad del tiempo de viaje, causalidad meteorológica. |
| ¿Por qué? | No hay ninguna fuente autorizada de movilidad en tiempo real u observada. Un GTFS estático es un plan, no una observación. |
| ¿Dónde residen las métricas observadas? | Solo en una extensión futura, respaldada por una fuente autorizada de GTFS-Realtime/AVL (pendiente de autorización y disponibilidad). |
| Estado de las fuentes operativas AVL/GTFS-RT | Pendiente de autorización y disponibilidad. Que una URL sea accesible no es una autorización. |

### Implicaciones (vinculantes)

- Ningún gráfico, métrica o elemento de demostración puede etiquetarse ni leerse como retraso observado, rendimiento a tiempo o puntualidad.
- Ninguna entidad de esquema actual puede contener campos de movilidad observada (ver Sección 10).
- Los datos meteorológicos son solo contexto; no se permite ninguna afirmación causal.
- Las capturas raw se limitan a una instantánea actual por conjunto de datos aprobado (ver Sección 13); sin descargas históricas masivas ni fixtures raw commiteados en el repositorio.

## 2. Fuente de movilidad: Cuenca en Datos (aceptada)

Cuenca en Datos es el portal oficial de datos abiertos del Municipio de Cuenca (basado en CKAN). La auditoría lo identificó como la fuente de movilidad estática más sólida utilizable hoy: los conjuntos de datos existen, los campos están documentados y hay instantáneas históricas disponibles entre 2022 y 2025.

| Conjunto de datos | Contenido | Campos auditados | Licencia (según publicación) | Estado |
| --- | --- | --- | --- | --- |
| Rutas / horarios planificados | Identidades de ruta y tiempos de servicio planificados | LINEA, COMPANIA, SENTIDO, ORIGEN, DESTINO; inicio, fin e intervalo para días laborables y fines de semana | CC BY-NC 2.0 | **Aceptado** |
| Paradas | Atributos y posiciones de paradas | Identificadores, nombres y ubicaciones de paradas | CC BY-NC 2.0 | **Aceptado** |

Enlaces oficiales de CKAN (verificados en la auditoría):

| Conjunto de datos | Vista del portal | API de CKAN |
| --- | --- | --- |
| Rutas / horarios planificados | https://cuencaendatos.cuenca.gob.ec/dataset/rutas-de-transporte-publico | https://cuencaendatos.cuenca.gob.ec/api/3/action/package_show?id=rutas-de-transporte-publico |
| Paradas | https://cuencaendatos.cuenca.gob.ec/dataset/paradas-de-transporte-publico | https://cuencaendatos.cuenca.gob.ec/api/3/action/package_show?id=paradas-de-transporte-publico |

La URL exacta del paquete se registra en cada evento de recolección en `source_snapshot.source_url`.

### 2.1 Metadatos de licencia publicados (verificados en vivo el 2026-08-02)

Los metadatos en vivo del paquete CKAN de ambos conjuntos de datos aprobados
publican actualmente `license_id=cc-nc`, el `license_title` genérico "Creative
Commons Non-Commercial (Cualquiera)", el `license_url` oficial de CC BY-NC 2.0
(`http://creativecommons.org/licenses/by-nc/2.0/`) e `isopen=false`. Esta es una
discrepancia de metadatos técnicamente resuelta, no una licencia inventada: el ID
publicado y la URL canónica identifican la licencia oficial CC BY-NC 2.0, y el
título almacenado es el marcador de posición genérico de CKAN del portal para
esa licencia.

Por lo tanto, la compuerta de licencia del recolector usa el **ID de licencia
publicado (`cc-nc`) más la URL canónica oficial de la licencia CC BY-NC 2.0**
(http/https, barra final opcional) como autoridad de compatibilidad, verificada
antes de cualquier descarga de recurso. `license_title` se conserva exactamente
en `license_published` y `source_metadata` y solo añade una advertencia cuando
difiere de `CC BY-NC 2.0`; `license_declared` sigue siendo el valor contractual
`CC BY-NC 2.0`; `isopen=false` y la restricción NonCommercial se conservan/
registran por manifest.

Los manifests fallidos del intento en vivo `2026-08-02T18:25:46Z` permanecen
como evidencia histórica inmutable en `data/manifests/`. Esta revisión no
autoriza una nueva captura; una captura nueva requiere autorización explícita.

Las instantáneas históricas (2022–2025) son el material para el análisis de
cambios entre instantáneas; su disponibilidad y fechas se registran por
`source_snapshot`.

## 3. Datos de geometría de rutas / recorrido (condicional)

| Aspecto | Hallazgo |
| --- | --- |
| Contenido | Paquete de geometría de rutas (recorrido) en el mismo portal; existe una exportación CSV reciente |
| Licencia | Los metadatos publicados carecen de una licencia clara |
| Estado | **Condicional — excluido de la ingesta del MVP.** Solo podrá usarse más adelante como geometría complementaria una vez que la licencia esté confirmada y este contrato sea revisado. |

Enlaces oficiales del portal (solo para referencia y confirmación de licencia — **no aceptados para ingesta**):

| Vista del portal | API de CKAN |
| --- | --- |
| https://cuencaendatos.cuenca.gob.ec/dataset/recorrido-de-las-rutas-de-transporte-publico | https://cuencaendatos.cuenca.gob.ec/api/3/action/package_show?id=recorrido-de-las-rutas-de-transporte-publico |

## 4. Conjuntos de datos de movilidad excluidos o condicionales

| Fuente | Estado | Motivo |
| --- | --- | --- |
| Guayaquil — capas oficiales ArcGIS PUGS Metrovía (paradas, troncal, alimentadores) | Condicional (solo geometría estática complementaria) | Atributos estáticos útiles de rutas/paradas (maxRecordCount 2000), pero sin marcas de tiempo ni historial operativos, y sin licencia de reutilización explícita |
| Quito — referencias municipales de GTFS / monitoreo en tiempo real | Pendiente / no verificado | Existen referencias oficiales (GTFS/Google Maps, monitoreo interno en tiempo real), pero no se verificó ningún feed descargable documentado públicamente ni una API autorizada |
| Aplicaciones privadas, endpoints internos, extracción de Google Maps, scraping, fuentes sin licencia | **Excluido** | Sin autorización; términos, política de robots o controles de acceso; no reproducible |
| MobilityDatabase | **No es una fuente** | Solo catálogo de descubrimiento; el catálogo auditado no contiene ningún feed de Ecuador |

## 5. Estado de licencias y atribución

| Fuente / conjunto de datos | Estado |
| --- | --- |
| Cuenca en Datos — metadatos de rutas/paradas | CC BY-NC 2.0 según lo declarado en los metadatos del conjunto de datos publicado. Se requiere atribución; cualquier resultado del proyecto debe respetar la restricción de no uso comercial. |
| Cuenca en Datos — geometría de rutas (recorrido) | Licencia ausente/poco clara — no utilizable para redistribución hasta que se confirme. |
| Capas ArcGIS Metrovía de Guayaquil | No se encontró una licencia de reutilización explícita — tratar como no redistribuibles hasta que se confirme. |
| INAMHI — conjuntos de datos oficiales del catálogo mensual de temperatura/precipitación | CC BY según lo declarado — se requiere atribución. |
| INAMHI — endpoints operativos | Licencia, límites y estabilidad sin confirmar — requieren confirmación antes de su uso. |
| NCEI (CDO/GHCN/ISD) | Respaldo histórico documentado. CDO requiere un token y documenta 5 solicitudes/seg y 10 000 solicitudes/día; seguir la citación y los términos de NCEI. |
| Open-Meteo | CC BY 4.0 con restricciones de no uso comercial y atribución; datos modelados/reanálisis, nunca observación directa. |

**Principio:** una URL pública es evidencia de que un recurso existe, no autorización para reutilizarlo o redistribuirlo. Solo una licencia declarada o un permiso explícito autoriza su uso; todo lo demás se trata como no autorizado.

## 6. Fuente meteorológica

| Prioridad | Fuente | Rol | Restricción |
| --- | --- | --- | --- |
| Primaria | INAMHI — visor y catálogo oficiales | Datos climáticos observados para el contexto de Cuenca | Los conjuntos de datos del catálogo mensual declaran CC BY; los endpoints operativos requieren confirmación (licencia, límites, estabilidad) |
| Respaldo histórico | NCEI CDO/GHCN/ISD | Observaciones históricas documentadas | Se requiere token (CDO); límites documentados: 5 solicitudes/seg, 10 000/día; citación/términos de NCEI |
| Respaldo modelado/reanálisis | Open-Meteo | Solo respaldo claramente etiquetado | CC BY 4.0; restricciones de no uso comercial/atribución; nunca presentado como observación directa |

Cada fila de `weather_observation` lleva un flag `data_kind` (`observed` vs `modeled/reanalysis`) para que los datos modelados nunca se confundan con datos observados.

## 7. Matriz de autorización de endpoints

| Nivel | Significado | Fuentes en el nivel |
| --- | --- | --- |
| **Aceptado (público, documentado)** | Uso en el MVP | Conjuntos de datos CKAN de Cuenca en Datos (rutas, paradas); conjuntos de datos del catálogo mensual de INAMHI (CC BY); API documentada de NCEI con token y límites documentados; Open-Meteo (CC BY 4.0 — solo modelado/reanálisis, nunca observación directa) |
| **Aceptado solo tras confirmación** | No usar hasta confirmar licencia/términos | Endpoints operativos de INAMHI; geometría de rutas de Cuenca (recorrido); capas ArcGIS Metrovía de Guayaquil |
| **Pendiente / requiere solicitud** | Requiere autorización o permiso; no se puede programar | GTFS/APIs municipales de Quito; cualquier fuente GTFS-Realtime o AVL |
| **Excluido** | Nunca | Aplicaciones privadas, endpoints internos, extracción de Google Maps, scraping, fuentes sin licencia; MobilityDatabase como fuente de datos (solo catálogo) |

Reglas: una URL accesible no es autorización para redistribuir; ningún endpoint privado se usa jamás; cada fuente utilizada registra su licencia declarada en `source_snapshot`.

Open-Meteo se acepta solo como datos modelados/reanálisis claramente etiquetados: respetar su atribución CC BY 4.0 y sus requisitos de no uso comercial/términos, y nunca presentarlo como observación directa.

## 8. Riesgos

| Riesgo | Descripción | Mitigación |
| --- | --- | --- |
| Cobertura geográfica | Ciudad única (Cuenca); las afirmaciones de cobertura están acotadas por los conjuntos de datos auditados, nunca a nivel de toda la ciudad | Informar la cobertura por instantánea; nunca extrapolar |
| Semántica estático vs. observado | El servicio planificado no es servicio observado; los lectores pueden malinterpretar los gráficos | Etiquetado destacado; lista de métricas reservadas; decisión de alcance en el README |
| Instantáneas desactualizadas | Las instantáneas de 2022–2025 tienen frescura variable; el análisis de cambios está acotado por las fechas de las instantáneas | Métrica de frescura; fechas por instantánea registradas |
| Estabilidad del esquema/API | Los campos de CKAN o las URLs de paquetes pueden cambiar | Fijar URLs en la configuración; versionar el esquema de cada instantánea; verificaciones de conformidad de esquema |
| Límites de velocidad no documentados | Los límites de los endpoints operativos de INAMHI son desconocidos; los de CDO están documentados | Paso de confirmación; limitación conservadora; límites documentados aplicados |
| Brechas/calidad de estaciones | Las estaciones meteorológicas pueden no cubrir los corredores | Informar las distancias estación–corredor y las brechas como resultado de primera clase |
| Licenciamiento/redistribución | CC BY-NC 2.0 (metadatos de Cuenca); licencias faltantes (geometría de rutas, Guayaquil) | Niveles del contrato; sin redistribución de datos sin licencia |
| Atribución | Obligaciones de atribución por fuente (INAMHI CC BY, Open-Meteo, NCEI) | Atribución registrada por instantánea y en los resultados |
| Representatividad de las estaciones | Las estaciones de aeropuerto o de punto único pueden no representar los corredores | Métrica de distancia más advertencias de representatividad en los informes |

## 9. Enlaces oficiales de documentación

| Recurso | URL | Estado |
| --- | --- | --- |
| Referencia de GTFS Schedule | https://gtfs.org/documentation/schedule/reference/ | Oficial, estable |
| Referencia de GTFS Realtime | https://gtfs.org/documentation/realtime/reference/ | Oficial, estable |
| Portal de Cuenca en Datos | Portal de datos abiertos del Municipio de Cuenca (CKAN); enlaces a conjuntos de datos en las Secciones 2–3 | Verificado en la auditoría |
| INAMHI — raíz del portal oficial | https://www.inamhi.gob.ec/ | Raíz oficial |
| INAMHI — visor oficial | https://inamhi.gob.ec/info/visor/ | Verificado en la auditoría |
| INAMHI — catálogo de temperatura (media mensual) | https://datosabiertos.gob.ec/dataset/temperatura-media-mensual | Verificado en la auditoría |
| INAMHI — catálogo de precipitación (total mensual) | https://datosabiertos.gob.ec/dataset/precipitacion-total-mensual | Verificado en la auditoría |
| Guayaquil — servicio oficial ArcGIS PUGS | https://geoportalcat.guayaquil.gob.ec/arcgis/rest/services/PUGS_NORMATIVO_2023_2027/PUGS_NORMATIVO_2023_2027/MapServer?f=pjson | Verificado en la auditoría; condicional (sin licencia de reutilización explícita) |
| Quito — página oficial de movilidad | https://movilidad.quito.gob.ec/?page_id=476 | Verificado en la auditoría; sin feed/API pública documentada |
| Quito — referencia oficial de monitoreo | https://pasajeros.quito.gob.ec/?p=9821 | Verificado en la auditoría; solo referencia |
| MobilityDatabase — catálogo de feeds | https://mobilitydatabase.org/feeds | Solo catálogo; no es una fuente de datos |
| MobilityDatabase — CSV de feeds | https://files.mobilitydatabase.org/feeds_v2.csv | Solo catálogo; no es una fuente de datos |
| Servicios web NCEI CDO v2 | https://www.ncei.noaa.gov/cdo-web/webservices/v2 | Oficial |
| NCEI GHCN-Daily | https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily | Oficial |
| NCEI ISD | https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database | Oficial |
| Open-Meteo | https://open-meteo.com/ | Oficial |

## 10. Contratos canónicos de esquema

Convenciones: toda entidad lleva `snapshot_id` que referencia `source_snapshot`; las marcas de tiempo son ISO 8601; la zona horaria IANA es America/Guayaquil para los datos de Cuenca; UTC se usa para las marcas de tiempo normalizadas; la fecha de servicio GTFS es un identificador de día de servicio, no una fecha de calendario.

### 10.1 `source_snapshot`

| Aspecto | Contrato |
| --- | --- |
| Propósito | Un evento de recolección de un conjunto de datos de una fuente en un momento dado; el ancla de provenance de todas las demás entidades. |
| Campos requeridos | `snapshot_id`, `source_id`, `dataset_id`, `collection_timestamp_utc`, `source_published_at` (cuando la fuente lo proporciona), `source_url`, `license_declared`, `content_hash`, `row_count`, `status` (`success`/`partial`/`failed`), `schema_version`, `notes` |
| Semántica de marca de tiempo/zona horaria | `collection_timestamp_utc` es el momento en que el recolector obtuvo los datos, normalizado a UTC; `source_published_at` conserva la marca de tiempo publicada/actualizada de la propia fuente, reteniendo el valor local original cuando está presente y registrando su zona IANA. |
| Provenance | `source_url` exacta, método de obtención (API CKAN pública documentada), `license_declared` copiado de los metadatos del conjunto de datos, identificador de la ejecución del recolector. |
| Calidad | Integridad respecto de los campos esperados, detección de duplicados, `content_hash` para la detección de cambios entre instantáneas, `schema_version` para la deriva de esquema. |

### 10.2 `mobility_network`

| Aspecto | Contrato |
| --- | --- |
| Propósito | Elementos estáticos de la red — rutas y paradas — exactamente como se publicaron en una instantánea. |
| Campos requeridos | `network_id`, `snapshot_id`, `element_type` (`route`/`stop`), `route_line` (LINEA), `company` (COMPANIA), `direction` (SENTIDO), `origin` (ORIGEN), `destination` (DESTINO), `stop_id` (paradas), `stop_name` (paradas), `geometry` (punto de parada; geometría de rutas solo si el conjunto de datos condicional de recorrido se acepta más adelante) |
| Semántica de marca de tiempo/zona horaria | Sin marcas de tiempo de observación; relativa a la instantánea vía `snapshot_id`. Zona horaria IANA registrada para el conjunto de datos. |
| Provenance | Conjuntos de datos de rutas/paradas de Cuenca en Datos; `snapshot_id` enlaza con el evento de recolección y la URL exactos. |
| Calidad | Integridad por campo (p. ej., conteos de SENTIDO/DESTINO faltantes), detección de rutas/paradas duplicadas, validez de coordenadas, conteos informados por instantánea. |

### 10.3 `planned_service`

| Aspecto | Contrato |
| --- | --- |
| Propósito | Ventanas de servicio y headways planificados por ruta, dirección y tipo de día. |
| Campos requeridos | `service_id`, `snapshot_id`, `network_id`, `route_line`, `direction`, `day_type` (`weekday`/`weekend`), `planned_start` (relativo al día de servicio), `planned_end` (relativo al día de servicio), `planned_headway` (intervalo en minutos; del campo de intervalo del conjunto de datos cuando se publica; de lo contrario, derivado con el método registrado), `service_date` (fecha de servicio GTFS cuando el conjunto de datos la proporciona) |
| Semántica de marca de tiempo/zona horaria | **Todos los horarios son relativos al día de servicio y pueden superar las 24:00:00** (p. ej., 25:10:00 = 01:10 del día posterior a la fecha de servicio). Conservar el valor tal como se publicó; nunca convertirlo ingenuamente a una marca de tiempo de calendario. Cuando se requiera una marca de tiempo de calendario, aplicar el desfase del día de servicio explícitamente y documentarlo. IANA America/Guayaquil. |
| Provenance | Campos de rutas/horarios de Cuenca en Datos; `snapshot_id`. |
| Calidad | Verificaciones de cordura de ventanas en aritmética relativa al día de servicio (start < end), headway no negativo, integridad del tipo de día por ruta/dirección. |

### 10.4 `weather_observation`

| Aspecto | Contrato |
| --- | --- |
| Propósito | Observaciones meteorológicas registradas de una fuente autorizada; contexto para la auditoría, nunca causalidad. |
| Campos requeridos | `observation_id`, `snapshot_id`, `source_id`, `station_id`, `station_name`, `variable` (p. ej., `temperature`, `precipitation`), `value`, `unit`, `observed_at_local`, `observed_at_utc`, `timezone`, `data_kind` (`observed`/`modeled/reanalysis`), `license_declared`, `attribution` |
| Semántica de marca de tiempo/zona horaria | Conservar la marca de tiempo local original tal como se publicó (`observed_at_local`), registrar la zona horaria IANA (America/Guayaquil) y normalizar a UTC (`observed_at_utc`). La hora continental de Ecuador es UTC−5 todo el año sin horario de verano (DST); derivar UTC desde la zona IANA, no fijar desfases codificados. |
| Provenance | Catálogo mensual de INAMHI (CC BY) como fuente primaria; NCEI como respaldo histórico (token, límites documentados); Open-Meteo solo como `data_kind=modeled/reanalysis` y siempre etiquetado. |
| Calidad | Informe de brechas de estaciones, valores faltantes, consistencia de unidades, verificaciones de rango de valores, conteos de registros por estación. |

### 10.5 `weather_context`

| Aspecto | Contrato |
| --- | --- |
| Propósito | Vínculo derivado entre estaciones meteorológicas y corredores de tránsito — solo contexto de distancia; explícitamente no causal. |
| Campos requeridos | `context_id`, `snapshot_id`, `station_id`, `corridor_id`, `distance_m`, `distance_method`, `weather_reference` (FK hacia `weather_observation`), `data_kind` |
| Semántica de marca de tiempo/zona horaria | Hereda la semántica de `weather_observation`; calculada por instantánea. |
| Provenance | Entidad derivada: documenta sus entradas (`weather_observation`, corredores derivados de `mobility_network`) y su método (`distance_method`, p. ej., haversine hasta el punto de parada/ruta más cercano). |
| Calidad | Cobertura de corredores sin estación cercana informada; advertencias de representatividad de estaciones (p. ej., estación de aeropuerto) documentadas. |

### Nota de reserva futura (movilidad observada)

La movilidad observada — posiciones de vehículos, llegadas/salidas reales, retrasos, puntualidad, cancelaciones — **no tiene entidad actual**, y no existe ninguna tabla `mobility_observation` en el MVP. Una futura entidad de movilidad observada está reservada para una fuente autorizada de GTFS-Realtime/AVL y requiere una revisión del contrato antes de definir cualquier esquema.

## 11. Métricas permitidas del MVP

| # | Métrica permitida |
| --- | --- |
| 1 | Cobertura de rutas (conteos y cobertura geográfica por instantánea) |
| 2 | Cobertura de paradas (conteos y cobertura geográfica por instantánea) |
| 3 | Ventanas de servicio planificadas (inicio/fin por ruta, dirección y tipo de día) |
| 4 | Headway planificado (intervalo por ruta, dirección y tipo de día) |
| 5 | Cambios entre instantáneas (rutas, paradas, ventanas, headways) |
| 6 | Frescura (antigüedad de la instantánea respecto de la recolección/publicación) |
| 7 | Integridad (valores faltantes por campo y por conjunto de datos) |
| 8 | Duplicados (tasa sobre una muestra revisada) |
| 9 | Distancia desde las estaciones meteorológicas hasta los corredores de tránsito |

**No son métricas actuales del MVP** (reservadas para una futura fuente autorizada de GTFS-Realtime/AVL):

| Métrica reservada | Requisito (gate) |
| --- | --- |
| Retraso observado | Fuente autorizada de GTFS-RT/AVL |
| Puntualidad / porcentaje a tiempo | Fuente autorizada de GTFS-RT/AVL |
| Cancelaciones reales | Fuente autorizada de GTFS-RT/AVL |
| Posiciones de vehículos | Fuente autorizada de GTFS-RT/AVL |
| Fiabilidad del tiempo de viaje | Fuente autorizada de GTFS-RT/AVL |
| Causalidad meteorológica | Datos observados autorizados más una revisión explícita de diseño causal |

## 12. Reglas de tiempo

1. Conservar la marca de tiempo local original siempre que la fuente proporcione una.
2. Normalizar a UTC cuando corresponda, derivado de la zona horaria IANA (America/Guayaquil para Cuenca), nunca de un desfase asumido y codificado.
3. Registrar la fecha de servicio GTFS para los datos derivados de horarios; una fecha de servicio es un identificador de día de servicio, no una fecha de calendario.
4. **Conservar los tiempos relativos al día de servicio mayores que 24:00:00 tal como se publicaron (p. ej., 25:10:00). Nunca convertirlos ingenuamente a fechas de calendario.** Cualquier interpretación de calendario aplica el desfase del día de servicio explícitamente (25:10:00 en la fecha de servicio D es 01:10 en D+1) y queda documentada.
5. Las marcas de tiempo de recolección (`collection_timestamp_utc`) se registran en UTC y nunca se modifican.

## 13. Política de fixtures y datos raw

- **Hito aprobado (actual):** la recolección de instantáneas permite exactamente una captura explícita de instantánea actual por conjunto de datos aprobado de rutas/paradas mediante la API documentada CKAN `package_show`. Los bytes exactos del recurso se escriben en `data/raw/<dataset_id>/<UTC-stamp>.json` (ignorado por git) y un manifest JSON pequeño en `data/manifests/<dataset_id>/<UTC-stamp>.manifest.json` (versionado). El manifest registra la URL de la fuente, la licencia declarada (`CC BY-NC 2.0`), la marca de tiempo de recolección, el SHA-256 de los bytes exactos y un estado `success`/`partial`/`failed`.
- **Selección de recursos (política del hito aprobado):** de los recursos publicados de un conjunto de datos aprobado, solo son elegibles los recursos CSV que no identifiquen geometría, datos geoespaciales, geometría de rutas (recorrido) ni shapes (comparados sin distinción de mayúsculas/minúsculas en id/nombre/descripción/url del recurso). El recolector selecciona de forma determinista el CSV elegible **más nuevo**: la clave de actualidad es la señal más reciente entre la fecha de corte de datos embebida en el nombre/descripción del recurso (año de 4 dígitos con nombre de mes en español o inglés — p. ej. `2025Abril`, `2022Septiembre` — o un mes numérico) y las fechas de metadatos del recurso (`metadata_modified`, `last_modified`, `created`), con cada señal y finalmente el id estable del recurso como criterios de desempate deterministas. La selección nunca es posicional; los formatos ZIP/ODS/otros y los recursos de geometría se excluyen antes de la comparación de actualidad.
- **Invariantes de manifests fallidos:** los fallos previos a la descarga (paquete, licencia, formato, HTTP, red, cuerpo inválido) escriben un manifest `failed` con `raw_file = null`, `content_hash = null` y `row_count = null` — un manifest nunca apunta a un archivo raw que no existe. Cuando el cuerpo del recurso se descarga pero la decodificación/parseo CSV falla, los bytes exactos se conservan en la ruta raw determinista **antes** de escribir el manifest fallido; el manifest registra el error de codificación/validación, `row_count = null` y el SHA-256 calculado desde el archivo raw en disco.
- **Verificación de hash:** `content_hash` siempre se calcula desde el archivo raw en disco y se verifica contra él antes de escribir el manifest que lo contiene; un fallo de verificación elimina el archivo raw y no escribe ningún manifest.
- **Sin mutación silenciosa de manifests históricos:** los manifests históricos nunca se reescriben. Un manifest fallido cuyo archivo raw declarado falta (un huérfano) se reemplaza mediante un sidecar exclusivo `.manifest.correction.json` escrito por el helper offline `supersede_orphan_manifest(...)`: `status: superseded`, `raw_verifiable: false`, `raw_file`/`content_hash` de nivel superior en null, y la ruta/hash raw originales conservados solo bajo `unverified_original_claims` (no hay raw disponible; el hash original no está confirmado). El manifest original permanece byte-idéntico.
- **Sigue prohibido:** las descargas históricas masivas de las instantáneas 2022–2025, cualquier fuente o conjunto de datos más allá de los dos aprobados (incluida la geometría de rutas/recorrido), los fixtures raw de prueba commiteados y cualquier captura fuera del recolector documentado.
- Cualquier fixture futuro debe ser: pequeño, documentado, licenciado/permitido para redistribución y vinculado al `source_snapshot` del que proviene.
- Los conjuntos de datos raw grandes, las credenciales y el estado local de ejecución nunca se commitean.

### Resultado de la última captura autorizada

La segunda ejecución autorizada de `--dataset all` se realizó a las `2026-08-02T18:51:08Z`. Hizo dos solicitudes `package_show` y dos solicitudes de recursos CSV. Rutas se completó con éxito con el recurso `e55af215-4648-4e3b-84c9-d7e929435008` y 76 filas. Paradas falló la validación de cuerpo UTF-8 tras descargar el recurso `ffa506af-01c4-4b5b-afe2-e2f63b862ca6`; bajo la política de selección corregida, el CSV aprobado más reciente, `GADCuenca_ParadasTransporte_2025Abril.csv` (recurso `ed2f1b0f-73e5-4a59-acb4-394f8ec36d7e`), es el más nuevo de forma determinista y el CSV de septiembre de 2022 no se acepta como instantánea exitosa actual. El manifest fallido de paradas declaró un `raw_file`/`content_hash` huérfano porque el cuerpo inválido no se persistió; el hito de corrección offline lo reemplazó con `2026-08-02T18-51-08Z.manifest.correction.json` (estado `superseded`, `raw_verifiable: false`, ruta/hash originales solo como claims no verificados) sin reescribir el archivo original. **No ocurrió ninguna captura nueva en este hito de corrección** — las correcciones del recolector de preservación de bytes y verificación de hash en disco se aplicaron y probaron offline. Los manifests fallidos más antiguos permanecen inmutables. No se capturó ningún dato histórico masivo, de geometría, meteorológico ni operativo. La resolución técnica de compatibilidad de licencia no es asesoría legal, y no se autoriza ninguna captura adicional sin una nueva autorización explícita.

## 14. Hito de transformación canónica (implementado)

Implementado y probado en `src/mobility_reliability/validation/` y
`src/mobility_reliability/transformation/` (solo stdlib; totalmente offline; sin
red, sin captura, sin escrituras). Los manifests y raws capturados ahora se
parsean en las entidades de la Sección 10 con informes de calidad por
instantánea.

| Entidad / API | Contrato |
| --- | --- |
| `validate_source_snapshot(manifest_path, raw_dir)` | Validación estructural estricta de un manifest + sus bytes raw exactos; lanza `SnapshotValidationError` ante cualquier inconsistencia (fail closed); devuelve un `SourceSnapshot` con la proyección `source_snapshot` apta para JSON más manifest/raw/filas para las transformaciones |
| `transform_snapshot(manifest_path, raw_dir)` | Validación primero; luego `source_snapshot`, `mobility_network`, `planned_service`, `quality_report` |
| `transform_captures(route_manifest, stops_manifest, raw_dir)` | Las dos capturas aprobadas combinadas: dos `source_snapshots`, registros de red combinados, registros de ruta `planned_service`, dos informes de calidad |

### 14.1 Validación estricta de manifest/raw

- El manifest debe ser un objeto JSON con `status: success`; todos los campos requeridos no vacíos; la URL del conjunto de datos/fuente exactamente una de las dos URLs `package_show` aprobadas; el ID/formato del recurso y los metadatos del recurso seleccionado mutuamente consistentes; la huella de licencia `license_id=cc-nc` más la URL oficial de CC BY-NC 2.0; la marca de tiempo de recolección válida en UTC estricto y `source_published_at` requerido (ausente/vacío/inválido falla cerrado; se acepta la forma ISO naive del portal); `schema_version` un int positivo; `raw_file` relativo y dentro de `raw_dir`; SHA-256 bien formado e igual a los bytes raw; UTF-8/CSV bien formado y sin filas irregulares (non-ragged); `row_count` igual a las filas de datos CSV reales.
- Los metadatos del paquete (`source_metadata`) deben ser un objeto cuyo `name` coincida con el conjunto de datos y cuya lista `resources` contenga el ID del recurso seleccionado.
- El recurso seleccionado debe ser CSV y no geométrico; se rechazan la geometría de rutas (recorrido), ZIP/ODS y los recursos geoespaciales. La atribución y el ID del recurso se verifican.
- Una inconsistencia estructural manifest/raw **lanza una excepción**; nunca se degrada a una advertencia.

### 14.2 Transformación que preserva raw y semántica de calidad

- Cada fila raw se convierte exactamente en un registro de red (`element_type='route'` o `'stop'`); cada columna de entrada se conserva textualmente en un mapeo `raw`; los campos tipados en blanco se vuelven null (marcados `missing`), un SENTIDO no vacío fuera de IDA/RETORNO se marca `unknown`, y las coordenadas inválidas se marcan `syntax_invalid`/`out_of_range`; `network_id` es estable (instantánea + número de fila); la provenance (`source_snapshot_id`, `source_id`, `dataset_id`, `source_url`, `resource_id`, `raw_file`) viaja en cada registro.
- Coordenadas: sintaxis decimal estricta sin heurísticas (`-?\d+(\.\d+)?`, dígitos ASCII) más **solo rangos globales** (latitud [-90, 90], longitud [-180, 180]). `-2.895.956` es sintaxis inválida; `-290.179` está fuera de rango; tres decimales nunca se leen como separadores de miles; sin bounding box de Cuenca; los valores raw nunca se corrigen. Las coordenadas tipadas inválidas son null con un flag de calidad explícito. Una geometría de punto de parada existe solo cuando AMBAS coordenadas pasan; no se crea ninguna geometría de rutas.
- Horarios: un registro `planned_service` por fila de ruta y tipo de día (weekday/saturday/sunday) con minutos de día de servicio tipados (`0:09` → 9) y texto H:MM explícito en `*_raw`; los valores por encima de 24:00 se conservan sin conversión de calendario; el centinela exacto `0:00/0:00/0:00` es `service_status='no_service'` (ceros tipados conservados, nunca una ventana activa inválida); las ventanas activas requieren start < end y headway > 0; los intervalos malformados/ausentes/negativos/cero y las violaciones de cronología anulan los valores tipados afectados con flags de calidad y se informan; `service_date` nunca se inventa (null).
- Informes de calidad: conteos de filas/esperadas (el conteo esperado es una verificación no universal aplicada solo a los dos IDs de recurso aprobados conocidos — rutas 76, paradas 383), conteos de campos faltantes, duplicados de fila completa y de clave natural (clave de ruta `(LINEA, COMPANIA, SENTIDO, ORIGEN, DESTINO)`; clave de parada `(N,)`), conteos de SENTIDO unknown, conteos de coordenadas inválidas y cobertura de puntos válidos, conteos de horarios malformados/inválidos/sin servicio/intervalos, advertencias, errores y cobertura de elementos limpios. Los problemas de calidad de datos permanecen como flags/advertencias observables — las filas raw nunca se corrigen ni descartan silenciosamente.
- Solo planificado: sin meteorología, sin GTFS-Realtime/AVL, sin geometría de rutas, sin dashboards; la transformación no hace afirmaciones de movilidad observada.

### 14.3 Métricas observadas de las capturas aprobadas (2026-08-02)

| Instantánea | Métricas de calidad observadas |
| --- | --- |
| Rutas (76 filas) | ORIGEN en blanco en 4 filas, DESTINO en blanco en las mismas 4 filas; SENTIDO solo IDA (38) / RETORNO (38); 684 celdas de horario, 0 malformadas, 0 por encima de 24:00; 228 ventanas activas, 0 inválidas; 8 ventanas sin servicio (líneas 21/23 × ambas direcciones × sábado/domingo); 0 duplicados; 68/76 registros limpios |
| Paradas (383 filas) | Todos los campos no vacíos; 0 duplicados; latitud syntax-invalid 331 / out-of-range 48 / valid 4; longitud syntax-invalid 374 / out-of-range 4 / valid 5; 0 filas con ambas coordenadas válidas (cobertura de puntos 0.0); `?` ASCII literal en 5 valores de `Ubicacion` (filas 5, 6, 46, 47, 115 — conservados, nunca corregidos) |

## Lista de verificación

- [ ] Todo conjunto de datos usado en el MVP está en un nivel "Aceptado" de la Sección 7 con una licencia declarada.
- [ ] Ninguna métrica fuera de la lista permitida de la Sección 11 se calcula ni se muestra.
- [ ] Ninguna entidad actual contiene campos de movilidad observada; no existe ninguna tabla `mobility_observation`.
- [ ] Todos los horarios son relativos al día de servicio; no existe ninguna conversión ingenua >24:00:00.
- [ ] Los datos meteorológicos están etiquetados con `data_kind`; no aparece ninguna afirmación causal en ninguna parte.
- [ ] Las URLs y licencias exactas de las fuentes se registran en `source_snapshot` para cada evento de recolección.
- [ ] Cualquier cambio de fuentes, entidades o métricas revisa este contrato antes de los cambios de implementación.

## Próximo paso

El hito de transformación canónica (Sección 14) está implementado: los manifests y raws capturados se parsean en `source_snapshot`, `mobility_network` y `planned_service` con informes de calidad por instantánea, todo fijado por pruebas (incluida la triangulación contra los raws capturados). Próximo: verificaciones de frescura, contratos de esquema (Pandera o equivalente) sobre las entidades canónicas, análisis de cambios entre instantáneas y análisis geoespacial.
