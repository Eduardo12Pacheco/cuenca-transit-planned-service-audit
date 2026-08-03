# Guion de demo — 60–90 segundos (Streamlit sin conexión)

Un recorrido ágil (duración objetivo: **60–90 segundos**) de la demo local sin conexión. Todo lo mostrado es
**servicio planificado únicamente**: filas de rutas, ventanas planificadas e
intervalos planificados (de los snapshots aprobados en el modo evidencia real,
o ficticios en el modo demostración). NO es puntualidad,
retrasos, frecuencia observada, GTFS-Realtime, AVL ni cobertura geográfica —
y no se muestra ningún mapa por decisión de calidad.

La demo tiene **dos modos**, decididos por la presencia de los dos raw
aprobados en `data/raw/`:

- **Modo evidencia real** — ambos raw aprobados presentes: los snapshots
  exactos (76 rutas / 383 paradas), con hashes y provenance inmutables.
- **Modo demostración** — ningún raw aprobado presente (checkout limpio):
  el fixture sintético versionado `data/demo/synthetic-combined.json`, con
  valores ficticios y un aviso prominente de que **no son datos oficiales**.

Ambos modos comparten el límite planificado, las cuatro vistas y la frase de no
mostrar mapa. Los números citados en cada recorrido son los de su modo.

## Modo demostración — checkout limpio sin `data/raw/` (60–90 segundos)

Recorrido para un clon público sin los raw (git-ignorados). Todo lo mostrado es
**ficticio y etiquetado como tal**; sirve para demostrar la app, no el servicio
real.

### 0. Arranque y aviso sintético (0–10 s)

```bash
UV_OFFLINE=1 uv sync --extra demo
uv run --extra demo streamlit run app/streamlit_app.py
```

Evidencia visible esperada al iniciar, **antes de cualquier métrica**, el aviso
amarillo exacto:

> **Modo demostración: los datos mostrados son completamente sintéticos, no son
> datos oficiales y no describen el servicio real de Cuenca.**

Junto al aviso de límite planificado («Esta demo muestra únicamente servicio
planificado…») y la barra lateral con **Selección** (Línea / Sentido / Tipo de
día) y la evidencia marcada `(sintético)`.

### 1. Servicio planificado activo (10–30 s)

Línea `DEMO-01` · IDA · Entre semana (valores por defecto): el resumen muestra
`ventana planificada 6:00–20:00 … intervalo planificado 0:15 … Estado: Activo`
y la tabla principal lista las filas `DEMO-01` (IDA y RETORNO), `DEMO-02` y
`DEMO-03` con sus ventanas ficticias.

### 2. Ventana sin servicio (30–45 s)

Barra lateral → **Línea** → `DEMO-02` · **Tipo de día** → `Domingo`. El resumen
dice `SIN SERVICIO: la fuente publica el centinela 0:00/0:00/0:00 (no hay
ventana planificada). Estado: Sin servicio.` y la tabla **Ventanas sin
servicio** lista las 3 ventanas ficticias (DEMO-02 domingo; DEMO-03 sábado y
domingo).

### 3. Calidad de paradas y no-mapa (45–60 s)

Pestaña → **Calidad de paradas**: métricas ficticias `Paradas 4`, `Paradas con
geometría válida 0`, `Latitud: sintaxis/problema 3`, `Latitud: fuera de rango
1`; la decisión de auditoría **`format_unresolved`** marcada como **sintética**
y la frase exacta de no mostrar mapa.

### 4. Evidencia del modo demostración (60–75 s)

Pestaña → **Evidencia y provenance — modo demostración**: advertencia de que
TODO es sintético, origen del fixture (`data/demo/synthetic-combined.json`,
`fixture synthetic-combined`), snapshots ficticios `demo-rutas@2024-01-15…` y
`demo-paradas@2024-01-15…` marcados `(sintético)` — **sin hashes, IDs de
recurso, URLs ni licencias oficiales** (ver `data/demo/README.md`).

### Frase final del modo demostración

*«Esta es una demo en modo demostración: todos los valores son sintéticos y no
describen el servicio real de Cuenca. Muestra las vistas y el flujo de la app;
la evidencia real con los snapshots aprobados se ejecuta cuando los raws están
presentes.»*

---

## Modo evidencia real — snapshots aprobados (60–90 segundos)

Con los dos raw aprobados presentes en `data/raw/` (rutas
`2026-08-02T18-51-08Z` y paradas `2026-08-02T19-27-36Z`), la demo usa la
validación estricta y los valores exactos de siempre; **no hay ningún aviso de
modo demostración**. El fixture sintético nunca se usa en este modo.

### Preparación (antes de arrancar el cronómetro)

```bash
# una vez: resolver e instalar el extra demo fijado desde la caché local de uv (sin conexión)
UV_OFFLINE=1 uv sync --extra demo

# iniciar la demo
uv run --extra demo streamlit run app/streamlit_app.py
```

Abrir la URL local indicada (por defecto `http://localhost:8501`). Evidencia
visible esperada al iniciar: el título **«Auditoría del servicio planificado
de transporte público de Cuenca»**, el aviso amarillo de límite planificado
(«Esta demo muestra únicamente servicio planificado. No representa
puntualidad, retrasos, frecuencia observada, GTFS-Realtime, AVL ni cobertura
geográfica.») y la barra lateral con **Selección** (Línea / Sentido / Tipo de
día) más el indicador **Evidencia del snapshot**
(`rutas-de-transporte-publico@2026-08-02T18-51-08Z` y
`paradas-de-transporte-publico@2026-08-02T19-27-36Z`).

### Los 60–90 segundos (modo evidencia real)

### 1. Seleccionar una línea (0–10 s)

Barra lateral → **Línea**. Mantener la predeterminada (línea `1`) o elegir
cualquier línea; Sentido `IDA` y Tipo de día `Entre semana` quedan por
defecto.

Evidencia visible esperada: el encabezado de la pestaña Servicio planificado
se actualiza a `Línea 1 · IDA · Entre semana` y el resumen muestra la ventana
y el intervalo planificados, p. ej. `ventana planificada 5:50–21:15 …
intervalo planificado 0:09 … Estado: Activo`.

### 2. Inspeccionar el horario planificado (10–25 s)

La pestaña Servicio planificado muestra **las 76 filas de rutas** para el
tipo de día seleccionado: ventanas e intervalos planificados con los
**valores raw H:MM** (`5:50`, `21:15`, `0:09`) en las columnas `Inicio`,
`Fin` e `Intervalo`, el estado (`Activo` / `Sin servicio` / `Inválido`) en la
columna `Estado`, las incidencias legibles en `Incidencias de calidad` y los
códigos técnicos bajo «Ver valores raw y códigos técnicos».

Evidencia visible esperada: una tabla de 76 filas con las columnas `Línea`,
`Empresa`, `Sentido`, `Origen`, `Destino`, `Inicio`, `Fin`, `Intervalo`,
`Estado` e `Incidencias de calidad`; al desplegar el expander técnico se ven
`service_status`, `planned_start`, `planned_headway_raw`, `service_id` y
`provenance.*`.

### 3. Cambiar el tipo de día (25–35 s)

Barra lateral → **Tipo de día** → `Sábado`.

Evidencia visible esperada: el encabezado cambia a `… · Sábado`; las filas de
las líneas `21` y `23` (ambos sentidos) pasan a estado **Sin servicio**.

### 4. Inspeccionar una ventana sin servicio (35–45 s)

Barra lateral → **Línea** → `21`, manteniendo `Sábado`. Debajo de la tabla
principal, la tabla **Ventanas sin servicio** lista las 8 ventanas (líneas
21 y 23 × IDA/RETORNO × Sábado/Domingo).

Evidencia visible esperada: el resumen dice `SIN SERVICIO: la fuente publica
el centinela 0:00/0:00/0:00 (no hay ventana planificada). Estado: Sin
servicio.` — un centinela publicado, nunca una ventana activa inválida.

### 5. Abrir calidad de paradas (45–52 s)

Pestaña → **Calidad de paradas**.

Evidencia visible esperada: métricas `Paradas 383`, `Paradas con geometría
válida 0`, `Latitud: sintaxis/problema 331`, `Latitud: fuera de rango 48`,
`Longitud: sintaxis/problema 374`, `Longitud: fuera de rango 4`; la decisión
de auditoría **`format_unresolved`**; ejemplos raw exactos como `-2.895.956`
(fila 1) y `-79.014.574` (fila 1), etiquetados como valores raw exactos,
limitados y nunca convertidos.

### 6. Explicar por qué no se muestra mapa (52–60 s)

La vista de calidad de paradas encabeza con la frase de decisión:

> **No se muestra un mapa porque el formato de las coordenadas, el orden de
> los ejes y el sistema de referencia CRS no están resueltos.**

Decirlo en voz alta: *«Esta es una decisión de calidad de datos, no una
función faltante. Los valores `Latitud`/`Longitud` de la fuente mezclan
numerales agrupados y valores fuera de rango; la auditoría no puede probar el
formato, el orden de los ejes ni el CRS, y `Ubicacion` es un campo de
dirección/nombre — nunca coordenadas. La demo no convierte y no dibuja ningún
mapa. La pestaña Evidencia y provenance ata cada valor a los dos snapshots
exactos, sus SHA-256 raw y sus licencias declaradas CC BY-NC 2.0 — registros
técnicos, no asesoramiento legal.»*

Evidencia visible esperada: la frase exacta renderizada en la app, y en la
pestaña Evidencia y provenance los IDs de snapshot/recurso, los SHA-256 raw
(`dc3082ad…88ee07a`, `20969d2e…bdc62c`), las marcas de recopilación y las
licencias.

## Camino de fallo (si preguntan)

- **Un único raw aprobado presente** (falta el otro): cartel de error claro
  (`partial evidence`) que nombra los raw esperados — sin rastreos de error,
  sin valores inventados y **sin respaldo sintético**.
- **Evidencia real inválida** (raw corrupto, hash distinto, manifest
  inconsistente): la validación estricta falla y la app muestra el cartel de
  error con la identidad esperada — nunca el fixture.
- **Fixture ausente o malformado** en modo demostración: cartel de error claro
  que nombra el fixture — sin valores.
- **Checkout limpio (ningún raw): NO es un error**: entra en modo demostración
  con el fixture sintético etiquetado de forma prominente (ver recorrido
  arriba).

### Frase final del modo evidencia real (honesta)

*«Esta demo es una auditoría de servicio planificado construida sobre dos snapshots aprobados de Cuenca en Datos. Muestra lo que la fuente publica como planificado — ventanas e intervalos —; no mide puntualidad ni retrasos, y no muestra mapa porque el formato, el orden de los ejes y el CRS de las coordenadas no están resueltos. El código, los manifests, la auditoría de coordenadas y esta captura son reproducibles; los bytes raw no se redistribuyen por su licencia no comercial.»*

## Lista de verificación anti-afirmaciones

- [ ] Nunca decir «cobertura de red», «rutas confiables», «servicio puntual»,
      «mapa de movilidad» ni «movilidad en tiempo real» como logros.
- [ ] Decir «filas limpias del snapshot validado» para 68/76 — nunca
      cobertura completa.
- [ ] Decir «planificado» antes de cada afirmación de horario.
