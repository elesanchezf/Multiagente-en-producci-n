# 0003. Agente de bucle con tope y herramientas de solo lectura

## Contexto
Un agente que alterna entre modelo y herramientas puede no terminar nunca o consumir recursos sin control.

## Decisión
Un solo agente con un bucle de máximo `AGENT_MAX_STEPS` vueltas (3 por omisión) y dos herramientas de solo lectura. Al llegar al tope responde con el mensaje fijo `No pude completar la respuesta. Intenta con una pregunta más concreta.` El protocolo es un único objeto JSON por turno.

## Consecuencias
- El costo y el tiempo por pregunta tienen un máximo conocido.
- Las herramientas no pueden modificar datos de personal.
- Preguntas que requieran más de tres vueltas fallarán con el mensaje fijo.
- Las respuestas del modelo con formato inválido deben tratarse como error controlado.
