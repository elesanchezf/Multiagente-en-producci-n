# 0010. Clave por cliente y límite de peticiones en el middleware

## Contexto
Hasta la sesión 3 la API no tenía autenticación, lo que impedía publicarla. Se necesita identificar al cliente, atribuirle cada evento y limitar su uso, sin guardar estado compartido (ADR 0001).

## Decisión
`API_KEYS` (`cliente:clave,...`) se analiza al arrancar. El middleware exige `X-API-Key` en `POST /ask` y `GET /metrics`, compara con `hmac.compare_digest` y responde `401` si falta o no coincide. El cliente se guarda en un `ContextVar` (`client_var`) que el log, la auditoría y la traza incluyen como `client`. Después de autenticar, `ratelimit.py` aplica una ventana deslizante de 60 segundos por cliente con el reloj inyectado y responde `429` con `Retry-After`. La clave nunca se registra ni aparece en errores ni en `repr`; una `API_KEYS` malformada impide arrancar con un mensaje que da posición y largo de la entrada.

## Consecuencias
- Cada evento es atribuible a un cliente sin exponer su clave.
- El contador vive en memoria de cada proceso: con varias copias el límite efectivo se multiplica y se reinicia con el proceso. Es aceptable con una sola instancia; si se escala, el límite debe pasar a un almacén compartido y requerirá un nuevo ADR.
- Los intentos con clave inválida NO tienen límite por origen: solo el cliente autenticado tiene límite de peticiones. La persona responsable del plan aceptó esta limitación. La mitigación son las claves de al menos 16 caracteres (exigidas por `check_production`, ADR 0011) y la comparación en tiempo constante. Limitar intentos fallidos por origen requeriría un nuevo ADR.
- Rotar una clave requiere reiniciar el servicio.
