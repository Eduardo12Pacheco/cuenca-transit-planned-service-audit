"""Demo local sin conexión de Streamlit para la auditoría del servicio
planificado de Cuenca.

La demo es de solo lectura y está respaldada por snapshots: renderiza la
salida de la transformación canónica
(``mobility_reliability.transformation.transform_captures``) y el artefacto
existente de auditoría de coordenadas. Nunca escribe, nunca captura, nunca
toca la red y nunca vuelve a implementar parsing.

Organización del paquete
------------------------
- ``app._data`` — constantes de rutas y cargadores de solo lectura (la
  validación estricta permanece en ``mobility_reliability``).
- ``app._views`` — modelos de vista puros y deterministas (sin imports de
  Streamlit).
- ``app.streamlit_app`` — el punto de entrada de Streamlit (``streamlit run app/streamlit_app.py``).
"""
