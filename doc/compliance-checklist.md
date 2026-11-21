# Lista de compliance de producción

Cada regla indica dónde está en el código y cómo se comprueba. Las reglas de arranque las aplica `check_production` (`app/compliance.py`) solo con `ENVIRONMENT=production`; `create_app` y `validate_environment` en `app/main.py` la ejecutan y lanzan `ConfigError` si hay incumplimientos, sin incluir valores. Las claves y los datos de ejemplo son ficticios. Véase la [arquitectura](architecture.md) y el [ADR 0011](adr/0011-compliance-as-code-fail-closed.md).

| Regla | Dónde está en el código | Cómo se comprueba |
| --- | --- | --- |
| `MODEL_PROVIDER` no puede ser `fake` en producción | `check_production` en `app/compliance.py` | `tests/test_compliance.py` y el escenario «Production refuses to start with the fake model» de `tests/features/security.feature` |
| `API_KEYS` no puede estar vacía y cada clave debe tener al menos 16 caracteres (`MIN_KEY_LENGTH`) | `check_production` en `app/compliance.py`; `MIN_KEY_LENGTH` y `parse_api_keys` en `app/auth.py` | `tests/test_compliance.py` (una regla por vez y combinadas) y `tests/test_auth.py` |
| Con trazas encendidas, `HIDE_INPUTS` y `HIDE_OUTPUTS` deben valer `true` | `check_production` en `app/compliance.py`; ocultamiento en `app/tracing.py` | `tests/test_compliance.py` y `tests/test_tracing.py` |
| `POST /ask` y `GET /metrics` exigen `X-API-Key`; sin clave o con clave inválida responden `401`; la comparación es en tiempo constante | `identify_client` en `app/auth.py` (`hmac.compare_digest`); `_make_gate` en `app/main.py` | `tests/test_auth.py` y los escenarios de rechazo de clave de `tests/features/security.feature` |
| Una clave nunca se escribe en el log, en la traza, en un mensaje de error ni en `repr`; `API_KEYS` malformada impide arrancar con posición y largo, nunca el valor | `_malformed` y `parse_api_keys` en `app/auth.py`; `api_keys` con `repr=False` en `app/config.py` | `tests/test_security_config.py`, `tests/test_security_tracing.py` y los escenarios de log y de lista malformada de `tests/features/security.feature` |
| Más de `RATE_LIMIT_PER_MINUTE` peticiones por cliente autenticado en 60 segundos responden `429` con `Retry-After` (mínimo 1); el reloj se inyecta | `RateLimiter.check` en `app/ratelimit.py`; `_make_gate` en `app/main.py`; `rate_limit_per_minute` en `app/config.py` | `tests/test_ratelimit.py`, `tests/test_security_config.py` y el escenario de límite de `tests/features/security.feature` |
| El log incluye `client` y nunca el texto de preguntas ni respuestas; la auditoría y la traza llevan el cliente | `client_var` y `JsonLogger.emit` en `app/observability.py`; metadatos en `app/tracing.py` | `tests/test_security_tracing.py` y el escenario «The client name is logged and the key never is» de `tests/features/security.feature` |
| La página guarda la clave solo en `sessionStorage`, en un campo de tipo contraseña, y pinta texto con `textContent` | `app/static/index.html` | `tests/test_static_page.py` |
| El contenedor no corre como root, deja fuera `.env`, `tests/` y `e2e/`, y los secretos de Render usan `sync: false` | `Dockerfile`, `.dockerignore` y `render.yaml` | `tests/test_delivery_files.py` |

## Limitaciones aceptadas

- Los intentos con clave inválida no tienen límite por origen: solo el cliente autenticado tiene límite de peticiones. Esta decisión la aprobó la persona responsable del plan. La mitigación es la exigencia de claves de 16 caracteres o más y la comparación en tiempo constante. Si se requiere limitar intentos fallidos por origen, debe decidirse en un nuevo ADR. Véase la sección «Limitación aceptada: intentos con clave inválida» de [architecture.md](architecture.md) y el [ADR 0010](adr/0010-api-key-per-client-and-rate-limit.md).
- El límite de peticiones es por proceso: el contador vive en la memoria de cada proceso. Con varias copias el límite efectivo se multiplica y se reinicia con el proceso; si se escala, debe pasar a un almacén compartido mediante un nuevo ADR (ADR 0010).

## Verificaciones pendientes antes de publicar

- [Verificación de la imagen base y vulnerabilidades](image-vulnerabilities.md): estado del 21-nov-2026: 0 críticas y 3 altas de OpenSSL sin corrección en la imagen final, riesgo aceptado temporalmente hasta el 27-nov-2026 para la demo académica (ver `openssl-aplicabilidad.md`); ver también [aplicabilidad de OpenSSL](openssl-aplicabilidad.md).
- [Arquitectura](architecture.md): contiene las decisiones y los puntos «Pendiente de decisión humana» (acceso y retención de logs, salida de datos con `gateway`, nombre del repositorio).
