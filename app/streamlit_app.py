"""Demo local de Streamlit (sin conexión) — Auditoría del servicio planificado
de transporte público de Cuenca.

Ejecutar desde la raíz del repositorio (sin red):

    uv run --extra demo streamlit run app/streamlit_app.py

La app es SOLO LECTURA y está respaldada por los snapshots: renderiza la
salida canónica de ``transform_captures`` y el artefacto de auditoría de
coordenadas existente. Nunca escribe, nunca captura y nunca vuelve a
implementar parsing. Un aviso destacado de límite planificado está siempre
visible: esto es servicio planificado, no puntualidad, retrasos, frecuencia
observada, GTFS-Realtime, AVL ni cobertura geográfica.

La app tiene dos modos de datos decididos por ``load_demo_payload``:

- ``real`` — los dos snapshots aprobados (manifests versionados + raws en
  ``data/raw/``) con la validación estricta y la auditoría real, sin cambios.
- ``synthetic`` — SOLO cuando no existe ningún raw aprobado (checkout
  limpio): el fixture canónico versionado ``data/demo/synthetic-combined.json``
  con valores ficticios, etiquetado de forma prominente como no oficial.

Reglas fail-closed (sin respaldo sintético): un único raw presente, evidencia
real inválida, o un fixture ausente/malformado/inválido muestran un cartel de
error claro con la identidad esperada — sin rastreos de error y sin valores
inventados.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Hace que la raíz del repositorio sea importable para que `streamlit run app/streamlit_app.py`
# funcione desde cualquier directorio (bajo pytest no tiene efecto).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402

from app import _data as data  # noqa: E402
from app import _i18n as i18n  # noqa: E402
from app import _views as views  # noqa: E402

st.set_page_config(
    page_title=i18n.APP_TITLE,
    layout="wide",
)

st.title(i18n.APP_TITLE)
st.warning(data.PLANNED_ONLY_BOUNDARY)

# ---------------------------------------------------------------------------
# Carga de evidencia (solo lectura). Cualquier fallo -> cartel claro, sin
# rastreo de error. ``load_demo_payload`` decide el modo por la presencia de
# los dos raw aprobados; el modo sintético nunca sustituye evidencia real.
# ---------------------------------------------------------------------------
try:
    payload = data.load_demo_payload()
except data.SyntheticFixtureError as exc:  # fixture ausente/malformado/inválido
    st.error(data.load_fixture_failure_message(exc))
    st.stop()
except Exception as exc:  # límite de la demo: nunca mostrar un traceback
    st.error(
        data.load_failure_message(
            exc,
            route_manifest=data.ROUTES_MANIFEST,
            stops_manifest=data.STOPS_MANIFEST,
            raw_dir=data.RAW_DIR,
        )
    )
    st.stop()

mode = payload["mode"]
combined = payload["combined"]
audit = payload["audit"]
if mode == data.DATA_MODE_SYNTHETIC:
    # Aviso prominente ANTES de cualquier métrica: los datos son ficticios.
    st.warning(data.SYNTHETIC_MODE_BANNER)
if audit is None:
    st.info(
        "El artefacto de auditoría de coordenadas no está disponible o no es "
        "legible; la vista de calidad de paradas muestra solo los conteos de "
        "la transformación, sin decisión de auditoría."
    )

# ---------------------------------------------------------------------------
# Barra lateral: selección + indicador de evidencia del snapshot
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header(i18n.SIDEBAR_SELECTION)
    line = st.selectbox(i18n.SIDEBAR_LINE, views.route_lines(combined), key="line")
    direction = st.selectbox(i18n.SIDEBAR_DIRECTION, list(data.DIRECTION_VALUES), key="direction")
    day_type = st.selectbox(
        i18n.SIDEBAR_DAY_TYPE,
        views.day_types(combined),
        key="day_type",
        format_func=lambda day: data.DAY_TYPE_LABELS.get(day, day),
    )
    st.divider()
    st.markdown(f"**{i18n.SIDEBAR_EVIDENCE}**")
    if mode == data.DATA_MODE_SYNTHETIC:
        st.caption(data.SYNTHETIC_EVIDENCE_HINT)
        for snapshot in combined["source_snapshots"]:
            st.markdown(
                f"- `{snapshot['dataset_id']}` (sintético)\n"
                f"  {snapshot['snapshot_id']}\n"
                "  fixture ficticio, no una captura oficial"
            )
    else:
        st.caption(i18n.SIDEBAR_EVIDENCE_HINT)
        for snapshot in combined["source_snapshots"]:
            st.markdown(
                f"- `{snapshot['dataset_id']}`\n"
                f"  {snapshot['snapshot_id']}\n"
                f"  recopilado {snapshot['collection_timestamp_utc']}"
            )

# ---------------------------------------------------------------------------
# Vistas
# ---------------------------------------------------------------------------
planned_tab, quality_tab, stops_tab, evidence_tab = st.tabs(
    [i18n.TAB_PLANNED, i18n.TAB_ROUTE_QUALITY, i18n.TAB_STOPS_QUALITY, i18n.TAB_EVIDENCE]
)

with planned_tab:
    day_label = data.DAY_TYPE_LABELS[day_type]
    st.subheader(f"Línea {line} · {direction} · {day_label}")
    window = views.selected_window(combined, line, direction, day_type)
    if window is None:
        if mode == data.DATA_MODE_SYNTHETIC:
            st.markdown(
                "No hay ningún registro de servicio planificado que coincida "
                "con esta selección en el fixture sintético."
            )
        else:
            st.markdown(
                "No hay ningún registro de servicio planificado que coincida con "
                "esta selección en el snapshot capturado."
            )
    elif window["status"] == "no_service":
        st.markdown(
            f"**Línea {line} · {direction} · {day_label}** — SIN SERVICIO: "
            "la fuente publica el centinela 0:00/0:00/0:00 "
            "(no hay ventana planificada). Estado: Sin servicio."
        )
    elif window["status"] == "invalid":
        st.markdown(
            f"**Línea {line} · {direction} · {day_label}** — ventana INVÁLIDA; "
            "incidencias de calidad: "
            f"{views.readable_flags(window['flags']) or 'ninguna'}. "
            "Estado: Inválido."
        )
    else:
        st.markdown(
            f"**Línea {line} · {direction} · {day_label}** — "
            f"ventana planificada {window['start_raw']}–{window['end_raw']} "
            f"(minutos del día de servicio {window['start_minutes']}–{window['end_minutes']}), "
            f"intervalo planificado {window['headway_raw']} "
            f"(cada {window['headway_minutes']} min). Estado: Activo."
        )

    st.markdown(
        f"Todas las filas de rutas para **{day_label}** — ventanas e intervalos "
        "planificados con los valores raw H:MM de la fuente y el estado "
        "(Activo / Sin servicio / Inválido) con sus incidencias de calidad."
    )
    st.dataframe(
        views.service_table_rows(combined, day_type),
        hide_index=True,
        width="stretch",
    )

    with st.expander(i18n.EXPANDER_TECHNICAL):
        st.caption(i18n.EXPANDER_TECHNICAL_HINT)
        details = views.technical_detail_rows(combined, line, direction, day_type)
        if details is None:
            st.markdown("No hay registro técnico para esta selección.")
        else:
            # Coerción de visualización: todos los valores como texto para que el dataframe
            # sea estable en tipos.
            display_details = [
                {
                    "campo": detail["campo"],
                    "valor": "" if detail["valor"] is None else str(detail["valor"]),
                }
                for detail in details
            ]
            st.dataframe(display_details, hide_index=True, width="stretch")

    st.markdown(
        f"**Ventanas sin servicio** "
        f"({views.route_quality_summary(combined)['no_service_windows_count']}) "
        "— los centinelas exactos 0:00/0:00/0:00, nunca ventanas activas inválidas."
    )
    st.dataframe(views.no_service_window_table_rows(combined), hide_index=True, width="stretch")

with quality_tab:
    st.subheader("Calidad de rutas — filas de rutas planificadas")
    quality = views.route_quality_summary(combined)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rutas", quality["row_count"])
    c2.metric("Origen sin valor", quality["missing_origen"])
    c3.metric("Destino sin valor", quality["missing_destino"])
    c4.metric("Ventanas sin servicio", quality["no_service_windows_count"])
    c1.metric("Sentido IDA", quality["sense_counts"]["IDA"])
    c2.metric("Sentido RETORNO", quality["sense_counts"]["RETORNO"])
    c3.metric(
        "Celdas de horario válidas",
        f"{quality['schedule_cells'] - quality['schedule_cells_malformed']} de {quality['schedule_cells']}",
    )
    c4.metric(
        "Intervalos válidos",
        f"{quality['interval_cells'] - quality['interval_cells_invalid']} de {quality['interval_cells']}",
    )
    c1.metric("Filas limpias", quality["elements_clean"])
    st.markdown(
        f"**{quality['elements_clean']}/{quality['elements_total']}** son "
        f"{quality['clean_label']} (sin incidencias de calidad) — no es "
        "cobertura geográfica ni de red."
    )
    st.dataframe(views.route_table_rows(combined), hide_index=True, width="stretch")

with stops_tab:
    st.subheader("Calidad de paradas — coordenadas sin resolver")
    stops = views.stops_quality_summary(combined, audit)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Paradas", stops["row_count"])
    c2.metric("Paradas con geometría válida", stops["geometry_rows"])
    c3.metric(
        "Latitud: sintaxis/problema",
        (stops["latitude"] or {}).get("syntax_invalid", 0),
    )
    c4.metric(
        "Latitud: fuera de rango",
        (stops["latitude"] or {}).get("out_of_range", 0),
    )
    c1.metric(
        "Longitud: sintaxis/problema",
        (stops["longitude"] or {}).get("syntax_invalid", 0),
    )
    c2.metric(
        "Longitud: fuera de rango",
        (stops["longitude"] or {}).get("out_of_range", 0),
    )

    st.markdown(f"**{data.NO_MAP_DECISION}**")
    st.markdown(
        "Esta es una **decisión de calidad de datos**, no una función "
        "faltante: no se puede dibujar un mapa porque la fuente no permite "
        "probar el formato, el orden de los ejes ni el CRS. `Ubicacion` es el "
        "campo de dirección/nombre de la parada y NUNCA se usa como "
        "coordenadas."
    )

    if stops["audit_decision"]:
        st.markdown(
            f"Decisión de auditoría: **`{stops['audit_decision']}`** "
            f"(format_resolved={stops['audit_format_resolved']}, "
            f"conversion_justified={stops['audit_conversion_justified']}, "
            f"geometry_generated={stops['audit_geometry_generated']})"
        )
        if mode == data.DATA_MODE_SYNTHETIC:
            st.markdown("Decisión y valores **sintéticos** (fixture de demostración) — ver `data/demo/README.md`.")
        else:
            st.markdown("— ver `docs/coordinate-quality-audit.md`.")
        st.markdown(f"SHA-256 de los valores auditados: `{stops['audit_raw_sha256']}`")
        if mode == data.DATA_MODE_SYNTHETIC:
            st.markdown(
                "Valores ficticios de `Latitud`/`Longitud` (primeras "
                "ocurrencias, limitados; no se convierte ni se interpreta nada):"
            )
        else:
            st.markdown(
                "Valores raw exactos de `Latitud`/`Longitud` (primeras "
                "ocurrencias, limitados; no se convierte ni se interpreta nada):"
            )
        if audit is not None:
            for column, category in views.audit_columns_with_examples(audit):
                examples = views.audit_example_rows(audit, column, category, cap=5)
                gloss = i18n.CATEGORY_GLOSSES.get(category, category)
                st.markdown(f"**{column} — {category}** ({examples['total']} valores; {gloss})")
                for example in examples["rows"]:
                    st.markdown(f"- Fila {example['row']}: `{example['value']}`")
    else:
        st.markdown("Decisión de auditoría: no disponible (artefacto ilegible).")

with evidence_tab:
    if mode == data.DATA_MODE_SYNTHETIC:
        st.subheader("Evidencia y provenance — modo demostración")
        st.warning(data.SYNTHETIC_PROVENANCE_WARNING)
        fixture_meta = combined.get("fixture") or {}
        st.markdown(data.SYNTHETIC_PROVENANCE_INTRO.format(fixture_name=fixture_meta.get("name", "desconocido")))
        for snapshot in fixture_meta.get("snapshots") or []:
            st.markdown(
                f"- `{snapshot['dataset_id']}` — `{snapshot['snapshot_id']}` "
                f"— filas: {snapshot['row_count']} **(sintético)**"
            )
        st.markdown("### Decisión de auditoría de coordenadas (sintética)")
        st.markdown(
            "Decisión: **`format_unresolved`** con valores ficticios — ver "
            "`data/demo/README.md`. La demo no muestra mapa por esta decisión."
        )
    else:
        st.subheader("Evidencia y provenance")
        st.markdown(
            "Todos los valores de esta demo provienen de los dos snapshots "
            "aprobados que se listan abajo. Las decisiones de compatibilidad de "
            "licencia son técnicas y no constituyen asesoramiento legal."
        )
        for row in views.provenance_rows(combined):
            st.markdown(
                f"### {row['dataset_id']} — {row['snapshot_id']}\n"
                f"- resource_id: `{row['resource_id']}`\n"
                f"- recurso: {row['resource_name']}\n"
                f"- archivo raw: `{row['raw_file']}`\n"
                f"- SHA-256 del archivo raw: `{row['content_hash']}`\n"
                f"- recopilado: {row['collection_timestamp_utc']} · "
                f"publicado por la fuente: {row['source_published_at']}\n"
                f"- filas: {row['row_count']} · estado: {row['status']}\n"
                f"- licencia: {row['license_declared']} (`{row['license_id']}`) — "
                f"{row['license_url']}\n"
                f"- atribución: {row['attribution']}\n"
                f"- método de obtención: {row['retrieval_method']}\n"
                f"- recurso creado: {row['resource_created']} · "
                f"última modificación: {row['resource_last_modified']}\n"
                f"- URL de la fuente: {row['source_url']}"
            )
        st.markdown("### Decisión de auditoría de coordenadas")
        st.markdown(
            "Decisión: **`format_unresolved`** — ver el informe en "
            "`docs/coordinate-quality-audit.md` y el JSON en "
            "`data/quality/coordinate-format-audit.json`. La demo no muestra mapa "
            "por esta decisión."
        )
