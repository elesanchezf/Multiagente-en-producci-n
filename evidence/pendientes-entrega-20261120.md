# Pendientes obligatorios de entrega (20-nov-2026)

Fuente de requisitos: `Reto-Modulo4.md` (tabla de evidencia). Entrega: 21-nov-2026.

| Área | Comprobado | Pendiente (bloquea) |
| --- | --- | --- |
| Evaluación (costos) | Arnés, 12 preguntas, topes de llamadas y presupuesto; sonda real Gemma 2/3 (Q01, Q04 OK) | Q09 con Gemma real; comparación baseline/optimized real con tokens, calidad, latencia y precios; análisis de límites |
| Despliegue | Build local, usuario no root, health y /ask en contenedor local; CI definido | Despliegue en Render (servicio independiente), Swagger, consulta autenticada con modelo real en la URL pública, concurrencia sobre el despliegue; CI ejecutado en GitHub |
| Observabilidad | Traza real LangSmith con mismo request_id (19-nov, 70B) | Captura de la interfaz de LangSmith; traza del flujo con Gemma |
| Seguridad | Privacidad/PII y aislamiento concurrente probados localmente; claves y auditoría | Revisión de privilegios; decisión de riesgo sobre 6 altas de OpenSSL sin corrección (Scout); revisar contenido de trazas reales |
| Capturas | `screenshots/multiagent-local.png` (local, simulado) | Swagger, Render, LangSmith, resultados reales |
| Documento | README, arquitectura, ADR, evaluación de costos (heredados) | Actualizar documentos de la sesión 4; análisis final con cifras reales |
| Repositorio / PR | Remoto `origin` configurado | Rama sin commits: commit, push y PR hacia `main`; no existe repositorio base del profesor (ver `doc/plan-reto.md`) |
| Video | — | Guion y grabación de 3 a 5 minutos (máximo 5) |

Sin ejecución real nada de lo marcado como pendiente está acreditado. Lo simulado no demuestra el proveedor real.

## Actualización 21-nov-2026
- Comprobado: Q09 real con Gemma aprobada (`costs/20261121-003252-real/`); `scripts/run-comparison.ps1` listo (plan verificado sin red).
- Sigue pendiente: ejecutar la comparación real (autorización suya), análisis con cifras reales, Render, Swagger, capturas LangSmith/Render, decisión de OpenSSL, commits/push/PR, video.
