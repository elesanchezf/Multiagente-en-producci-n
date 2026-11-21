# 0012. Contenedor y despliegue condicionado al pipeline de CI

## Contexto
El producto debe publicarse en Render solo cuando sus comprobaciones pasen, y los ingenieros deben ver cada etapa. Un fallo no debe llegar a producción ni exponer secretos.

## Decisión
La imagen se construye con `python:3.12-slim`, un usuario sin privilegios y `uvicorn` en `${PORT:-8000}`; `.dockerignore` excluye `.env`, `tests/`, `e2e/` y cachés. `.github/workflows/ci.yml` corre en cada push y pull request con cuatro trabajos encadenados por `needs`: `style`, `unit`, `e2e` y `docker`. `render.yaml` define un servicio Docker del plan gratuito con `healthCheckPath: /health` y `autoDeployTrigger: checksPass`, de modo que Render publica solo si el pipeline pasa. El servicio lleva el mismo nombre que el repositorio. Los secretos (`API_KEYS`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`) usan `sync: false` y se escriben solo en Render. `scripts/smoke.py` comprueba el servicio publicado con la clave tomada de `SMOKE_API_KEY`.

## Consecuencias
- Cada etapa es visible en la pestaña Actions y un trabajo en rojo detiene el despliegue.
- Ningún secreto está en el repositorio, la imagen ni los argumentos de comandos.
- La imagen incluye las dependencias de prueba porque hay un solo `requirements.txt`; es más pesada pero simple.
- El plan gratuito suspende el servicio y reinicia las métricas, y el nombre del servicio depende del repositorio que indique la persona.
- La publicación sigue requiriendo la aprobación de una persona antes de `scripts/publish.py`.
