# Resultado: privacidad y concurrencia local

Fecha: 19 de noviembre de 2026. Entorno: Windows, Python 3.12.16, proveedor `fake`,
datos ficticios, sin `.env` ni credenciales reales.

## Comprobado

- `pytest tests --cov=app --cov-fail-under=80`: 155 aprobadas; cobertura 97,15 %.
- `pylint app tests --max-line-length=88`: 10.00/10, código 0.
- `test_sensitive_record_does_not_reach_second_model_call` ahora usa un modelo
  contador: un registro sensible devuelve 502 tras exactamente una llamada al modelo
  y sin valor sensible en respuesta ni log.
- Prueba HTTP (`scripts/load_local.py`): 300 solicitudes, 30 simultáneas, un proceso
  uvicorn: 300 respuestas 200, 0 errores, 300/300 respuestas con el empleado correcto
  y sin datos de otros, 300/300 `X-Request-ID` reflejados; 320,1 solicitudes/s;
  latencia ms: p50 89,3; p95 96,4; p99 104,6; máx 109,6. Log del servidor sin texto de preguntas.

## Cambios de código

`tests/conftest.py` (`make_client` acepta `model` y `employee_directory`),
`tests/test_privacy.py`, y `app/main.py` (funciones auxiliares `_payload`,
`_error_details`, `_enforce_compliance`, sin cambio de comportamiento).

## Limitaciones y pendientes

- La latencia incluye un modelo simulado: no representa Cloudflare ni Render.
- Un solo proceso y máquina local; falta carga sobre el despliegue.
- Docker Scout sigue pendiente por requerir login. Imagen base actual: `python:3.12-slim`
  (tag móvil). Docker Hub lista ramas 3.14, 3.13 y 3.12 sobre Debian trixie; las
  fuentes difieren en el parche vigente. Verificar y fijar tag con parche y digest
  antes de construir. Fuente: https://hub.docker.com/_/python
- Sin LangSmith real, sin despliegue, sin push.
