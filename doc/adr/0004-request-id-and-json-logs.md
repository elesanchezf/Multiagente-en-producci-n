# 0004. Id por petición y log JSON sin contenido de usuario

## Contexto
Para responder qué pasó con una petición se necesita un identificador común a la respuesta, al log y a las trazas. El texto de preguntas y respuestas puede contener datos de personal y no debe quedar en registros.

## Decisión
Un middleware en `main.py` toma `X-Request-ID` del cliente o genera un UUID, lo guarda en un `ContextVar` y lo devuelve en el encabezado de toda respuesta y como `request_id` en `POST /ask`. El módulo `observability.py` emite una línea JSON por evento (`request`, `agent_run`, `audit`, `error`) en la salida estándar, con `ts` tomado de un reloj inyectado. Los eventos solo llevan longitudes, conteos y nombres; nunca texto de pregunta o respuesta. Los errores registran solo el tipo de excepción y responden `500` con `{"detail": "internal error", "request_id": ...}`.

## Consecuencias
- Cualquier petición se rastrea con un solo id, que la página web muestra a la persona usuaria.
- Un `X-Request-ID` enviado por el cliente es entrada no confiable: debe limitarse en largo y caracteres para evitar inyección en el log.
- Las pruebas son deterministas porque el reloj se inyecta.
- Los argumentos de herramientas en `audit` (por ejemplo un id de empleado) siguen siendo datos del directorio; el log requiere control de acceso y retención definida.
