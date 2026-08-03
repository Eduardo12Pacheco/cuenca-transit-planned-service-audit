# Fixture sintético de demostración (`data/demo/`)

Este directorio contiene el fixture de demostración del **modo sintético** de la
demo Streamlit:

- `synthetic-combined.json` — salida con forma canónica (la forma de
  `transform_captures`) con registros **completamente ficticios**: rutas,
  paradas, `planned_service` (los tres tipos de día: `weekday`, `saturday`,
  `sunday`), reportes de calidad, snapshots/provenance sintéticos y un payload
  de auditoría de coordenadas sintético con decisión `format_unresolved`.

## ⚠️ Advertencia: datos sintéticos, no oficiales

**TODO el contenido de este fixture es ficticio y no describe el servicio real
de transporte público de Cuenca.** No fue producido por la transformación real
sobre capturas oficiales y no contiene hashes reales, IDs de recurso, URLs de
fuente, licencias, atribuciones ni métricas de filas oficiales. En la demo, el
modo sintético lo etiqueta de forma prominente:

> **Modo demostración: los datos mostrados son completamente sintéticos, no son
> datos oficiales y no describen el servicio real de Cuenca.**

El fixture **nunca** se usa cuando existe evidencia real: el cargador de la demo
(`app/_data.py`) solo entra en modo sintético cuando **ninguno** de los dos
archivos raw aprobados está presente (p. ej. un checkout limpio, es decir, una copia
limpia del repositorio), y falla de
forma estricta ante evidencia parcial, malformada o inválida.

## Autoría y no derivación

Creado **desde cero** por los autores del repositorio (`fixture.authored_by` /
`fixture.authored_date` en el JSON) como obra de demostración. No se deriva de
capturas oficiales, de archivos raw, de los tests ni de ningún otro artefacto
del repositorio: todos los IDs (`DEMO-01`, `S-DEMO-01`, …), nombres, empresas,
horarios y coordenadas son inventados. La forma del JSON replica la salida
canónica para que la demo consuma exactamente las mismas vistas.

## Limitaciones del modo demostración

- **Solo servicio planificado**: ventanas e intervalos planificados ficticios;
  no es puntualidad, retrasos, frecuencia observada, GTFS-Realtime, AVL ni
  movilidad en tiempo real.
- **Sin cobertura geográfica**: las coordenadas son texto sin resolver
  (`format_unresolved`) y ninguna parada tiene geometría; no se muestra mapa.
- **Sin evidencia oficial**: no hay snapshots aprobados detrás de estos
  valores; los `content_hash`, IDs y URLs del fixture son ficticios.

## Procedencia técnica (`provenance`)

- `fixture.origin`, `fixture.authored_date`, `fixture.snapshots` y
  `fixture.limitations` del propio JSON describen el origen y el alcance.
- La demo renderiza esta información en la pestaña «Evidencia y provenance —
  modo demostración» (solo en modo sintético).
- Los `source_snapshots` del fixture son objetos de forma canónica con valores
  ficticios; **no** son manifest ni evidencia de captura.

## Reutilización del fixture (declaración propia)

Este fixture es una obra sintética creada por los autores del repositorio y no
contiene datos de terceros. Se concede una **licencia permisiva simple** para
este fixture: cualquiera puede copiarlo, modificarlo y redistribuirlo, incluso
comercialmente, con atribución a los autores del repositorio y **sin garantías**
de ningún tipo. Esta declaración **no depende de ninguna autorización de
terceros** porque el fixture no incorpora datos, textos ni métricas de fuentes
oficiales; tampoco está sujeto a la licencia no comercial de los snapshots
oficiales (que, de todos modos, no se redistribuyen en este repositorio). No
utilice este fixture para afirmar nada sobre el servicio real de Cuenca.
