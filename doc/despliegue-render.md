# Despliegue en Render y mínimo privilegio (preparado; no ejecutado)

Servicio nuevo y separado: **`multiagente-reto`** (`render.yaml`). No modifica el servicio `hr-assistant`. Nada de lo siguiente se ha ejecutado: el despliegue y la carga de secretos requieren la decisión y las credenciales de la persona responsable.

## Variantes que reproduce el blueprint
`MODEL_SMALL` = Gemma 4 26B (`@cf/google/gemma-4-26b-a4b-it`), `MODEL_LARGE` = Llama 3.3 70B fp8 fast, `ROUTING=true`, `HISTORY_WINDOW=6`, `AGENT_MAX_STEPS=3`, `MODEL_MAX_TOKENS=300`, `MODEL_TEMPERATURE=0`, `CACHE_TTL_SECONDS=0` y `MODEL_EXTRA_PARAMS` con `enable_thinking=false` y `response_format=json_object` solo para Gemma. Es la variante optimized de `evidence/resultado-comparacion-E06.md`. Una prueba (`tests/test_delivery_files.py`) verifica estos valores y que coincidan con `scripts/run-comparison.ps1`.
Con `ENVIRONMENT=production` el servicio no arranca si falta `API_KEYS`, si una clave tiene menos de 16 caracteres, si el proveedor es `fake` o si las trazas están encendidas sin ocultar entradas y salidas.

## Secretos que se cargan en el panel de Render (nunca en el repositorio)
| Variable | Contenido | Privilegio mínimo recomendado |
| --- | --- | --- |
| `API_KEYS` | `cliente:clave` por cliente | Una clave por cliente, 16 caracteres o más, aleatoria; rotar al terminar la revisión |
| `CF_ACCOUNT_ID`, `CF_GATEWAY_ID` | Identificadores de cuenta y gateway | Son datos de cuenta, no se versionan |
| `CF_API_TOKEN` | Token de Cloudflare | Token de API restringido a la cuenta y solo al permiso de Workers AI; sin permisos de edición de DNS, Workers ni otros servicios. Confirmar el nombre exacto del permiso en el panel |
| `CF_AIG_TOKEN` | Token de autenticación del AI Gateway | Solo el permiso de ejecutar peticiones por el gateway; necesario solo si el gateway tiene autenticación activada |
| `LANGSMITH_API_KEY` | Clave de LangSmith | Clave de servicio limitada a escritura de trazas en el espacio de trabajo del proyecto `multiagente-reto`; no usar una clave personal con permisos de administración |

Revisar y rotar los tres tokens tras la entrega.

## Revisión de mínimo privilegio sobre el diseño
- Herramientas del agente: solo lectura (`get_employee`, `search_by_department`); el modelo no escribe datos ni ejecuta procesos.
- Contenedor: usuario no root (UID 10001); `.dockerignore` deja fuera `.env`, `tests/` y `e2e/`.
- CI: permisos `contents: read`, sin secretos de repositorio; Render publica solo si el CI pasa (`autoDeployTrigger: checksPass`).
- Rutas protegidas (`/ask`, `/metrics`) con `X-API-Key`; `/health` y `/docs` públicas.
- **Observación sobre la cuenta de GitHub usada en esta sesión:** la sesión de `gh` tiene los alcances `gist`, `read:org`, `repo` y `workflow`. Para publicar basta con `repo` y `workflow` (el CI está en `.github/workflows`); `gist` y `read:org` no son necesarios. Conviene un token de alcance mínimo.
- **No verificado:** los permisos reales de los tokens en los paneles de Cloudflare y LangSmith y la configuración de Render; solo la persona responsable puede comprobarlos.

## Después de desplegar (comandos de verificación; sustituir los marcadores)
1. `curl https://<servicio>.onrender.com/health` debe devolver 200.
2. Abrir `https://<servicio>.onrender.com/docs` (Swagger) y capturar la pantalla.
3. `curl -X POST https://<servicio>.onrender.com/ask -H "X-API-Key: <clave>" -H "Content-Type: application/json" -d '{"question":"¿Quién es el empleado EMP-0003?"}'` debe devolver 200 con `agents_used` y `review_status`.
4. Repetir la consulta varias veces en paralelo (por ejemplo con `scripts/load_local.py` adaptado a la URL) y registrar errores y latencias.
5. Abrir la traza en LangSmith con el `request_id` de la respuesta, comprobar que las entradas aparecen ocultas y capturar la pantalla.
Limitaciones del plan gratuito de Render: el servicio se suspende por inactividad (la primera petición tarda más) y las métricas son por proceso.
