# 0013. Coordinador determinista, agente de directorio y agente revisor

## Contexto
El producto de la sesión 4 tenía un único agente con herramientas. El reto exige un sistema multiagente en producción con trazabilidad por agente, control de costos y controles de seguridad.

## Decisión
`POST /ask` pasa por un coordinador determinista (sin modelo) que delega en un agente de directorio (herramientas de solo lectura, máximo `AGENT_MAX_STEPS` llamadas) y, cuando hay evidencia, en un agente revisor sin herramientas y con contexto independiente (pregunta, borrador y evidencia; nunca el historial). Solo se publica la presentación determinista de los campos permitidos de los registros consultados, no la prosa libre del modelo. Las llamadas máximas son `AGENT_MAX_STEPS + 1`, sin bucles de revisión.

## Consecuencias
- Una aprobación no permite publicar afirmaciones ajenas a la evidencia (por ejemplo, salarios).
- El revisor suma una llamada y su costo se incluye en los totales; en la comparación real representó ≈ 20 % del costo estimado de cada variante (`evidence/resultado-comparacion-E06.md`).
- Compartir proveedor no comparte conversación; no es un modelo distinto (el revisor usa el mismo modelo que la solicitud).
- Límites conocidos: el modelo puede pedir una herramienta inexistente (Q06) o no devolver JSON; el coordinador lo trata como falla de protocolo controlada. Q05 y Q06 no aprobaron en la comparación real.
- Precios y costos: un solo criterio de precios para ambas variantes; los costos son estimaciones, no facturas.
