# 0008. Costo por respuesta calculado en la aplicación

## Contexto
Para saber si una palanca (enrutamiento, ventana, tope de salida, caché) abarata sin empeorar, hace falta un costo medible por respuesta, también con el modelo simulado y sin gastar cuota.

## Decisión
Un módulo `pricing.py` carga `data/model_prices.json` (USD por millón de tokens) y calcula `cost_usd = (entrada * precio_in + salida * precio_out) / 1e6` por llamada al modelo. Una llamada con `cf-aig-cache-status: HIT` se cuenta en `cached_calls` y cuesta 0. Cada `ModelResponse` informa modelo, tokens y si fue cacheada; el agente acumula `cost_usd` y `cached_calls`. Con `fake`, los dos modelos simulados se llaman como `MODEL_SMALL` y `MODEL_LARGE` y se tarifan por nombre. Un modelo sin precio impide arrancar. `POST /ask` agrega `model`, `route`, `cached_calls` y `cost_usd`; `/metrics` agrega `cost_usd` acumulado. La ventana (`HISTORY_WINDOW`) recorta solo el historial del cliente, nunca la pregunta ni los mensajes de herramientas de la corrida actual.

## Consecuencias
- Las palancas se miden sin red; `verification evaluate` compara línea base y configuración por omisión.
- Los precios cambian: el archivo debe revisarse antes de cada uso y su fecha de verificación queda a la vista.
- El costo es una estimación basada en los tokens que informa el proveedor, no una factura.
- El log registra modelo, ruta y costo, nunca texto de preguntas ni respuestas.
