# Prueba real de una consulta completa (19 de noviembre de 2026)

Informe: `gateway-20261119-223603.json` (SHA-256 `ed415c8d3e186c87b4251f802ece5cab33f31d76825aefbe3c4db150609767e0`).
request_id: `smoke-a1601932321f`. Resultado del script: `passed=true`, etapa `complete`.
Ejecutada por la persona responsable en su terminal; revisada aquí sin repetir llamadas.

## Comprobado (según el informe)
- **Consulta real:** proveedor `gateway`, modelo `@cf/meta/llama-3.3-70b-instruct-fp8-fast`, `ROUTING=false`.
- **Tres llamadas** al modelo (2 del directorio y 1 del revisor), dentro del máximo autorizado de 4; ninguna desde caché; límite de llamadas no activado.
- **Agentes:** coordinador, directorio y revisor; `review_status = approved`.
- **Respuesta correcta:** describe a EMP-0001 (Ana López, Tecnología, Analista de datos) y a ningún otro empleado (dato ficticio).
- **Consumo:** total 641 tokens de entrada y 70 de salida; directorio 389/64; revisor 252/6.
- **Costo estimado:** 0,000346 USD (revisor 0,000087 USD), calculado con la tabla de precios; no es una factura de Cloudflare.
- **Correlación del request_id:** igual en el encabezado y en el cuerpo de la respuesta; eventos del log JSON con ese
  request_id (`handoff`, `agent_run`, `workflow_completed`, `request`, más `audit`) y ejecuciones de LangSmith encontradas en el
  proyecto `multiagente-reto-revision` mediante el metadato `request_id`: `coordinator`, `directory_agent`, `agent_run`, `model_call`,
  `reviewer_agent`, `reviewer_model_call` y `tool_call`.
- `HIDE_INPUTS` y `HIDE_OUTPUTS` activos en la ejecución.

## Observación de presupuesto
La estimación previa de entrada (490, 738 y 817 tokens) fue entre 3,2 y 3,3 veces la entrada real (153, 236 y 252): fue
conservadora en esta muestra de una sola consulta. No demuestra un límite para otras preguntas.

## No comprobado / limitaciones
- No hay captura de la interfaz de LangSmith; la verificación fue por consulta de metadatos. No se comprobó visualmente que las
  entradas aparezcan como `[hidden]`.
- Los eventos del log provienen de la captura en proceso de la prueba, no de logs de un servicio desplegado.
- No se usó el modelo pequeño ni el enrutamiento; no hay medición de ahorro ni de calidad comparada.
- No se contrastó el costo con la facturación de Cloudflare. Intentos anteriores fallidos pudieron generar llamadas sin registro.
- No hay despliegue; no se verificó Render.
