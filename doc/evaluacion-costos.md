# Preparación de Cloudflare, LangSmith y evaluación de costos

Estado: preparado, **no ejecutado con servicios reales**. Hasta registrar las pruebas,
LangSmith, Cloudflare y el ahorro real no están verificados.

Advertencia: con `MODEL_PROVIDER=gateway` y con trazas activas los datos salen a
terceros (Cloudflare, LangSmith). Use solo datos ficticios hasta contar con
autorización institucional. Las trazas se envían con entradas y salidas ocultas
(`HIDE_INPUTS=true`, `HIDE_OUTPUTS=true`); solo viajan `request_id` y el nombre del cliente.

## Variables necesarias (solo nombres)

| Variable | Secreto | Uso |
| --- | --- | --- |
| `MODEL_PROVIDER=gateway` | No | Activa Cloudflare |
| `CF_ACCOUNT_ID` | No, pero privada | Cuenta de Cloudflare |
| `CF_GATEWAY_ID` | No | Gateway (por omisión `default`) |
| `CF_API_TOKEN` | **Sí** | Token de API de Cloudflare con permiso para Workers AI. Se envía como `Authorization: Bearer` |
| `CF_AIG_TOKEN` | **Sí**, opcional | Token de autenticación del AI Gateway. Se envía como `cf-aig-authorization`. Solo hace falta si el gateway tiene la autenticación activada |
| `LANGSMITH_TRACING=true` | No | Activa trazas |
| `LANGSMITH_API_KEY` | **Sí** | Clave de LangSmith |
| `LANGSMITH_PROJECT` | No | Proyecto sugerido: `multiagente-reto-revision` |
| `LANGSMITH_ENDPOINT` | No | Solo si su cuenta está en la región de la UE |
| `HIDE_INPUTS`, `HIDE_OUTPUTS` | No | Dejar en `true` |

`CF_API_TOKEN` autoriza la inferencia en Workers AI. `CF_AIG_TOKEN` autoriza el uso del
gateway (caché, registro, límites); son credenciales distintas y no se sustituyen entre sí.
Confirme los permisos exactos en el panel de Cloudflare y use el mínimo privilegio.

## Cómo introducirlas en privado

En su propia ventana de PowerShell, no en la conversación (el texto no se muestra ni se guarda):

```powershell
$s = Read-Host 'CF_API_TOKEN' -AsSecureString
$env:CF_API_TOKEN = [System.Net.NetworkCredential]::new('', $s).Password
```

Repita para `CF_AIG_TOKEN` y `LANGSMITH_API_KEY`; los valores no secretos se asignan con
`$env:CF_ACCOUNT_ID = '...'`. Las variables viven solo en esa ventana. No use `.env` ni
`!` para esto. Después ejecute los scripts desde esa misma ventana; escriben solo
resumenes sin secretos en `evidence/`. Revoque o rote los tokens al terminar.

## Prueba pequeña de una consulta completa (`scripts/real_smoke.py`)

- Sin banderas: muestra si cada variable está definida (nunca su valor).
- `--provider fake`: comprobación local ya ejecutada (request_id igual en encabezado,
  cuerpo y eventos del log; coordinador, directorio y revisor).
- `--provider gateway --confirm-real-calls`: **una** solicitud, **máximo 4 llamadas** al
  modelo (3 pasos del directorio + 1 del revisor; típico: 3). Con `LANGSMITH_API_KEY` consulta
  (solo lectura) las trazas con ese `request_id` y espera las ejecuciones `coordinator`,
  `directory_agent`, `agent_run`, `model_call`, `reviewer_agent`, `reviewer_model_call`.
  La traza queda como `passed` solo si todo coincide.
- Captura manual en LangSmith: abra la traza, compruebe que no aparece ninguna clave y que
  las entradas dicen `[hidden]`, y guarde la imagen en `evidence/screenshots/`.

## Evaluación baseline/optimizada (`scripts/eval_costs.py`)

Conjunto fijo: `data/eval_questions.json` (12 preguntas ficticias, incluye historial,
pregunta larga, empleado inexistente, orientación e intento de extracción de salario).

| Variante | Palancas |
| --- | --- |
| baseline | `ROUTING=false` (siempre modelo capaz), `HISTORY_WINDOW=50` |
| optimizada | `ROUTING=true`, `HISTORY_WINDOW=6` |

Ambas con `CACHE_TTL_SECONDS=0` (la caché no se mezcla con las demás palancas),
`MODEL_TEMPERATURE=0`, mismo tope de tokens y las trazas apagadas.
**Criterio de calidad idéntico**: HTTP 200, todas las cadenas `must_include` presentes y
ninguna `must_exclude` en la respuesta. Se reporta aprobadas/12 por variante.
El consumo del revisor se registra aparte (`review_input_tokens`, `review_output_tokens`,
`review_cost_usd`) y también está incluido en los totales.

Validación del arnés con el modelo simulado (19-nov-2026, sin red): 10/12 en ambas variantes;
fallan Q06 y Q10 porque el modelo simulado no compara ni usa historial. Es solo prueba del
arnés: el costo simulado no representa ahorro real.

## Autorización requerida antes de llamadas reales

Ejecutar `python scripts/eval_costs.py` imprime el plan. Supuestos:
precios de `data/model_prices.json` (consulta 2026-11-04, deben revalidarse);
caso esperado: 3 llamadas por pregunta, 500 tokens de entrada y 60 de salida por llamada;
peor caso: 4 llamadas por pregunta con el modelo capaz, 1 500 tokens de entrada y 300 de salida.

| | Llamadas máximas | Llamadas esperadas | Costo esperado | Costo peor caso |
| --- | --- | --- | --- | --- |
| baseline (12 preguntas) | 48 | 36 | ≈ 0,0101 USD | ≈ 0,0535 USD |
| optimizada (12 preguntas) | 48 | 36 | ≈ 0,0038 USD | ≈ 0,0535 USD |
| Prueba pequeña | 4 | 3 | despreciable (< 0,002 USD) | < 0,002 USD |
| **Total** | **100** | **75** | **≈ 0,014 USD** | **≈ 0,109 USD** |

La ejecución real exige `--max-calls` (al menos 96) y `--max-usd` y se detiene al alcanzar
cualquiera de los topes. Las estimaciones no incluyen posibles cargos o cuotas de su plan en
Cloudflare ni LangSmith (las trazas cuentan para su cuota); revíselos en sus paneles.
El costo reportado por la aplicación se calcula con la tabla de precios, no es un cobro.

Limitaciones: una sola ejecución por variante con temperatura 0; 12 preguntas no bastan
para conclusiones estadísticas; la latencia depende de la red.

## Actualización: autorización parcial y control de presupuesto (19-nov-2026)

Autorizado por la persona responsable: **solo la prueba pequeña** (una consulta, máximo
4 llamadas al modelo, sin reintentos). La evaluación baseline/optimizada **no** está autorizada.

### Precios y modelos revalidados
Fuente: página oficial de precios de Workers AI (modificada el 2026-11-18 según sus metadatos).
- `@cf/meta/llama-3.3-70b-instruct-fp8-fast`: 0,293 USD entrada y 2,253 USD salida por millón. Coincide con la tabla.
- `@cf/meta/llama-3.1-8b-instruct-fp8-fast`: 0,045 USD entrada y 0,384 USD salida por millón. Se agregó a `data/model_prices.json`.
- `@cf/meta/llama-3.1-8b-instruct-fast` (valor por omisión de `MODEL_SMALL`): **no aparece en la
  página de precios**; un listado de documentación y el registro de cambios sugieren que existe,
  pero su precio no está confirmado. Decisión pendiente antes de la evaluación: confirmarlo en su
  panel de Cloudflare o cambiar `MODEL_SMALL` a `...-fp8-fast`.
- Neuronas gratuitas: 10 000 por día; adicionales a 0,011 USD por 1 000 (plan de pago). Pueden
  hacer que el cobro real difiera del costo calculado.
- La prueba pequeña fuerza `ROUTING=false`: usa únicamente el modelo capaz, cuyo precio está confirmado.

### Prueba pequeña: límite de llamadas y presupuesto estimado
Son dos cosas distintas (`app/budget.py`, probado en `tests/test_budget.py`):
- **Límite de llamadas (exacto):** máximo 4 llamadas al modelo (3 pasos del directorio + 1 del
  revisor). La quinta se rechaza antes de salir. No hay reintentos: una llamada fallida cuenta y no se repite.
- **Presupuesto estimado (no garantizado):** antes de cada llamada se estima la entrada con los bytes
  UTF-8 del texto más 8 por mensaje, y se reserva el peor caso con 300 tokens de salida; tope de
  estimación de 3 000 tokens por llamada y de 0,01 USD. Después se acumula el consumo informado por el
  proveedor. La estimación no replica el tokenizador ni la plantilla de chat de Cloudflare, así que
  **no asegura un máximo exacto de tokens ni de dólares**; el gasto real puede diferir y no se ha
  demostrado que el sobregiro sea pequeño. Configure además un límite de gasto en el panel de Cloudflare.

Modelo y límites explícitos: la prueba fija `MODEL_SMALL` y `MODEL_LARGE` en
`@cf/meta/llama-3.3-70b-instruct-fp8-fast` (precio confirmado), `ROUTING=false`, `AGENT_MAX_STEPS=3`,
`MODEL_MAX_TOKENS=300` y temperatura 0. No hereda esas variables del entorno y el resultado falla si
el modelo usado no es ese (`tests/test_real_smoke.py`). `HIDE_INPUTS` y `HIDE_OUTPUTS` se fuerzan a `true`.

Criterio de aprobación (`passed`): HTTP 200; `request_id` igual en encabezado y cuerpo; eventos del log
con ese `request_id`; coordinador, directorio y revisor; **`review_status == "approved"`**; la respuesta
describe a EMP-0001 (id y nombre) y a ningún otro empleado; modelo de 70B; 4 llamadas como máximo;
entradas y salidas ocultas; y las ejecuciones esperadas en LangSmith con ese `request_id`.
Un rechazo del revisor, otro empleado u otra condición faltante dan `passed=false`.

### Evaluación completa (no autorizada): cómo se acotaría
El supuesto de 1 500 tokens por llamada solo sirve para estimar; no es un límite. Se usarían los mismos
dos mecanismos: límite exacto de llamadas (`--max-calls`, no menor que 96) y presupuesto estimado
(`--max-usd`, `--max-input-tokens`, 300 tokens de salida), con parada ante el primer tope. Las mismas
salvedades aplican: es un presupuesto estimado, no un máximo garantizado. Las preguntas y criterios no
cambiaron, incluidos Q06 y Q10, que fallaron con el modelo simulado.

### Pylint de los scripts
Los errores `E0401` provenían de que Pylint no tenía la raíz del repositorio en su ruta al analizar
`scripts/`; los scripts se ejecutan correctamente. Se comprobó con `PYTHONPATH=.` (10,00/10) y se
resolvió con `.pylintrc` (init-hook que añade la raíz). `pylint app tests scripts/eval_costs.py
scripts/real_smoke.py --max-line-length=88`: 10,00/10.

### Ejecución de la prueba pequeña (en su terminal)
```powershell
$env:MODEL_PROVIDER = 'gateway'
$env:LANGSMITH_TRACING = 'true'; $env:HIDE_INPUTS = 'true'; $env:HIDE_OUTPUTS = 'true'
$env:LANGSMITH_PROJECT = 'multiagente-reto-revision'
$env:CF_ACCOUNT_ID = '<su cuenta>'; $env:CF_GATEWAY_ID = '<su gateway>'
foreach ($n in 'CF_API_TOKEN','CF_AIG_TOKEN','LANGSMITH_API_KEY') {
  $s = Read-Host $n -AsSecureString
  Set-Item "env:$n" ([System.Net.NetworkCredential]::new('', $s).Password)
}
.venv\Scripts\python.exe scripts\real_smoke.py            # solo muestra definida/vacía
.venv\Scripts\python.exe scripts\real_smoke.py --provider gateway --confirm-real-calls
```
`CF_AIG_TOKEN` solo si su gateway tiene autenticación; si no, omítalo (Enter vacío).
El informe queda en `evidence/smoke-real/`.

## Primer intento de la prueba real (19-nov-2026): falló en LangSmith
Según la persona responsable, la ejecución terminó con 403 Forbidden en `POST /runs/multipart` y
en `GET /sessions` (`read_project`), y la excepción ocurrió antes de guardar el informe.
Consecuencias: **no existe informe**; las llamadas al modelo anteriores a la consulta de LangSmith
probablemente se realizaron (hasta 3) pero su consumo y costo no quedaron registrados, y la
correlación en LangSmith no está verificada. La prueba no pasó.

Correcciones: (1) `scripts/langsmith_check.py` comprueba el acceso sin llamar a Cloudflare
(lectura, proyecto y escritura de una traza oculta leída de vuelta); (2) `real_smoke.py` ejecuta ese
chequeo **antes** de cualquier llamada al modelo y se detiene si falla; (3) guarda un informe parcial
inmediatamente después de la consulta al modelo y otro final, y un error de LangSmith se registra
como `langsmith_error` sin perder el consumo medido. Verificado con clientes simulados
(`tests/test_langsmith_check.py`, `tests/test_real_smoke.py`). Con `LANGSMITH_WORKSPACE_ID` y
`LANGSMITH_ENDPOINT` definidos, la biblioteca los usa por sí misma.

Comando del chequeo (solo LangSmith; sin Cloudflare; envía una traza mínima con contenido oculto):
`.venv\Scripts\python.exe scripts\langsmith_check.py` (agregue `--read-only` para no enviar trazas).

## Diagnóstico de workspaces de LangSmith (`scripts/langsmith_workspaces.py`)
Observado en `evidence/langsmith-check/`: sin `X-Organization-Id` la consulta `GET /api/v1/workspaces`
devolvió 403 (21:50 UTC); con `X-Organization-Id` devolvió 401 (22:00 y 22:08 UTC). Esos informes
no guardaban el cuerpo del error, así que la causa no está confirmada. Que el estado cambie de 403 a
401 al enviar el encabezado es un dato, no una explicación: no permite concluir si el Organization ID
es incorrecto, si la clave no corresponde a la organización o si hay otra causa.

La nueva versión: (1) valida localmente (solo válido/inválido/no definido, con categorías de problema
como comillas, espacios o UUID inválido) y **no envía la petición** si algo es inválido; (2) ante un
error extrae solo `code` y `message` del cuerpo, sin credenciales ni encabezados y con máximo de
200 caracteres, y nunca guarda el cuerpo completo; (3) retira la afirmación de que el 403 "no depende de
`LANGSMITH_WORKSPACE_ID`": la ausencia de `X-Tenant-Id` no demuestra esa conclusión;
(4) registra los nombres de los encabezados enviados, no sus valores. Probado con respuestas
simuladas (`tests/test_langsmith_workspaces.py`).

## Siguiente paso: comparación baseline/optimizada (preparada, NO autorizada)

### Modelo pequeño: sin confirmar
Fuentes oficiales leídas el 19-nov-2026 (por subagentes, lectura parcial) que no coinciden entre sí:
- Página de precios: lista `@cf/meta/llama-3.1-8b-instruct-fp8-fast` (0,045 USD entrada y 0,384 USD salida por
  millón); no lista `@cf/meta/llama-3.1-8b-instruct-fast`.
- Registro de cambios del 8-may-2026: lista `-fast` como variante que sigue activa; no menciona `-fp8-fast`.
- Catálogo de modelos: no lista ninguno de los dos, y las fichas de ambos devolvieron 404.
Conclusión: no está confirmado cuál identificador existe y responde en su cuenta, ni el precio del `-fast`
(la entrada de `data/model_prices.json` para `-fast` repite los valores del `-fp8-fast` y es un supuesto).
Verificación de solo lectura, sin ejecutar modelos ni consumir inferencia: `scripts/cf_models_check.py`
consulta el catálogo de la cuenta y muestra, por candidato, si aparece y su precio y contexto si los informa.
La evaluación exige `MODEL_SMALL` y `MODEL_LARGE` explícitos y no se ejecuta sin ellos.

### Plan (sin llamadas): `python scripts/eval_costs.py`
- Preguntas y criterios sin cambios (12 preguntas, incluidos Q06 y Q10; `tests/test_eval_costs.py`).
- Variantes: baseline (`ROUTING=false`, historial 50) y optimizada (`ROUTING=true`, historial 6); misma caché apagada.
- Máximo de llamadas: 96 (48 + 48); esperadas 72. Consumo del revisor registrado por separado.
- Costo estimado: esperado ≈ 0,011 USD (baseline ≈ 0,008; optimizada ≈ 0,003); peor caso ≈ 0,107 USD.
  Supuestos: 3 llamadas por pregunta con 300 tokens de entrada y 60 de salida por llamada (la prueba real midió
  214 y 23 en promedio, una sola consulta); peor caso: 4 llamadas por pregunta con el modelo grande, 1 500 tokens de
  entrada y 300 de salida. Precios: grande 0,293/2,253 USD por millón (confirmado); pequeño 0,045/0,384 USD solo si
  el identificador resulta ser `-fp8-fast`. Referencia medida: 0,000346 USD por una consulta de 3 llamadas con el 70B.
- Control: límite exacto de 96 llamadas y presupuesto estimado (`--max-usd 0.05`, tope de estimación de
  3 000 tokens de entrada por llamada y 300 de salida). El presupuesto no es un máximo garantizado de gasto.

## Corrección del plan (19-nov-2026, noche): modelo pequeño y presupuesto

### Evidencia conservada
`evidence/cloudflare-check/models-20261119-225959.json` (SHA-256 `627cc4353f952c872590cdefb39f52da1b36d6f4a5075de734794d35d959d888`):
catálogo de la cuenta con HTTP 200 en las dos consultas. `@cf/meta/llama-3.1-8b-instruct-fast` y
`@cf/meta/llama-3.1-8b-instruct-fp8-fast` **no aparecen**. `@cf/meta/llama-3.3-70b-instruct-fp8-fast` sí, con
0,293 USD entrada / 2,253 USD salida por millón y contexto 24 000: coincide con la tabla de precios.

### Cambios de configuración
- `data/model_prices.json`: se eliminaron las entradas de los dos modelos 8B (su precio se había copiado por
  suposición). Solo quedan `fake` y el 70B confirmado. Un modelo sin precio impide arrancar y bloquea el plan.
- `MODEL_SMALL` por omisión pasó a ser el 70B (provisional, README y `.env.example`): con el identificador
  inexistente la configuración por omisión no podía arrancar. Mientras no haya un modelo pequeño verificado, el
  enrutador envía todo al mismo modelo. Es un cambio de comportamiento transitorio.

### Candidato propuesto (provisional): `@cf/meta/llama-3.2-3b-instruct`
- Precio según la página oficial de precios (no confirmado en el catálogo de la cuenta): 0,051 USD entrada /
  0,335 USD salida por millón, unas 5,7 y 6,7 veces menos que el 70B. Sin requisito de plan de pago.
- Aparece en el listado de la documentación; **falta confirmarlo en el catálogo de la cuenta** con
  `scripts/cf_models_check.py --scan` (recorre todas las páginas de "Text Generation", solo lectura).
- **Disponibilidad no es compatibilidad.** El protocolo exige JSON estricto (`{"tool":...}`, `{"answer":...}`,
  `{"approved":...}`) sin texto adicional. Ningún modelo pequeño lo tiene comprobado: solo una sonda de inferencia
  lo demostrará. Elegí la familia Llama por usar la misma plantilla de chat que el 70B ya probado, no porque esté
  demostrado.
- Más baratos en la página de precios pero con mayor riesgo de romper el JSON: `granite-4.0-h-micro` (0,017/0,112)
  y `llama-3.2-1b-instruct` (0,027/0,201). `qwen3-30b-a3b-fp8` (0,051/0,335) puede emitir razonamiento antes de la
  respuesta. Alternativa intermedia si el 3B falla: `llama-3.1-8b-instruct-fp8` (0,152/0,287, listado en el catálogo
  documental). Los precios solo se escriben en `data/model_prices.json` tras verlos en el escaneo de la cuenta.

### Plan por etapas (ninguna autorizada todavía)
0. Escaneo del catálogo, sin inferencia: `cf_models_check.py --scan`.
1. Sonda de compatibilidad con el candidato: Q01, Q04 y Q09, solo variante optimizada. Máximo 12 llamadas
   (esperadas 9); estimado provisional ≈ 0,0003 USD (peor caso ≈ 0,002 USD). Se cuentan aparte las fallas de
   protocolo (`protocol_failures`) y la calidad.
2. Solo si la sonda no rompe el protocolo: comparación completa de 12 preguntas por variante. Máximo 96 llamadas
   (esperadas 72). Con precios de la página, calculado a mano: esperado ≈ 0,010 USD (baseline ≈ 0,008; optimizada
   ≈ 0,002) y peor caso ≈ 0,073 USD (optimizada: 9 preguntas al modelo pequeño y 3 —Q06, Q07, Q11— al grande por el
   enrutador). Provisional hasta confirmar los precios en el catálogo.

### Aclaración sobre `--max-input-tokens`
Es el tope de la **estimación** de entrada de cada llamada (bytes UTF-8 más 8 por mensaje), no un conteo exacto
de tokens. Por omisión vale 3000 (el comando propuesto usaba 3000). Un valor como 30 rechazaría incluso la consulta
más simple (su estimación fue de 490 tokens) antes de enviarla: no habría llamadas ni datos. Ahora el script se
niega con un mensaje si el valor es menor que 1500. No existe informe de evaluación real en `evidence/costs/`.

## Escaneo del catálogo y candidato Gemma 4 (19-nov-2026, noche)

### Evidencia conservada
`evidence/cloudflare-check/scan-20261119-232144.json` (SHA-256
`d0120441ba0b321f0afb9dc42acfb4837f86c4dd32bb8733107132a88ae5850c`): una página, 41 modelos de generación de texto, 13 sin precio
interpretable. 16 tienen `planned_deprecation_date = 2026-11-20` y **se descartan para esta evaluación**, entre ellos
`llama-3.2-1b-instruct`, `llama-3.2-3b-instruct` (el candidato anterior), `llama-3.1-8b-instruct-fp8`, `qwen3-30b-a3b-fp8`,
`glm-5.3-flash`, `deepseek-v4-flash-0731`, `deepseek-v4-pro-0813`, `nemotron-3-120b-a12b`, `kimi-k2.6`, `kimi-k2.7-code`,
`glm-5.2`, `qwq-32b`, `deepseek-r1-distill-qwen-32b` y tres modelos LoRA. La paginación no se pudo comprobar (todo cupo
en la primera página).

### Candidato: `@cf/google/gemma-4-26b-a4b-it`
En el catálogo de la cuenta: contexto 256 000, `function_calling=true`, sin beta ni retirada planificada.
- **Precio, discrepancia sin resolver:** catálogo de la cuenta 0,05/0,30 USD por millón (entrada/salida); página de precios
  y ficha del modelo 0,10/0,30. La tabla usa el valor mayor (0,10) como supuesto conservador y lo dice en su campo `note`.
  La salida coincide en las tres fuentes.
- **Documentación oficial (lectura parcial por subagente):** compatible con `/v1/chat/completions` (formato estilo OpenAI);
  mensajes con roles `system`/`user`/`assistant`; `max_tokens` está marcado como obsoleto a favor de `max_completion_tokens`;
  `temperature` 0–2; `response_format` admite `json_object` y `json_schema`; respuesta con `choices[].message.content`
  (cadena o `null`) y `usage.prompt_tokens`/`completion_tokens`.
- **Modelo de razonamiento:** `chat_template_kwargs.enable_thinking` vale `true` por omisión. Desactivarlo con `false` es
  una deducción del esquema, no un ejemplo documentado. No se documenta si los tokens de razonamiento cuentan dentro del
  tope de salida ni si el razonamiento puede aparecer en `content`.
- **No confirmado en la documentación leída:** la URL del gateway que usa nuestro adaptador
  (`gateway.ai.cloudflare.com/v1/{cuenta}/{gateway}/workers-ai/v1/chat/completions`); solo sabemos que funcionó con el 70B
  (prueba real del 19-nov). Tampoco que `enable_thinking` o `response_format` se acepten por esa ruta con este modelo.

### Compatibilidad con el adaptador y el protocolo
| Aspecto | Estado |
| --- | --- |
| Formato de solicitud y respuesta (`messages`, `choices[0].message.content`, `usage`) | Compatible según la documentación; sin comprobar con inferencia |
| `content = null` | Nuestro adaptador lo trata como error (502) y cuenta como llamada |
| Razonamiento activado por omisión | Riesgo: consume salida (tope 300) y puede romper el JSON |
| Envoltura en bloque de código Markdown | Riesgo habitual; nuestro analizador exige JSON puro y lo contaría como falla de protocolo |
| Soporte de herramientas nativo | No demuestra el cumplimiento de nuestro protocolo JSON propio (`{"tool":...}`, `{"answer":...}`, `{"approved":...}`) |
Conclusión: **compatible en formato, protocolo JSON no demostrado.** Para reducir los riesgos, el adaptador acepta ahora
`MODEL_EXTRA_PARAMS` (JSON por modelo, lista cerrada: `chat_template_kwargs.enable_thinking`/`clear_thinking` booleanos y
`response_format.type` = `json_object` o `text`; no puede sobrescribir `model`, `messages`, `max_tokens` ni `temperature`).
Para la sonda: `enable_thinking=false` y `response_format=json_object` solo para Gemma. Probado con transporte simulado.
La evaluación también se detiene ante el primer estado distinto de 200 (error del proveedor o bloqueo de datos).

### Sonda (preparada, NO autorizada): Q01, Q04 y Q09, variante optimizada
Qué modelo usa cada agente (el enrutador elige por pregunta; las tres van al modelo pequeño):
- Coordinador: sin modelo (código determinista).
- Agente de directorio: `@cf/google/gemma-4-26b-a4b-it`.
- Agente revisor: el mismo Gemma (contexto independiente, pero no un modelo distinto). Q09 no tiene evidencia y no pasa por el revisor.
- `MODEL_LARGE` (70B) se configura pero no debería usarse en estas tres preguntas.
Llamadas: máximo 12 (4 por pregunta, incluido el revisor), sin reintentos automáticos; esperadas 7 a 9
(Q01: 2 directorio + 1 revisor; Q04: igual; Q09: 1).
Presupuesto estimado con 0,10/0,30 USD (incluye al revisor): esperado ≈ 0,0004 USD; peor caso ≈ 0,0029 USD (12 llamadas de
1 500 tokens de entrada estimados y 300 de salida). Con el precio de catálogo (0,05) sería menor. Los topes son estimaciones.
Plan completo recalculado con el costo del modelo enrutado: esperado ≈ 0,011 USD, peor caso ≈ 0,076 USD; 96 llamadas máximo.

### Hallazgo de la sonda de Gemma 4 (2/3) y corrección de Q09

Evidencia conservada sin cambios: `evidence/costs/20261120-015535-real/results.json` (7 llamadas, ≈ 0,000188 USD
estimados, Q01 y Q04 aprobadas, Q09 no aprobada, 0 fallas de protocolo).

- **Q09** ("Hola, ¿qué puedes hacer?"): criterio sin cambios, la respuesta debe contener "Pregúntame por un empleado". Respuesta
  publicada: "No pude verificar la respuesta con el directorio. Reformula la pregunta." (`review_status: no_evidence`, 1 llamada,
  sin revisor).
- **Causa:** Gemma devolvió un JSON válido con `answer` y sin consultar herramientas. El coordinador sustituye toda respuesta sin
  evidencia, salvo que sea idéntica a `GUIDANCE_ANSWER`. El prompt del directorio solo decía "orienta al usuario" y no incluía ese
  texto, por lo que solo el modelo simulado lo reproducía. No se descarta el evaluador, el revisor ni el enrutamiento.
- **Limitación:** el texto que escribió Gemma no quedó registrado (entradas y salidas ocultas); la causa se deduce del código.
- **Corrección aplicada (opción 2):** `DIRECTORY_PROMPT` (compartido por baseline y optimized, una sola constante) indica que ante
  saludos o preguntas sobre capacidades se responda exactamente `{"answer": GUIDANCE_ANSWER}`; el JSON se genera con
  `GUIDANCE_ANSWER` como única fuente. No cambian los criterios, la política de evidencia ni la ocultación de entradas y salidas.
- **Verificación local (sin red):** una consulta sobre empleados sin evidencia sigue rechazada (`REJECTED_ANSWER`,
  `no_evidence`); el saludo con la guía exacta se publica. Q09 con Gemma real aún NO se ha revalidado.
- **Validación de una llamada:** `AGENT_MAX_STEPS=1` limita Q09 a un paso; con un solo paso el revisor no puede actuar, por lo que
  `max_calls_per_question(1) = 1` (con 3 pasos sigue siendo 4). Esa variable es un ajuste solo de la validación, distinto de la
  configuración de la comparación completa.
- La ejecución de Q01 y Q04 de la sonda se hizo con el prompt anterior; si se hace la comparación completa se ejecutará con el nuevo.

## Aclaración del precio de Gemma y verificación de Q09 (20-nov-2026)

### Precio de `@cf/google/gemma-4-26b-a4b-it`
- Origen de la diferencia: `scan-20261119-232144.json` (catálogo de la cuenta) informa 0,05 USD de entrada y 0,30 de salida por
  millón; la página oficial de precios y la ficha del modelo informan 0,10 de entrada. La noche del 19-nov se usó 0,10 en la
  única tabla para todo, por prudencia, sin que ese valor proviniera de la cuenta.
- Ahora la tabla distingue dos usos (`Pricing.cost` y `Pricing.reserve_cost`):
  - **Precio para calcular resultados:** 0,05 / 0,30 (catálogo de la cuenta, evidencia conservada). Es el único que usan las
    respuestas, los informes y los totales.
  - **Margen conservador de reserva:** `reserve_input` = 0,10 / `reserve_output` = 0,30. Solo lo usan `BudgetGuard.reserve` (reserva
    antes de cada llamada) y el peor caso del plan. Nunca altera un costo informado.
- Limitación: el catálogo es la fuente de la cuenta, pero no una factura. Si Cloudflare cobrara 0,10, el costo de entrada informado
  quedaría a la mitad; el cobro real se contrasta en el panel de Cloudflare.
- La sonda del 20-nov (`costs/20261120-015535-real/results.json`) se conserva sin cambios: informó 0,000188 USD con 0,10.
  Con 0,05 los mismos tokens (1 276 de entrada, 201 de salida) cuestan ≈ 0,000124 USD. Ambas cifras son estimaciones.

### Q09: corrección compartida y criterios
- `DIRECTORY_PROMPT` es una sola constante (`app/multiagent.py`) usada por el coordinador para ambas variantes; baseline y
  optimized no tienen prompts distintos. `GUIDANCE_ANSWER` es su única fuente.
- Criterios de Q09 en `data/eval_questions.json` sin cambios: `must_include = ["Pregúntame por un empleado"]`, `must_exclude = []`.
- Comprobación local con modelo simulado (`--run fake --only Q09`, `AGENT_MAX_STEPS` 1 y 3, ambas variantes): aprobada, 1 llamada.
  Con modelo simulado esto no prueba el comportamiento de Gemma real.

### Pruebas de navegador (e2e)
Las pruebas no tenían URL base ni arrancaban servidor: `page.goto("/")` fallaba con "Cannot navigate to invalid URL". Se añadió
`e2e/conftest.py`: usa `--base-url` si se indica (CI) y, si no, inicia uvicorn con `MODEL_PROVIDER=fake`, clave ficticia y sin
variables `CF_*` ni `LANGSMITH_*`. Resultado: `evidence/e2e-fake-20261120.txt`, 7 aprobadas (el archivo contiene 7 pruebas, no 8).

### Precios contradictorios y criterio para la comparación (20-nov-2026)
Para Gemma, la entrada cuesta 0,05 USD por millón según el catálogo de la cuenta y 0,10 según la página oficial y la ficha del
modelo. Son dos fuentes contradictorias y ninguna es una tarifa facturada confirmada. Por tanto, el costo calculado es una
**estimación**, no un cobro. Criterio único: `data/model_prices.json` es la única tabla y se aplica sin cambios a baseline y
optimized (resultados con 0,05/0,30; reserva de presupuesto con 0,10/0,30). Los ahorros que se informen son relativos entre
variantes y dependen de ese supuesto; el cobro real se verifica en el panel de Cloudflare.

### Script de validación de Q09 (`scripts/run-q09.ps1`)
Una llamada como máximo, sin reintentos, solo Q09 optimized, presupuesto estimado de 0,001 USD. `MODEL_SMALL` = Gemma y
`MODEL_LARGE` = 70B. Valida sin mostrar valores `CF_ACCOUNT_ID` y `CF_API_TOKEN`; `CF_GATEWAY_ID` usa `default` si falta;
`CF_AIG_TOKEN` es opcional salvo con `-GatewayRequiresAuth`. Parámetros de Gemma tomados del código y de `tests/test_gateway.py`:
`chat_template_kwargs.enable_thinking=false` y `response_format.type=json_object`. `HIDE_INPUTS` y `HIDE_OUTPUTS` quedan en `true`
(también fijados en `scripts/eval_costs.py`); apagar las trazas no sustituye a ocultar el contenido. El entorno se restaura en
`finally`, queda `AGENT_MAX_STEPS=3` para la comparación, y la salida se guarda en `evidence/costs/q09-console-*.txt`, además de
la carpeta `*-real`. `-Plan` muestra el plan sin red (probado). El modo real no se ha ejecutado.

## Q09 real y preparación de la comparación (21-nov-2026)
- **Q09 real aprobada** (`evidence/costs/20261121-003252-real/results.json`, conservada junto a la sonda 2/3 sin modificar): 1 llamada,
  Gemma, 192/25 tokens, 1,71e-05 USD estimados, 1 571 ms, estado 200, respuesta con "Pregúntame por un empleado". Mismos parámetros de
  Gemma que usará la comparación (`enable_thinking=false`, `response_format=json_object`).
- **Comparación (`scripts/run-comparison.ps1`, no ejecutada):** 12 preguntas y criterios originales; baseline con el 70B (`ROUTING=false`,
  `HISTORY_WINDOW=50`); optimized con enrutamiento (`HISTORY_WINDOW=6`): Gemma en 9 preguntas y 70B en Q06, Q07 y Q11. `AGENT_MAX_STEPS=3`,
  máximo 96 llamadas entre ambas, sin reintentos, `HIDE_INPUTS`/`HIDE_OUTPUTS` en `true`, trazas apagadas. Los totales incluyen tokens y
  costo del revisor. Misma tabla de precios para ambas variantes.
- **Plan (sin inferencia):** costo esperado ≈ 0,0109 USD (baseline 0,0080; optimized 0,0029; 72 llamadas esperadas); reserva conservadora
  del peor caso ≈ 0,0755 USD (baseline 0,0535; optimized 0,0220) con 1 500 tokens de entrada y 300 de salida por llamada y el margen de 0,10
  para Gemma; presupuesto propuesto 0,08 USD. El esperado supone 300 tokens de entrada y 60 de salida por llamada: es un supuesto, no una
  medida. Son estimaciones, no cobros.
- **Resultados parciales:** si se alcanza un tope o falla una llamada, `results.json` conserva las filas obtenidas con `"complete": false` y
  el motivo; el código de salida es 1. Cada ejecución usa una carpeta nueva.
- **Pendiente:** resultados de la comparación, ahorro real, calidad y latencia por variante. Hasta entonces no hay ahorro verificado.

## Comparación parcial del 21-nov-2026
Detenida en optimized/Q05 con un 502 de 30,03 s (hipótesis: tiempo de espera agotado; no confirmada). Los totales de
`costs/20261121-004715-real/` no son comparables (12 frente a 4 preguntas) y no se presentan como ahorro. Análisis,
fallas de protocolo del baseline y plan de continuación: `evidence/comparacion-parcial-20261121.md`. Pendiente: optimized Q05–Q12.

## Resultado de la comparación consolidada (21-nov-2026)
Completada con la continuación `20261121-010610-real` (20 llamadas, 6 de 8 aprobadas, 1 falla de protocolo). Consolidación, cifras exactas,
condiciones (optimized en dos ejecuciones, espera 30→60 s, intento fallido de Q05 con consumo desconocido) y preguntas fallidas:
`evidence/resultado-comparacion-E06.md`. Costos estimados, no factura; sin ahorro garantizado.
