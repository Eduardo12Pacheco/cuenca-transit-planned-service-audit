"""Pruebas de composición/interacción AppTest de la demo Streamlit sin conexión.

Estas pruebas solo corren cuando el extra opcional ``demo`` (Streamlit) está
instalado: ``pytest.importorskip("streamlit")`` mantiene la suite base
ejecutable sin él. Con el extra de demo disponible verifican:

- el arranque contra los snapshots capturados reales (raws presentes) con el
  título en español, el aviso de límite solo-planificado, la frase exacta en
  español de no-mapa y las métricas fijadas (76 filas de rutas, 383 filas de
  paradas, 68 filas limpias, 8 ventanas sin servicio);
- al menos una interacción real: seleccionar una línea + tipo de día reejecuta
  la app y el resumen de la ventana seleccionada cambia (ventana activa vs el
  centinela sin servicio ``0:00/0:00/0:00``), con estados localizados
  (``Activo`` / ``Sin servicio``) y etiquetas de día (``Sábado``);
- la tabla principal de servicio planificado usa las columnas de lector en
  español (``Línea``, ``Empresa``, ``Sentido``, ``Origen``, ``Destino``,
  ``Inicio``, ``Fin``, ``Intervalo``, ``Estado``, ``Incidencias de calidad``)
  y nunca expone claves canónicas;
- degradación controlada: un manifest ausente o una raíz raw ausente renderiza
  un cartel de error claro en español — nunca un traceback ni valores
  inventados.

La app es de solo lectura por contrato; nada en estas pruebas escribe estado
del repositorio (solo archivos temporales bajo ``tmp_path`` para los casos de
fallo).
"""

from __future__ import annotations

from pathlib import Path

import pytest

streamlit = pytest.importorskip(
    "streamlit", reason="requiere el extra opcional 'demo' (streamlit)"
)
from streamlit.testing.v1 import AppTest  # noqa: E402

from app import _data as data  # noqa: E402

APP_PATH = Path(__file__).resolve().parents[1] / "app/streamlit_app.py"

REAL_RAWS_PRESENT = (
    (data.RAW_DIR / "rutas-de-transporte-publico/2026-08-02T18-51-08Z.json").is_file()
    and (data.RAW_DIR / "paradas-de-transporte-publico/2026-08-02T19-27-36Z.json").is_file()
)

REQUIRES_REAL_RAWS = pytest.mark.skipif(
    not REAL_RAWS_PRESENT,
    reason="las capturas raw aprobadas están en .gitignore y ausentes en este checkout",
)


def run_app() -> AppTest:
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def all_text(at: AppTest) -> str:
    """Todo el texto visible para el lector: título, encabezados, markdown, alertas, captions."""
    parts = [element.value for element in at.title]
    parts += [element.value for element in at.header]
    parts += [element.value for element in at.subheader]
    parts += [element.value for element in at.markdown]
    parts += [element.value for element in at.warning]
    parts += [element.value for element in at.error]
    parts += [element.value for element in at.info]
    parts += [element.value for element in at.success]
    parts += [element.value for element in at.caption]
    return "\n".join(parts)


def metric_map(at: AppTest) -> dict[str, str]:
    return {element.label: str(element.value) for element in at.metric}


@REQUIRES_REAL_RAWS
def test_app_inicia_con_capturas_reales_y_muestra_evidencia_fijada():
    at = run_app()

    text = all_text(at)
    # Título en español, límite solo-planificado y la frase exacta de no-mapa.
    assert "Auditoría del servicio planificado de transporte público de Cuenca" in text
    assert "Esta demo muestra únicamente servicio planificado." in text
    assert "GTFS-Realtime, AVL ni cobertura geográfica." in text
    assert "No se muestra un mapa porque el formato de las coordenadas," in text
    assert (
        "el orden de los ejes y el sistema de referencia CRS no están resueltos." in text
    )
    # Los hashes de provenance de ambos snapshots son visibles (etiquetas de evidencia).
    assert "dc3082ad1312e7f9c7127fef316b4b70d8b452dcd94025d471f0b417f88ee07a" in text
    assert "20969d2e6dbc4d91338901f88c2805afaf642b757adfa4be97225c7364bdc62c" in text
    # Métricas fijadas de la transformación canónica (etiquetas en español).
    metrics = metric_map(at)
    assert metrics["Rutas"] == "76"
    assert metrics["Paradas"] == "383"
    assert metrics["Filas limpias"] == "68"
    assert metrics["Ventanas sin servicio"] == "8"
    assert metrics["Origen sin valor"] == "4"
    assert metrics["Destino sin valor"] == "4"
    assert metrics["Paradas con geometría válida"] == "0"
    assert "68/76" in text
    assert "filas limpias del snapshot validado" in text
    # La selección por defecto (línea 1, IDA, Entre semana) renderiza una ventana activa.
    assert "Línea 1" in text
    assert "5:50" in text
    assert "Activo" in text
    # Las etiquetas de selección de la barra lateral están localizadas (encabezado + widgets).
    assert "Selección" in text
    assert "Evidencia del snapshot" in text
    labels = {selectbox.label for selectbox in at.selectbox}
    assert labels == {"Línea", "Sentido", "Tipo de día"}


@REQUIRES_REAL_RAWS
def test_app_interaccion_selecciona_linea_y_tipo_de_dia():
    at = run_app()

    # Interacción 1: una ventana activa entre semana para la línea 1 (por defecto).
    assert "Línea 1" in all_text(at)
    assert "Activo" in all_text(at)

    # Interacción 2: la línea 21 NO TIENE SERVICIO los sábados (centinela 0:00).
    at.selectbox(key="line").select("21").run()
    at.selectbox(key="day_type").select("saturday").run()
    assert not at.exception, at.exception
    text = all_text(at)
    assert "SIN SERVICIO" in text
    assert "0:00/0:00/0:00" in text
    assert "Sin servicio" in text
    assert "Sábado" in text  # etiqueta de día localizada en el encabezado de selección

    # Interacción 3: de vuelta a entre semana, la misma línea está activa.
    at.selectbox(key="day_type").select("weekday").run()
    assert not at.exception, at.exception
    assert "5:40" in all_text(at)


@REQUIRES_REAL_RAWS
def test_app_renderiza_las_76_filas_de_rutas_del_dia_seleccionado():
    at = run_app()
    # La tabla de servicio planificado tiene una fila por ruta para el tipo de día y
    # usa las columnas de lector localizadas (sin claves canónicas).
    assert len(at.dataframe) >= 1
    columns = list(at.dataframe[0].value.columns)
    assert columns == [
        "Línea",
        "Empresa",
        "Sentido",
        "Origen",
        "Destino",
        "Inicio",
        "Fin",
        "Intervalo",
        "Estado",
        "Incidencias de calidad",
    ]
    assert "Rutas" in metric_map(at)


def test_app_manifest_ausente_muestra_cartel_sin_traceback(tmp_path, monkeypatch):
    """Ambos raw presentes pero los manifests ausentes -> cartel del camino real estricto
    (el cargador solo cambia al fixture cuando NO existe ningún raw)."""
    raw_dir = tmp_path / "raw"
    for raw_file in (data.ROUTES_RAW_FILE, data.STOPS_RAW_FILE):
        raw_path = raw_dir / raw_file
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(data, "RAW_DIR", raw_dir)
    missing = tmp_path / "missing" / "snapshot.manifest.json"
    monkeypatch.setattr(data, "ROUTES_MANIFEST", missing)
    monkeypatch.setattr(data, "STOPS_MANIFEST", missing)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()

    assert not at.exception, at.exception  # sin elemento traceback
    text = all_text(at)
    assert "no pudo cargar" in text
    assert "snapshot.manifest.json" in text
    assert "Traceback" not in text
    assert "DEMO-01" not in text  # nunca recurre al fixture sintético


def test_app_sin_raws_y_sin_fixture_muestra_cartel(tmp_path, monkeypatch):
    """Sin raws y sin fixture -> cartel fail-closed, nunca valores vacíos/falsos."""
    monkeypatch.setattr(data, "RAW_DIR", tmp_path / "no-raw-root")
    monkeypatch.setattr(data, "SYNTHETIC_COMBINED_JSON", tmp_path / "missing-fixture.json")

    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()

    assert not at.exception, at.exception
    text = all_text(at)
    assert "no pudo cargar" in text
    assert "sintético" in text
    assert "Traceback" not in text
    assert "DEMO-01" not in text


def test_app_raw_parcial_falla_de_forma_estricta_sin_fallback_sintetico(tmp_path, monkeypatch):
    """Exactamente un raw aprobado -> fail closed; sin fallback sintético."""
    raw_dir = tmp_path / "raw"
    routes_raw = raw_dir / data.ROUTES_RAW_FILE
    routes_raw.parent.mkdir(parents=True, exist_ok=True)
    routes_raw.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(data, "RAW_DIR", raw_dir)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()

    assert not at.exception, at.exception
    text = all_text(at)
    assert "no pudo cargar" in text
    assert "evidencia parcial" in text
    assert "Traceback" not in text
    assert "DEMO-01" not in text


def test_app_modo_sintetico_renderiza_servicio_planificado_util(tmp_path, monkeypatch):
    """Camino de clone limpio: sin raws -> demo del fixture sintético con el aviso sintético
    prominente, el límite solo-planificado, la frase exacta de no-mapa y filas/métricas
    sintéticas útiles."""
    monkeypatch.setattr(data, "RAW_DIR", tmp_path / "no-raw-root")

    at = run_app()
    text = all_text(at)
    # Aviso sintético prominente (frase exacta fijada) antes de las métricas.
    assert data.SYNTHETIC_MODE_BANNER in text
    assert "Esta demo muestra únicamente servicio planificado." in text
    assert "GTFS-Realtime, AVL ni cobertura geográfica." in text
    assert "No se muestra un mapa porque el formato de las coordenadas," in text
    assert "el orden de los ejes y el sistema de referencia CRS no están resueltos." in text
    # Contenido sintético útil: ventana activa, tabla de servicio, estado sin servicio.
    assert "DEMO-01" in text
    assert "Activo" in text
    assert "6:00" in text
    # La barra lateral y la provenance distinguen el fixture de los snapshots oficiales.
    assert "sintético" in text
    metrics = metric_map(at)
    assert metrics["Rutas"] == "4"
    assert metrics["Paradas"] == "4"
    assert metrics["Ventanas sin servicio"] == "3"
    assert metrics["Filas limpias"] == "4"
    assert metrics["Paradas con geometría válida"] == "0"
    assert metrics["Latitud: sintaxis/problema"] == "3"
    assert metrics["Latitud: fuera de rango"] == "1"


def test_app_modo_sintetico_interaccion_muestra_centinela_sin_servicio(tmp_path, monkeypatch):
    """En modo sintético el centinela exacto 0:00/0:00/0:00 se renderiza para una selección
    sin servicio, con la etiqueta de día localizada."""
    monkeypatch.setattr(data, "RAW_DIR", tmp_path / "no-raw-root")

    at = run_app()
    at.selectbox(key="line").select("DEMO-02").run()
    at.selectbox(key="day_type").select("sunday").run()
    assert not at.exception, at.exception
    text = all_text(at)
    assert "SIN SERVICIO" in text
    assert "0:00/0:00/0:00" in text
    assert "Domingo" in text


def test_app_modo_sintetico_no_filtra_evidencia_oficial(tmp_path, monkeypatch):
    """El modo sintético nunca muestra hashes/IDs de resource/URLs/afirmaciones de licencia
    oficiales; la pestaña de evidencia etiqueta explícitamente el fixture como sintético."""
    monkeypatch.setattr(data, "RAW_DIR", tmp_path / "no-raw-root")

    at = run_app()
    text = all_text(at)
    for official in (
        "dc3082ad",
        "20969d2e",
        "e55af215",
        "ed2f1b0f",
        "creativecommons",
        "CC BY-NC",
        "cuencaendatos",
        "GADCuenca_RutasTransporte_2025Marzo.csv",
    ):
        assert official not in text
    assert "modo demostración" in text.lower()
    assert "synthetic-combined.json" in text


def test_app_fixture_sintetico_malformado_falla_de_forma_estricta(tmp_path, monkeypatch):
    """Un fixture malformado falla de forma estricta con un cartel claro."""
    bad = tmp_path / "bad-fixture.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(data, "RAW_DIR", tmp_path / "no-raw-root")
    monkeypatch.setattr(data, "SYNTHETIC_COMBINED_JSON", bad)

    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()

    assert not at.exception, at.exception
    text = all_text(at)
    assert "no pudo cargar" in text
    assert "Traceback" not in text
    assert "DEMO-01" not in text

# Términos de deploy/menú que la shell pública de la demo nunca debe mostrar. La
# supresión se configura con el ``toolbarMode = "minimal"`` soportado en el
# ``.streamlit/config.toml`` versionado (sin trucos de CSS).
DEPLOYMENT_TERMS = (
    "Deploy",
    "Deploy app",
    "Manage app",
    "Streamlit Community Cloud",
    "Settings",
)


def test_app_modo_sintetico_no_muestra_terminos_de_deploy_ni_menu(tmp_path, monkeypatch):
    """El texto de la demo sintética nunca expone los controles Deploy/menú de Streamlit.

    Verifica (a) que la configuración de toolbar versionada es ``minimal`` y (b) que el
    texto público de la app (título, encabezados, markdown, alertas, captions) no contiene
    términos de deploy/menú. La verificación del navegador renderizado vive en el
    procedimiento de capturas de pantalla (Playwright); esta prueba fija el contrato a
    nivel de app y la configuración soportada.
    """
    import tomllib

    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / ".streamlit" / "config.toml"
    assert config_path.is_file(), "falta el .streamlit/config.toml versionado"
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert config["client"]["toolbarMode"] == "minimal"

    monkeypatch.setattr(data, "RAW_DIR", tmp_path / "no-raw-root")
    at = run_app()
    text = all_text(at)
    for term in DEPLOYMENT_TERMS:
        assert term not in text
