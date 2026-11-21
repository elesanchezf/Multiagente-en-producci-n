# 0005. Métricas por proceso y SLO de latencia

## Contexto
La API es sin estado y se escala con más copias (ADR 0001). Se necesita medir tasa de error, latencia y tokens sin introducir almacenamiento compartido.

## Decisión
`GET /metrics` reporta solo lo observado por el proceso que atiende, con `pid`, `requests`, `error_rate`, `latency_ms` (p50, p95), `tokens` y `slo` (`p95_ms_target` desde `SLO_P95_MS`, `met` verdadero si el p95 es menor que la meta). Los contadores viven en un objeto de métricas creado en `create_app()`, no en variables globales, con un tope de muestras de latencia.

## Consecuencias
- No se agrega base de datos ni servicio externo; el estado es solo de observación y se pierde al reiniciar.
- Con varias copias cada una reporta lo suyo; la agregación queda para un recolector externo (fuera de alcance).
- El tope de muestras acota la memoria a costa de que p50 y p95 sean de una ventana reciente.
- `/metrics` no tiene autenticación en la spec; conviene restringirlo a la red interna.
