# HR Assistant

## Reto de multiagentes en producción

Este reto es «Sistema multi-agente en producción» (plan y rúbrica M4); no es el reto de Servidor MCP. Esta copia evoluciona la base de M4 (sesión 4) con un coordinador, un agente de directorio y un agente revisor. Diseño: `doc/multiagent-architecture.md`; documento de entrega: `doc/entrega.md` y `doc/entrega/` (Word y PDF); estado de evidencias: `evidence/README.md`. Los documentos heredados describen la sesión 4.

### Requisitos previos
- Python 3.12, Git y [uv](https://docs.astral.sh/uv/) (o pip). Docker, solo para la imagen. Cuenta de Cloudflare con AI Gateway y, opcionalmente, LangSmith, solo para el proveedor real.

### Clonar e instalar (Windows, PowerShell)
```powershell
git clone https://github.com/elesanchezf/Multiagente-en-producci-n.git
cd Multiagente-en-producci-n
git checkout reto/produccion
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv venv --python 3.12
uv pip sync --python .venv/Scripts/python.exe requirements.lock.txt
```
Las versiones de `requirements.lock.txt` corresponden al entorno Windows verificado; la imagen de contenedor las instala en Linux.

### Variables de entorno
Copie `.env.example` y complete los valores (no suba `.env`). Con modelo simulado basta `MODEL_PROVIDER=fake` y `API_KEYS=cliente:<clave de 16 o más caracteres>`. Con proveedor real: `MODEL_PROVIDER=gateway`, `CF_ACCOUNT_ID`, `CF_API_TOKEN` y, si el gateway lo exige, `CF_AIG_TOKEN`. Las tablas de variables están más abajo. Los secretos se escriben solo en el entorno o en el panel de Render.

### Comandos de ejecución
```powershell
$env:MODEL_PROVIDER = 'fake'; $env:API_KEYS = 'cliente:clave-ficticia-0123456789'
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000      # API; Swagger en /docs, salud en /health
powershell -ExecutionPolicy Bypass -File scripts/verify-local.ps1  # pruebas y Pylint (guarda evidencia en evidence/runs/)
.venv/Scripts/python.exe -m pytest tests e2e                       # unitarias y de navegador (las e2e inician su servidor simulado)
docker build --platform linux/amd64 -t multiagente-reto:final .    # imagen de contenedor
```
La evaluación real de costos (`scripts/run-q09.ps1`, `scripts/run-comparison.ps1`) exige `-ConfirmRealCalls` y credenciales en la ventana de PowerShell. El despliegue en Render se describe en `doc/despliegue-render.md`.

Para las capturas locales, con datos ficticios y modelo simulado:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.playwright'
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe scripts/capture-local.py
```

El ejecutor ocupa temporalmente el puerto 8014, guarda la captura y cierra su servidor. No carga `.env` ni usa credenciales reales.

Asistente de Recursos Humanos con API web sin estado, una página de consulta y
observabilidad por petición: identificador de petición, log JSON, métricas por
proceso y trazas opcionales en LangSmith. Todos los datos de ejemplo son ficticios.

## Cómo correrlo

Desde la raíz del repositorio (equivale a la sección anterior, con pip):

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
desde la raíz del repositorio:

```
pytest tests --cov=app
```

La cobertura mínima es de 80 %. No ejecute `pytest` sin argumentos: también
recolectaría `e2e/`, que necesita el producto en marcha.

Punta a punta (`e2e/`, Playwright): requieren `pytest-playwright` (incluido en
`requirements.txt`) y navegadores instalados. Sin `--base-url`, `e2e/conftest.py`
inicia el producto con el modelo simulado y una clave ficticia en un puerto libre;
con `--base-url` (como en CI) usa el servidor indicado.

```
playwright install
pytest e2e
```

Alternativa con servidor propio (dos terminales; `E2E_API_KEY` debe coincidir con una
clave de `API_KEYS`):

```
MODEL_PROVIDER=fake uvicorn app.main:app --port 8000
pytest e2e --base-url http://127.0.0.1:8000
```

Desde la raíz de la
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
| `MODEL_SMALL` | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Modelo barato; provisional: sin modelo pequeño verificado, igual al capaz |
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

## Entrega del reto: estado de las evidencias (21-nov-2026)

Resumen honesto; el detalle, con fechas y límites, está en `evidence/README.md`,
`evidence/pendientes-entrega-20261120.md` y `doc/evaluacion-costos.md`.

| Área | Comprobado | Pendiente |
| --- | --- | --- |
| Multiagente | Coordinador, directorio y revisor; 242 pruebas, cobertura 98 %, Pylint 10/10, 7 e2e (modelo simulado) | — |
| Proveedor real | Consulta real con 70B y traza en LangSmith (19-nov); sonda Gemma 2/3; Q09 real aprobada; comparación completa | — |
| Costos | Comparación real de 12 preguntas por variante (`evidence/resultado-comparacion-E06.md`): aprobadas 9 vs 10; costo estimado 0,003643 vs 0,001374 USD; latencia media 1 804 vs 3 802 ms. Optimized combina dos ejecuciones (espera 30→60 s); Q05 y Q06 no aprobaron en ambas | Costos estimados, no factura; ahorro no garantizado; muestra pequeña |
| Concurrencia | Local: 300 solicitudes, 30 simultáneas, 0 errores | Sobre el despliegue |
| Seguridad | Privacidad, claves, aislamiento (local); Scout 21-nov: 0 críticas y 3 altas de OpenSSL sin corrección | Revisión de privilegios; decisión de riesgo sobre OpenSSL |
| Despliegue | Build amd64 y humo en contenedor local (21-nov) | Render, Swagger, consulta real en URL pública |
| Entrega | Remoto configurado | Commits, push, PR hacia `main`, CI en GitHub, capturas y video |

Los precios de Gemma (0,05 y 0,10 USD por millón de entrada) provienen de fuentes
contradictorias: el costo calculado es una estimación, no una tarifa facturada.
