# Resultado de colaboración multiagente

Fecha: 19 de noviembre de 2026. Entorno: Windows, Python 3.12.16, dependencias
registradas en requirements.lock.txt. Proveedor: fake. Datos: ejemplos del curso.

## Resultado observado

- `python -m pytest tests --cov=app --cov-fail-under=80`: 141 aprobadas,
  cobertura total 96,96 %, código 0. Módulo multiagent: cobertura 100 %.
- `python -m pylint app tests --max-line-length=88`: 10.00/10, código 0.
- `python scripts/capture-local.py`: código 0; siete E2E aprobadas en Chromium.
  Se observa una advertencia de deprecación del plugin de fixtures para pytest 10;
  no impide esta ejecución con pytest 9.2.0.

La ejecución capturada usa request_id `9a750e8d-2e13-4b3a-83e1-8da83144fba8`.
El log y la respuesta muestran coordinator, directory y reviewer, dos llamadas
de consulta y una de revisión. La UI presenta datos del registro EMP-0003.
La clave de prueba se retiró del campo antes de capturar la pantalla.

## Casos comprobados

Contexto independiente del revisor; rechazo de dictamen negativo o inválido;
propagación de fallo del proveedor; suma del costo de revisión; límite de pasos;
rechazo de respuestas sin evidencia; exclusión de afirmaciones inventadas incluso
ante aprobación equivocada; jerarquía de trazas sin conexión externa; aislamiento
en 20 ejecuciones de dos empleados con cuatro hilos; respuesta de API; navegador.

El coordinador es determinista; los dos agentes usan contextos diferentes del mismo
modelo seleccionado. La revisión no modifica datos y no tiene herramientas.

## Incidencias resueltas

La primera pasada de Pylint señaló tres líneas largas y un doble de prueba con un
solo método. Se ajustó formato y se justificó la excepción localizada del doble.
Las primeras E2E no conectaron al servidor iniciado desde otra ejecución.
El ejecutor capture-local.py arranca servidor y pruebas juntos, comprueba health
y termina únicamente su propio proceso; las siete pruebas pasan con ese ejecutor.

## Límites pendientes

FakeModel aprueba por regla; estas pruebas no demuestran calidad semántica de un
revisor real. Los tokens y costos de esta captura son simulados. La prueba de hilos
no acredita carga HTTP sostenida. Falta Cloudflare, LangSmith real, PII, despliegue
y evaluación de ahorro sobre preguntas reales del benchmark.

Se consultó https://hub.docker.com/_/python/tags y se intentó escanear
`registry://docker.io/library/python:3.12-slim` para linux/amd64 con Scout.
Scout terminó con código 1 solicitando login; ver python-base-scout.txt.
No existe escaneo aprobado actual ni de la base ni de la imagen final del reto.
