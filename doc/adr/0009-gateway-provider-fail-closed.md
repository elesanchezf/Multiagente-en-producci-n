# 0009. Proveedor gateway con configuración estricta y fallo controlado

## Contexto
El modelo real corre en Cloudflare Workers AI mediante AI Gateway. Implica un tercero, un token secreto, fallos de red y envío de datos de personal fuera de la institución.

## Decisión
`MODEL_PROVIDER=gateway` agrega un `GatewayModel` (con `httpx`) que llama al endpoint de chat del gateway con `Authorization: Bearer`, y cuerpo `model`, `messages`, `max_tokens` y `temperature`; lee los tokens de `usage` y, con `CACHE_TTL_SECONDS > 0`, envía `cf-aig-cache-ttl`. Faltar `CF_ACCOUNT_ID`, `CF_GATEWAY_ID` o `CF_API_TOKEN` impide arrancar. Cualquier fallo de la llamada (red, tiempo agotado, estado distinto de 2xx, cuerpo inválido) se convierte en `ModelUnavailable`, que `POST /ask` responde como `502 {"detail": "model unavailable", "request_id": ...}`. La llamada lleva tiempo máximo explícito. El token se lee solo del entorno y nunca se registra ni se devuelve; `.env.example` no lleva valores reales.

## Consecuencias
- Un error del proveedor no se confunde con un error interno (500) ni filtra detalles.
- Las pruebas usan un transporte simulado de `httpx`; no se llama a Cloudflare en pruebas.
- Con `gateway`, el contenido de las preguntas sale a un tercero: se requiere autorización institucional antes de usar datos reales de personal.
- Sigue pendiente la decisión humana sobre autenticación y control de acceso de la API.
