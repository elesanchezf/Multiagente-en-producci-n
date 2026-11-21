# Plan del reto de multiagentes en producción

## Alcance acordado

Se reutiliza M4 sesión 4. No se implementará MCP. Destino autorizado:
https://github.com/elesanchezf/Multiagente-en-producci-n.
El usuario indicó que no existe repositorio base de entrega; se preparará un PR
interno hacia main. No se afirmará que es un PR a un repositorio del profesor.

## Diagnóstico inicial

El producto contiene un único Agent con herramientas de consulta. Existen API,
autenticación, métricas, integración opcional LangSmith, cliente Cloudflare,
Dockerfile, CI y pruebas. Su existencia no demuestra operación real ni cumplimiento
completo de la rúbrica. El Dockerfile usa un tag mutable y dependencias no fijadas.
render.yaml todavía nombra el servicio del curso: debe separarse antes de desplegar.

Actualización: se integró Coordinator en /ask, con agente de directorio y revisor
de contexto independiente. Diseño: multiagent-architecture.md. Verificaciones:
141 pruebas, siete E2E, cobertura 96,96 % y Pylint 10/10; evidencia local simulada.

## Trabajo por etapas

1. Conservar base y ejecutar pruebas con evidencia de resultados.
2. Diseñar coordinación, agente de directorio y agente revisor con contratos claros,
   pasos limitados, trazas por agente y revisión sustentada en resultados de herramientas.
3. Probar controles de entrada/salida, detección de información sensible, auditoría
   y aislamiento entre solicitudes concurrentes.
4. Confirmar Cloudflare y LangSmith con secretos configurados fuera de la conversación.
5. Medir baseline y optimización sobre el mismo conjunto de preguntas con modelo real.
6. Construir y escanear imagen linux/amd64; fijar versiones y registrar digest.
7. Validar CI, desplegar servicio independiente y recoger capturas de funcionamiento.
8. Preparar README, análisis, PR y guion de video de 3–5 minutos.

## Evidencia y honestidad de resultados

Consultar evidence/README.md. Las cifras de la sesión 4 son antecedentes, no
resultados del reto. LangSmith real, costos reales, concurrencia y seguridad siguen
pendientes hasta tener evidencia. Consultado el catálogo oficial de Python:
https://hub.docker.com/_/python/tags el 19 de noviembre de 2026.
La consulta de tags no sustituye un escaneo actualizado de vulnerabilidades.
