# 0001. API sin estado

## Contexto
El asistente debe poder escalar y ser sencillo de operar. Guardar conversaciones en el servidor exigiría almacenamiento compartido y trataría datos de las conversaciones.

## Decisión
La API no guarda nada entre peticiones. El cliente conserva el historial y lo envía en `history`. Los datos se cargan en lectura y no se modifican.

## Consecuencias
- Escalar consiste en ejecutar más copias detrás de un balanceador.
- No hay datos de conversación en el servidor, lo que reduce el riesgo de privacidad.
- Cada petición debe validar el historial recibido, que no es confiable.
- No hay memoria de largo plazo ni auditoría de conversaciones; si se requieren, se decidirá en otro ADR.
