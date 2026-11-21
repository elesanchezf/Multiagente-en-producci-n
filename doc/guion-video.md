# Guion de video (3 a 5 minutos)

Reglas: solo se muestra lo comprobado; datos ficticios; sin claves ni tokens en pantalla (campo de clave vacío). Las escenas marcadas **[PENDIENTE]** no se pueden grabar hasta contar con la evidencia; no se sustituyen por material simulado ni se presentan como reales.

| Tiempo | Escena | Qué se muestra | Estado |
| --- | --- | --- | --- |
| 0:00–0:20 | Presentación | Objetivo: pasar de un agente único a un sistema multiagente en producción; todo con datos ficticios | Listo |
| 0:20–1:00 | Arquitectura | Diagrama de `doc/multiagent-architecture.md`: coordinador, directorio, revisor y presentación determinista | Listo |
| 1:00–1:40 | Funcionamiento local | Página local con modelo simulado: pregunta por EMP-0003, `request_id`, respuesta aprobada por el revisor. Indicar que es modelo simulado | Listo (captura local) |
| 1:40–2:10 | Pruebas y seguridad | 252 pruebas, Pylint 10/10, 401 sin clave, detección de datos sensibles, usuario no root | Listo |
| 2:10–3:00 | Costos y calidad (E06) | Tabla de `evidence/resultado-comparacion-E06.md`: costo estimado 0,001374 frente a 0,003643 USD, 10/12 frente a 9/12 aprobadas, latencia media 3 802 frente a 1 804 ms. Decir: estimaciones, no factura; optimized combina dos ejecuciones; timeout 30 → 60 s | Listo |
| 3:00–3:30 | Fallos conocidos | Q05 y Q06 no aprobaron en ambas variantes; causa de Q06 (herramienta inexistente); Q12 con criterio de seguridad cumplido pero falla de protocolo en baseline | Listo |
| 3:30–4:00 | Contenedor y vulnerabilidades | Build amd64, humo local, Docker Scout: 0 críticas y 3 altas de OpenSSL sin corrección, revisión de aplicabilidad y riesgo no aceptado | Listo |
| 4:00–4:30 | Trazabilidad real | Traza en LangSmith con el mismo `request_id` que el log | Capturas de LangSmith tomadas (árbol de agentes y `request_id` smoke-a1601932321f, contenido oculto); **pendiente adjuntarlas al repositorio** y usarlas aquí |
| 4:30–4:50 | Despliegue | Swagger y health en la URL pública de Render, consulta autenticada y varias peticiones concurrentes | **[PENDIENTE]** despliegue |
| 4:50–5:00 | Cierre | Resumen de pendientes: despliegue, capturas, decisión de OpenSSL, PR | Listo |

Si el despliegue no está listo al grabar, se omiten las escenas pendientes y el cierre declara explícitamente que no se desplegó; el video no debe superar 5 minutos.
