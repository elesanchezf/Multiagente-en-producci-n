# 0011. Compliance como código: negarse a arrancar en producción

## Contexto
Una configuración insegura (modelo simulado, sin claves, claves cortas o trazas que envían texto a un tercero) no debe llegar a producción por un descuido, y las reglas deben poder revisarse sin leer el código completo.

## Decisión
`compliance.py` expone una función pura que recibe la configuración y devuelve la lista de reglas incumplidas, sin valores. Con `ENVIRONMENT=production`, `create_app` la ejecuta y, si la lista no está vacía, lanza `ConfigError` que nombra cada regla. Las reglas son: `MODEL_PROVIDER` distinto de `fake`; `API_KEYS` no vacía con claves de al menos 16 caracteres; y, con trazas encendidas, `HIDE_INPUTS` y `HIDE_OUTPUTS` en `true`. La verificación vive en `create_app` y no en `load_config`, para que una configuración inyectada tampoco la eluda. `doc/compliance-checklist.md` relaciona cada regla con su ubicación en el código y su prueba.

## Consecuencias
- Falla cerrada: es preferible no arrancar a operar sin controles.
- Las reglas se prueban una por una y combinadas, y la lista se audita en una sola tabla.
- Fuera de producción no se aplican, por lo que el desarrollo y las pruebas siguen usando el modelo simulado.
- Una regla nueva exige actualizar función, pruebas y tabla; la tabla puede desfasarse si no se revisa.
