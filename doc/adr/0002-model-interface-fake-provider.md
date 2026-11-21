# 0002. Modelo detrás de una interfaz, con proveedor simulado

Estado: Modificado por los ADR 0007 a 0009.

## Contexto
Se prevé cambiar de modelo en el futuro. En esta sesión no se quiere red, costo ni resultados no deterministas en las pruebas.

## Decisión
El agente depende solo de la interfaz `complete(messages)`, que se mantiene sin cambios. Existen dos proveedores, elegidos con `MODEL_PROVIDER`:
- `fake`: modelo simulado y determinista, sin red ni credenciales.
- `gateway`: modelo real mediante AI Gateway (ADR 0009).

El modelo se inyecta en `create_app()`. El enrutamiento entre modelos se describe en el ADR 0007 y el cálculo de costo en el ADR 0008.

## Consecuencias
- Cambiar de modelo no obliga a modificar el agente.
- Las pruebas son rápidas, repetibles y sin credenciales al usar `fake`.
- El comportamiento real de un modelo de lenguaje solo se observa con `gateway`.
- `gateway` exige credenciales y falla de forma cerrada: sin ellas no arranca, y los fallos del proveedor se responden de forma controlada (ADR 0009).
