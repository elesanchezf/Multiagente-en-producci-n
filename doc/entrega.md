# Documento de entrega: sistema multiagente en producción

Estado al 21 de noviembre de 2026. Versión local, sin publicar. La versión en el formato oficial (Word y PDF) está en `doc/entrega/`. Todos los datos son ficticios.
Cada afirmación remite a una evidencia en `evidence/`; lo que no tiene evidencia figura como **pendiente**.

## 1. Qué se entrega

El HR Assistant de la sesión 4 (API FastAPI sin estado) evolucionó a un sistema de dos agentes con un coordinador determinista:

- **Coordinador:** delega, aplica las condiciones de paso y suma el consumo.
- **Agente de directorio:** consulta `get_employee` y `search_by_department` (solo lectura), hasta `AGENT_MAX_STEPS=3` pasos.
- **Agente revisor:** una llamada adicional, sin herramientas y con contexto independiente, que aprueba o rechaza el borrador según la evidencia.

Diagrama y responsabilidades: `doc/multiagent-architecture.md`. Decisión: `doc/adr/0013-coordinador-y-revisor.md`.
Base de comparación: commit `6083236` del repositorio `hr-assistant` (78 archivos verificados por hash, `evidence/baseline/`).

## 2. Evidencias comprobadas

| Área | Evidencia | Resultado | Límites |
| --- | --- | --- | --- |
| Pruebas | `evidence/e2e-fake-20261120.txt`; ejecución del 21-nov | 252 pruebas aprobadas (unitarias y navegador); Pylint 10,00/10 sobre `app`, `tests`, `e2e` y scripts de evaluación | Modelo simulado en las e2e |
| Multiagente | `evidence/multiagent-*.txt`, `screenshots/multiagent-local.png` | Coordinador, directorio y revisor en una misma solicitud con `request_id` común | Captura local con modelo simulado |
| Proveedor real | `evidence/smoke-real/`, `evidence/costs/` | Consulta real con el 70B (19-nov); Q09 real con Gemma aprobada; comparación real completa | Datos ficticios; trazas con entradas y salidas ocultas |
| Observabilidad | `evidence/smoke-real/resultado-gateway-20261119.md` | Mismo `request_id` en respuesta, log y trazas de LangSmith (consulta por metadatos) | Sin captura de la interfaz de LangSmith |
| Concurrencia | `evidence/load/summary.json` | Local: 300 solicitudes, 30 simultáneas, 0 errores, aislamiento 300/300 | Modelo simulado; un proceso; no es el despliegue |
| Seguridad | `evidence/privacy-tests.txt`, `doc/compliance-checklist.md` | Autenticación por cliente, límite de peticiones, detección de datos sensibles en ambos sentidos, auditoría sin texto de preguntas | Revisión de privilegios pendiente |
| Contenedor | `evidence/docker/20261121/` | Build linux/amd64, usuario no root (UID 10001), `/health` 200, `/docs` 200, `/ask` 401 sin clave y 200 con clave, clave y pregunta ausentes del log | Imagen local sin digest de registro; humo con modelo simulado |
| Vulnerabilidades | `evidence/docker/20261121/`, `doc/image-vulnerabilities.md`, `doc/openssl-aplicabilidad.md` | 0 críticas y **3 altas** (OpenSSL, sin corrección en Debian) en la imagen final | Riesgo **no aceptado**; decisión pendiente |

## 3. E06: costos, calidad y latencia (comparación real de 12 preguntas)

Fuente: `evidence/resultado-comparacion-E06.md` y `evidence/costs/consolidado-20261121-004715-real+20261121-010610-real/`.

| Métrica | baseline (70B) | optimized (Gemma + enrutamiento) |
| --- | --- | --- |
| Aprobadas por criterio | 9/12 | 10/12 |
| Fallas de protocolo | 2 (Q06, Q12) | 1 (Q06) |
| Costo estimado registrado (USD, con revisor) | 0,003643 | **0,001374** |
| Latencia media / máxima (ms) | 1 804 / 4 324 | 3 802 / 8 135 |

- **Menor costo registrado:** optimized (≈ 62 % menos con el precio de catálogo de la entrada de Gemma, 0,05 USD por millón; ≈ 54 % menos con 0,10).
- **Aumento de latencia:** la media de optimized es aproximadamente el doble.
- **Preguntas fallidas pendientes de resolver:**
  - **Q05** (listar empleados de Tecnología): no aprobó en ambas variantes; el revisor rechazó la respuesta.
  - **Q06** (comparar dos empleados): no aprobó en ambas; el 70B pidió una herramienta inexistente (falla de protocolo).
  - Q01 no aprobó en baseline. En Q12 el criterio de seguridad se cumplió en ambas; el baseline tuvo además una falla de protocolo, informada aparte.
- **Limitaciones:**
  - Costos **estimados** con `data/model_prices.json`; no son una factura ni un ahorro garantizado. Gemma tiene dos precios de entrada contradictorios entre fuentes (0,05 y 0,10).
  - optimized **combina dos ejecuciones** y el tiempo de espera del gateway cambió de 30 a 60 s entre ellas.
  - Un intento de optimized/Q05 falló (502 tras 30 s) con consumo desconocido; se conserva aparte y no entra en los totales.
  - Una ejecución por variante, 12 preguntas, temperatura 0: sin significancia estadística.
  - Criterios de calidad sin cambios.

## 4. Pendientes que bloquean la entrega

1. **Despliegue en Render:** el blueprint del servicio separado `multiagente-reto` está listo (`render.yaml`, `doc/despliegue-render.md`); falta desplegarlo, Swagger público, consulta autenticada con el modelo real y concurrencia sobre la URL pública.
2. **Capturas faltantes:** Swagger, Render (servicio y health), interfaz de LangSmith con una traza, y los resultados de la comparación. Solo existe la captura local con modelo simulado.
3. **Decisión sobre OpenSSL:** tres altas sin corrección; requiere decisión de la persona responsable y repetir el escaneo sobre el digest de registro.
4. **Revisión de privilegios** (mínimo privilegio de tokens y servicio).
5. **Repositorio y PR:** la rama `reto/produccion` no tiene commits; `main` del repositorio de entrega está vacío (ver `doc/publicacion.md`). CI sin ejecutar en GitHub.
6. **Video** de 3 a 5 minutos (guion en `doc/guion-video.md`).
7. **Correcciones de calidad** de Q05 y Q06, si se decide abordarlas; no son requisito de la rúbrica.

## 5. Reproducibilidad

- Pruebas: `python -m pytest tests e2e` (las e2e inician el servidor con modelo simulado).
- Estilo: `pylint app tests e2e scripts/eval_costs.py scripts/real_smoke.py scripts/consolidate_comparison.py --max-line-length=88`.
- Imagen: `docker build --platform linux/amd64 -t multiagente-reto:final .` (base fijada por digest).
- Evaluación real: `scripts/run-q09.ps1` y `scripts/run-comparison.ps1` (exigen `-ConfirmRealCalls`; secretos solo en el entorno de la ventana).
- Consolidación sin red: `python scripts/consolidate_comparison.py <primera> <continuación>`.
