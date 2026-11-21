## Título del PR
feat: Sistema multiagente (coordinador, directorio y revisor) preparado para producción, con observabilidad, optimización de costos y controles de seguridad

> Este reto es «Sistema multi-agente en producción» (plan y rúbrica M4), no el reto de Servidor MCP. Se aplica el formato de componentes del PR de `M4._Formato_de_Entrega_NGC`. Versión completa en Word y PDF: `doc/entrega/`.

## Resumen de Cambios
El HR Assistant de la sesión 4, con un único agente, pasa a ser un sistema multiagente: un coordinador determinista delega en un agente de directorio (consulta de solo lectura) y en un agente revisor independiente que aprueba o rechaza el borrador contra la evidencia. Se añaden observabilidad por solicitud, enrutamiento de modelos con evaluación real de costos frente a un baseline, controles de seguridad y privacidad, un contenedor reproducible y un blueprint de Render. El despliegue en la nube sigue pendiente.

## Arquitectura del Sistema
- Diagrama: `doc/entrega/arquitectura.png` y `doc/multiagent-architecture.md`.
- Flujo: la API valida clave, límite y entrada → el coordinador delega en el agente de directorio (hasta 3 pasos, herramientas de solo lectura) → el revisor, sin herramientas y con contexto independiente, aprueba o rechaza → una presentación determinista publica solo campos permitidos → la respuesta lleva `request_id`, agentes usados y estado de revisión. El mismo `request_id` está en el log, las métricas y las trazas.
- Decisiones: coordinador determinista (predecible y auditable), revisor independiente (menos afirmaciones sin sustento), presentación determinista (no publica datos ajenos a la evidencia), enrutamiento por regla hacia un modelo pequeño (menor costo a cambio de mayor latencia). Ver ADR 0013.

## Instalación y Ejecución
Ver `README.md` (requisitos, instalación, variables de entorno y comandos). Resumen: Python 3.12 y uv; `uv pip sync requirements.lock.txt`; pruebas con `python -m pytest tests e2e`; imagen con `docker build --platform linux/amd64`. Los secretos solo en el entorno o en el panel de Render.

## Video de Demostración
**Pendiente.** Guion en `doc/guion-video.md`; no se incluye enlace hasta grabarlo.

## Evidencia y resultados
| Área | Resultado | Límites |
| --- | --- | --- |
| Pruebas | 252 aprobadas (unitarias y e2e); Pylint 10,00/10 | e2e con modelo simulado |
| Costos (12 preguntas, real) | costo estimado 0,001374 (optimized) frente a 0,003643 USD (baseline); aprobadas 10/12 frente a 9/12; latencia media 3 802 frente a 1 804 ms | Estimaciones, no factura; optimized combina dos ejecuciones (espera 30 → 60 s); Q05 y Q06 no aprobaron en ambas variantes |
| Seguridad | Autenticación, límite, validación, detección de datos sensibles, auditoría, secretos por entorno | Revisión de privilegios pendiente |
| Contenedor | amd64, usuario no root, health y Swagger en local | Sin digest de registro; 0 críticas y 3 altas de OpenSSL sin corrección (riesgo no aceptado, sin VEX) |

## Notas Adicionales
- Limitaciones: ver `doc/entrega.md` sección 3 y `doc/openssl-aplicabilidad.md`.
- Pendientes que bloquean la entrega: despliegue en Render, capturas de Swagger y Render (las dos de LangSmith son de una prueba local, no del despliegue), decisión sobre OpenSSL, CI en GitHub y video.

## Archivos en este PR
`app/` (API, coordinador y agentes), `tests/` y `e2e/`, `scripts/` (evaluación, consolidación, anonimización), `doc/` (arquitectura, ADR, costos, vulnerabilidades, despliegue, entrega), `evidence/` (con copias anonimizadas), `Dockerfile`, `render.yaml`, `.github/workflows/ci.yml`.

## Etiquetas
Share-OK: opcional; a decisión de la persona participante.
