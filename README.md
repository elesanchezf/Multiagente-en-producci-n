# HR Assistant

Asistente de Recursos Humanos con API web sin estado, una página de consulta y
observabilidad por petición: identificador de petición, log JSON, métricas por
proceso y trazas opcionales en LangSmith. Todos los datos de ejemplo son ficticios.

## Cómo correrlo

Desde la carpeta `product/`:

```
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

- Página web: `GET /`.
- Pregunta: `POST /ask` con `{"question": "...", "history": [...]}`. La respuesta
  incluye `request_id`.
- Salud: `GET /health`.
- Métricas de este proceso: `GET /metrics`.

## Pruebas

Unitarias y de comportamiento (no usan red ni requieren el producto corriendo),
desde `product/`:

```
pytest tests --cov=app
```

La cobertura mínima es de 80 %. No ejecute `pytest` sin argumentos: también
recolectaría `e2e/`, que necesita el producto en marcha.

Punta a punta (`e2e/`, Playwright): requieren `pytest-playwright` (incluido en
`requirements.txt`), navegadores instalados y el producto corriendo con el modelo
simulado.

```
playwright install
MODEL_PROVIDER=fake uvicorn app.main:app --port 8000
pytest e2e --base-url http://127.0.0.1:8000
```

Los dos últimos comandos se ejecutan en terminales distintas. Desde la raíz de la
fábrica, `uv run python -m verification <paso>` corre cada nivel: `unit`
(pruebas unitarias), `contract` (contrato contra el producto corriendo), `e2e`
(Playwright; arranca el producto por su cuenta), `evaluate` (costo y calidad
contra la línea base) y `qa` (estilo y pylint).

## Observabilidad

- Cada respuesta devuelve el encabezado `X-Request-ID`. Si el cliente lo envía y es
  válido (hasta 128 caracteres: letras, números, `.`, `_`, `:` y `-`) se reutiliza;
  si no, se genera un UUID.
- El log va a la salida estándar, una línea JSON por evento, con `ts` (UTC),
  `service`, `event` y `request_id`. Eventos: `request`, `agent_run`, `audit` y
  `error`. Nunca se registra el texto de la pregunta ni de la respuesta.
- `GET /metrics` es por proceso: con varias copias, cada una reporta lo suyo.
- Con `LANGSMITH_TRACING=true` y `LANGSMITH_API_KEY` en el entorno se envían trazas;
  sin la clave el producto funciona igual y no se conecta.

Advertencia: los registros `audit` contienen identificadores de empleado. Defina
retención y control de acceso a los logs antes de usar datos reales.

## Variables de entorno

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `MODEL_PROVIDER` | `fake` | Proveedor de modelo (`fake` o `gateway`) |
| `AGENT_MAX_STEPS` | `3` | Tope de vueltas del agente |
| `MAX_QUESTION_CHARS` | `2000` | Largo máximo de la pregunta |
| `EMPLOYEES_PATH` | `data/employees.json` | Archivo del directorio |
| `SERVICE_NAME` | `hr-assistant` | Campo `service` del log |
| `SLO_P95_MS` | `2000` | Meta de latencia p95 en milisegundos |
| `LANGSMITH_TRACING` | `false` | Enciende las trazas |
| `LANGSMITH_API_KEY` | (vacía) | Clave de LangSmith, solo del entorno |
| `HIDE_INPUTS` / `HIDE_OUTPUTS` | `true` | No enviar a LangSmith preguntas ni respuestas |

La clave nunca se escribe en el código ni en el log.

## Acceso y producción (sesión 4)

- `POST /ask` y `GET /metrics` exigen el encabezado `X-API-Key`. Sin clave o con una
  inválida responden `401 {"detail": "invalid or missing API key"}`. `GET /`,
  `GET /health` y `/docs` no piden clave.
- `API_KEYS` tiene la forma `cliente:clave,cliente2:clave2`. Si está mal formada el
  producto no arranca; el error da la posición y el largo de la entrada, nunca su valor.
- El nombre del cliente aparece como `client` en el log, la auditoría y los metadatos
  de la traza. La clave nunca se escribe en ellos ni en los errores.
- Más de `RATE_LIMIT_PER_MINUTE` peticiones de un cliente en un minuto responden
  `429 {"detail": "rate limit exceeded"}` con `Retry-After`. El contador es por proceso.
- Los intentos con clave inválida no tienen límite por origen; solo el cliente
  autenticado tiene límite. Use claves largas (16 caracteres o más).
- Con `ENVIRONMENT=production` el producto se niega a arrancar si `MODEL_PROVIDER` es
  `fake`, si `API_KEYS` está vacía o tiene claves de menos de 16 caracteres, o si las
  trazas están encendidas y `HIDE_INPUTS` o `HIDE_OUTPUTS` no valen `true`. Las reglas
  y su comprobación están en `doc/compliance-checklist.md`.
- La página tiene un campo de clave que se guarda solo en `sessionStorage`.

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | Con `production` se aplican las reglas de compliance |
| `API_KEYS` | (vacía) | Clientes y claves, secreto, solo del entorno |
| `RATE_LIMIT_PER_MINUTE` | `30` | Peticiones por cliente por minuto |

Con `API_KEYS` vacía en desarrollo, las rutas protegidas responden `401`: configure
al menos un cliente con una clave ficticia para probar localmente.

## Costos (sesión 3)

Con `MODEL_PROVIDER=gateway` el modelo real es Cloudflare Workers AI a través de
AI Gateway (cliente `httpx`). Con `fake` hay dos modelos simulados que se llaman
como `MODEL_SMALL` y `MODEL_LARGE` y se cobran con el precio de su nombre, por lo
que las palancas se miden sin red. Si la llamada falla, `POST /ask` responde
`502 {"detail": "model unavailable", "request_id": ...}`.

Palancas: enrutamiento por regla (`ROUTING`, `ROUTER_MAX_CHARS`), ventana de
historial (`HISTORY_WINDOW`; `0` no envía historial), tope de salida
(`MODEL_MAX_TOKENS`) y caché del gateway (`CACHE_TTL_SECONDS`; `0` la apaga).

`POST /ask` agrega `model`, `route` (`routing_disabled`, `too_long`,
`keyword:<palabra>` o `default`), `cached_calls` y `cost_usd`; `/metrics` agrega
`cost_usd` acumulado. Los precios están en `data/model_prices.json`; un modelo
sin precio impide arrancar.

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `CF_ACCOUNT_ID` | (vacía) | Cuenta de Cloudflare (obligatoria con `gateway`) |
| `CF_GATEWAY_ID` | `default` | Gateway de Cloudflare |
| `CF_API_TOKEN` | (vacía) | Token de Cloudflare, secreto, solo del entorno |
| `CF_AIG_TOKEN` | (vacía) | Token de autenticación de AI Gateway, opcional, secreto, solo del entorno |
| `MODEL_SMALL` | `@cf/meta/llama-3.1-8b-instruct-fast` | Modelo barato |
| `MODEL_LARGE` | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Modelo capaz |
| `ROUTING` | `true` | Enrutamiento por pregunta |
| `ROUTER_MAX_CHARS` | `80` | Preguntas más largas van al modelo capaz |
| `HISTORY_WINDOW` | `6` | Mensajes de historial que se mandan |
| `MODEL_MAX_TOKENS` | `300` | Tope de tokens de salida |
| `MODEL_TEMPERATURE` | `0` | Con 0 las evaluaciones son repetibles |
| `CACHE_TTL_SECONDS` | `0` | Caché del gateway (0: apagada) |
| `PRICES_PATH` | `data/model_prices.json` | Precios por modelo |

Encabezados hacia el gateway: el cliente siempre envía `Authorization: Bearer
<CF_API_TOKEN>` para Workers AI. Si `CF_AIG_TOKEN` está definida, envía además
`cf-aig-authorization: Bearer <CF_AIG_TOKEN>`; si está vacía, no envía ese
encabezado (útil solo si el gateway no exige autenticación). Ningún token se
escribe en el log ni en los errores.

Cuando el gateway devuelve un error HTTP, el log JSON del evento `error` incluye
`status_code` junto con `request_id`, sin credenciales ni preguntas. El cliente
sigue recibiendo `502 {"detail": "model unavailable", "request_id": ...}`.

`.env.example` lista todas las variables sin secretos. Con `gateway` los datos
salen a un tercero: use datos ficticios hasta contar con autorización
institucional.

## Documentación

Arquitectura y decisiones (ADR) en `doc/`.
