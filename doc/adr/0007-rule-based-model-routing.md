# 0007. Enrutamiento de modelo con una regla en código

## Contexto
La mayoría de las preguntas de RH son consultas simples (un id, un departamento) que un modelo pequeño resuelve. Usar siempre el modelo grande encarece cada respuesta sin mejorarla. La especificación pide que la elección no dependa de otro modelo.

## Decisión
Un módulo `router.py` con una función pura `choose_model(question, config)` devuelve el nombre del modelo y el motivo (`route`). Elige `MODEL_LARGE` si `ROUTING=false`, si la pregunta excede `ROUTER_MAX_CHARS` o si contiene alguna de las palabras clave de la especificación (comparación sin distinguir mayúsculas); en otro caso, `MODEL_SMALL`. La elección se hace una vez por pregunta y se mantiene en todas las vueltas del bucle. La interfaz `complete(messages)` no cambia: el agente recibe un modelo ya elegido de un conjunto `nombre -> modelo`.

## Consecuencias
- La regla es determinista, barata y se prueba con pruebas unitarias sin red.
- Una pregunta compleja sin palabra clave puede ir al modelo pequeño; las palancas se aceptan solo si la evaluación no pierde calidad.
- Los motivos de enrutamiento quedan en la respuesta y en el log, útiles para auditar costos.
- Cambiar la regla no toca el agente ni el protocolo con el modelo.
