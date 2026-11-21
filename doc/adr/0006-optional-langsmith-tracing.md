# 0006. Trazas opcionales en LangSmith con privacidad por omisión

## Contexto
Las trazas ayudan a depurar corridas del agente, pero envían datos a un tercero y no deben ser requisito para operar.

## Decisión
Las funciones del agente, del modelo y de las herramientas se decoran con `@traceable` mediante un adaptador en `tracing.py`. Las trazas solo se activan con `LANGSMITH_TRACING=true` y `LANGSMITH_API_KEY` en el entorno; sin clave no se intenta ninguna conexión y el decorador no cambia el comportamiento. `HIDE_INPUTS` y `HIDE_OUTPUTS` valen `true` por omisión y suprimen entradas y salidas. El `request_id` va en los metadatos. La clave nunca se escribe en código ni en el log.

## Consecuencias
- El producto funciona igual sin LangSmith.
- Por omisión no salen textos de preguntas ni respuestas de la institución.
- Desactivar el ocultamiento requiere autorización institucional, porque podrían salir datos de personal.
- Se añade la dependencia `langsmith`, importada de forma tolerante.
