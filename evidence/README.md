# Evidencias del reto

Cada evidencia debe indicar fecha, versión del código, entorno, comando o acción,
resultado y limitaciones. No incluir claves, encabezados de autenticación ni datos
personales reales. Una prueba simulada no demuestra funcionamiento del proveedor real.

| ID | Criterio | Evidencia prevista | Estado |
| --- | --- | --- | --- |
| E01 | Base reproducible | Manifiesto SHA256, pytest y pylint de la copia inicial | 126 pruebas OK; cobertura 96,61 %; ver baseline/resultado.md |
| E02 | Multiagente | Diagrama y ejecución con coordinación, consulta y revisión | Verificado localmente con modelo simulado; ver multiagent-result.md |
| E03 | Despliegue | Build, digest, usuario del contenedor, health y Swagger | Parcial: build amd64 (21-nov, ID local), usuario no root, health, Swagger local y /ask comprobados en contenedor local (evidence/docker/20261121/). Pendiente: despliegue en Render y Swagger público |
| E04 | Concurrencia | Solicitudes simultáneas, errores y latencias | Local comprobado (300 solicitudes, 30 simultáneas, 0 errores, aislamiento 300/300; evidence/load/summary.json). Pendiente: Render/proveedor real |
| E05 | Observabilidad | Traza real LangSmith y logs con el mismo request_id | Comprobado en una consulta real (19-nov-2026, request_id smoke-a1601932321f): 3 llamadas al modelo de 70B, respuesta correcta aprobada por el revisor, y el mismo request_id en respuesta, log y trazas de LangSmith (consulta por metadatos). Limitaciones: sin captura de la interfaz de LangSmith, log en proceso y no de un servicio desplegado; ver smoke-real/resultado-gateway-20261119.md |
| E06 | Costos | Mismo conjunto de preguntas antes/después, calidad, tokens y costo | Comprobado con límites: comparación real consolidada (12 preguntas por variante; optimized en dos ejecuciones, espera 30→60 s); ver `resultado-comparacion-E06.md`. Costos estimados, no factura; sin ahorro garantizado; Q05 y Q06 no aprobaron en ambas |
| E07 | Seguridad | Pruebas de validación, autenticación, auditoría, PII y privilegios | Parcial: controles de privacidad probados localmente (privacy-tests.txt). Pendiente: revisión de privilegios y despliegue |
| E08 | Vulnerabilidades | Docker Scout de imagen base y final con digest y plataforma | Escaneo del 21-nov-2026: 0 críticas y 3 altas (OpenSSL, sin corrección en Debian) en la imagen final; riesgo no aceptado; ver doc/image-vulnerabilities.md |
| E09 | Entrega | CI, PR, URL, README y video de 3–5 minutos | Pendiente |

Las capturas se guardarán en screenshots/ cuando se observen los resultados reales.
No se crean capturas ficticias ni se reutiliza evidencia histórica como prueba actual.
Los documentos heredados en doc/ describen la sesión 4: deben actualizarse antes de entregar.

## Evidencia disponible de colaboración

- `multiagent-tests.txt`: 141 pruebas, cobertura 96,96 %.
- `multiagent-pylint.txt`: 10.00/10, código de salida 0.
- `multiagent-e2e.txt`: siete pruebas de navegador aprobadas.
- `screenshots/multiagent-local.png`: captura real del navegador local con FakeModel.
- `screenshots/multiagent-response.json`: respuesta de la solicitud capturada.
- `multiagent-server.log`: transiciones con el mismo request_id de la captura.
- `multiagent-source-manifest.json`: hashes del código de esta etapa.

El costo mostrado en la respuesta es simulado: no representa un cobro de Cloudflare.
La ausencia de capturas de LangSmith o Render significa que esa verificación sigue pendiente.


## Evidencia de privacidad y concurrencia (19 de noviembre de 2026)

- `privacy-tests.txt`: 155 pruebas aprobadas, cobertura 97,15 %.
- `privacy-pylint.txt`: 10.00/10, código de salida 0.
- `load/summary.json` y `load/server.log`: prueba local de concurrencia.
- `privacy-concurrency-result.md`: resumen, alcance y pendientes.

Son pruebas locales con modelo simulado y datos ficticios. Las evidencias anteriores se conservan.

Evidencia Docker: `docker/` (resultado.md, scout-base.txt, scout-final.txt, build.txt, linux-tests.txt, smoke.txt).
Comparación de base 3.12 vs 3.13 (solo análisis, sin cambios): `docker/comparacion-312-vs-313.md`.

Preparación LangSmith/costos (sin llamadas reales): `doc/evaluacion-costos.md`, `costs/` (solo arnés simulado) y `smoke-real/` (solo local). E08 sigue abierto: 6 vulnerabilidades altas de OpenSSL sin aceptar.

Actualización: prueba pequeña autorizada (1 consulta, máx. 4 llamadas); evaluación completa NO autorizada. Precios revalidados y límite de llamadas y presupuesto estimado `app/budget.py`: ver `doc/evaluacion-costos.md`. E05, E06 y E08 siguen sin verificar.

Prueba real del 19-nov-2026: NO aprobada. Falló con 403 de LangSmith antes de guardar informe; consumo de las llamadas al modelo no registrado. Ver `doc/evaluacion-costos.md`. E05 sigue pendiente.

LangSmith: acceso aún sin verificar (403 sin X-Organization-Id; 401 con él). Diagnóstico seguro preparado en `scripts/langsmith_workspaces.py`; ver `doc/evaluacion-costos.md`.

E05: informe `smoke-real/gateway-20261119-223603.json` conservado. E03 (despliegue), E06 (ahorro) y E08 (OpenSSL) siguen sin verificar.

Catálogo de Cloudflare (`cloudflare-check/models-20261119-225959.json`, conservado): los modelos 8B candidatos no aparecen; el 70B sí, con precio confirmado. Precios copiados por suposición eliminados de `data/model_prices.json`. E06 sigue pendiente; ver `doc/evaluacion-costos.md`.

Escaneo del catálogo conservado (`cloudflare-check/scan-20261119-232144.json`): 16 modelos con retirada el 20-nov-2026 descartados; candidato Gemma 4 y sonda preparados, sin ejecutar. E06 sigue pendiente.

Sonda Gemma (`costs/20261120-015535-real/results.json`, conservada): 2/3; Q09 fallida por el prompt del directorio (ver `doc/evaluacion-costos.md`). Prompt corregido localmente; Q09 sin revalidar con el modelo real. E06 sigue pendiente.

## Actualización 20-nov-2026
- `e2e-fake-20261120.txt`: 7 pruebas de navegador aprobadas con servidor simulado iniciado por `e2e/conftest.py` (causa del fallo "invalid URL": faltaba URL base). 234 pruebas unitarias aprobadas (cobertura 97,90 %).
- Precio de Gemma separado: 0,05/0,30 para resultados y 0,10 solo como reserva de presupuesto; ver `doc/evaluacion-costos.md`.
- Q09 validada solo con modelo simulado; revalidación con Gemma real pendiente.
- Lista de pendientes de entrega: `pendientes-entrega-20261120.md`.

## Actualización 21-nov-2026
- `costs/20261121-003252-real/` (conservada): Q09 optimized con Gemma real aprobada: 1 llamada, 192 tokens de entrada y 25 de salida, 1,71e-05 USD estimados (0,05/0,30), 1 571 ms, `review_status: no_evidence`, 0 fallas de protocolo, estado 200. Valida solo Q09 tras corregir el prompt; no sustituye la comparación completa.
- La sonda original 2/3 (`costs/20261120-015535-real/`) no se modificó; se conserva como evidencia del fallo previo de Q09 y de la corrección.
- `scripts/run-comparison.ps1` preparado (plan comprobado sin inferencia; la ejecución real exige `-ConfirmRealCalls`). Plan: 96 llamadas máximas, ≈ 0,0109 USD esperado, ≈ 0,0755 USD de reserva conservadora, presupuesto propuesto 0,08 USD. E06 sigue pendiente.
- `scripts/eval_costs.py` guarda resultados parciales (`"complete": false`) y usa carpeta nueva por ejecución; código de salida 1 si se detiene.

## Actualización 21-nov-2026 (comparación parcial)
- `costs/20261121-004715-real/` (conservada): comparación real PARCIAL (baseline 12/12; optimized 4 evaluadas; detenida en optimized/Q05 por 502 tras 30,03 s). No es evidencia de ahorro. Análisis en `comparacion-parcial-20261121.md`.
- Corrección mínima: tope de espera del gateway 60 s y motivo del error en el log. E06 sigue pendiente hasta completar optimized Q05–Q12.

## Actualización 21-nov-2026 (comparación consolidada)
- `costs/20261121-010610-real/` (conservada): continuación completa de optimized Q05–Q12 (20 llamadas, 6 aprobadas, 1 falla de protocolo).
- `costs/consolidado-20261121-004715-real+20261121-010610-real/` y `resultado-comparacion-E06.md`: consolidación sin inferencia. El intento fallido de Q05 se conserva aparte; su consumo es desconocido.

## Actualización 21-nov-2026 (preparación de entrega)
- `docker/20261121/`: etiquetas oficiales de Python, correcciones disponibles, build de `multiagente-reto:final` (ID local, no digest de registro), Scout de la base candidata (0 críticas, 5 altas) y de la imagen final (0 críticas, 3 altas de OpenSSL sin corrección), extractos del Debian Security Tracker y prueba de humo. E03 sigue parcial (sin despliegue ni Swagger público); E08 abierto: riesgo no aceptado.
- `langsmith-check/workspaces-20261119-223325.anonimizado.json`: copia anonimizada para entrega; el original sigue en local y está excluido del control de versiones.
- Documentos de entrega: `doc/entrega.md`, `doc/guion-video.md`, `doc/publicacion.md`, `doc/adr/0013-coordinador-y-revisor.md`.

## Copias anonimizadas (21-nov-2026)
Los originales con rutas o identificadores personales se conservan solo en local y no se versionan (`.gitignore`). Para entregar se usan copias con sufijo `.anonimizado` que empiezan con la línea `[ANONIMIZADO]`:
`baseline/api-diagnostic`, `baseline/pytest-isolated`, `baseline/pytest`, `e2e-fake-20261120`, `multiagent-e2e`, `multiagent-tests` y `langsmith-check/workspaces-20261119-223325`. Las referencias de este índice a esos nombres se refieren al original local; en el repositorio está la copia anonimizada. Generador: `scripts/anonymize_evidence.py`.
- `docker/20261121/openssl-aplicabilidad.txt` y `doc/openssl-aplicabilidad.md`: revisión de aplicabilidad de las tres CVE (no se encontró uso; no afectado no demostrado).

## Capturas de LangSmith (21-nov-2026)
La persona responsable tomó dos capturas de la interfaz de LangSmith: el árbol de agentes y el `request_id` smoke-a1601932321f con contenido oculto. Están en `evidence/screenshots/`: `langsmith-arbol-agentes.png` (árbol completo; contiene una búsqueda del navegador con 0/0 que **no** es evidencia de correlación) y `langsmith-correlacion-request-id.png` (metadatos `client` = smoke y `request_id` = smoke-a1601932321f, salida oculta). Son de una prueba local del 19-nov-2026 con Cloudflare y LangSmith reales (70B), no del despliegue. Revisadas visualmente: sin claves ni identificadores de cuenta.
