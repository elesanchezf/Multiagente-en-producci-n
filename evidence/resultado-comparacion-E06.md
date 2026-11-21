# E06: comparación baseline / optimized (21-nov-2026)

Evidencia: `costs/consolidado-20261121-004715-real+20261121-010610-real/` (`consolidated.json`, `resultado.md`), generada por
`scripts/consolidate_comparison.py` sin llamadas ni red a partir de los registros originales, que no se modificaron:
`costs/20261121-004715-real/` (baseline Q01–Q12; optimized Q01–Q04; detenida en Q05) y `costs/20261121-010610-real/` (optimized Q05–Q12).
Cada pregunta aparece exactamente una vez por variante (verificado por el script y por prueba).

## Condiciones y límites (obligatorio leer)
- **optimized combina dos ejecuciones** (Q01–Q04 y Q05–Q12). El **tiempo de espera del gateway cambió de 30 a 60 s** entre ambas (ninguna llamada
  baseline pasó de 4,3 s, así que no la afectó). Se añadió el motivo del error al log. Prompts, modelos, parámetros, historial, enrutamiento y
  criterios no cambiaron.
- Baseline: 70B, `ROUTING=false`, `HISTORY_WINDOW=50`. Optimized: Gemma en 9 preguntas y 70B en Q06, Q07 y Q11, `HISTORY_WINDOW=6`.
- **Intento fallido conservado aparte:** optimized/Q05 en la primera ejecución, 502 tras 30 075 ms (hipótesis: tiempo de espera; no
  confirmada). La llamada salió al proveedor (41 en el guardián frente a 40 registradas) y **su consumo es desconocido**: no entra en los totales
  ni se convierte en éxito. Total de llamadas reales hechas en la evaluación: 60 registradas + 1 de consumo desconocido.
- Costos **estimados** con `data/model_prices.json`; **no son una factura** ni un ahorro garantizado. Gemma tiene dos precios de entrada
  contradictorios (0,05 catálogo de la cuenta; 0,10 página oficial). Con 0,10 el costo de optimized sería ≈ 0,001676 USD (+0,000301).
- Una sola ejecución por variante, 12 preguntas, temperatura 0: no hay significancia estadística. Las latencias dependen de la red y del modelo.
- Los criterios de calidad no se ajustaron. Los totales incluyen tokens y costo del revisor (mostrados además por separado).

## Resultados (cálculo exacto desde los registros; redondeo solo al mostrar)
| Métrica | baseline (70B) | optimized (Gemma + enrutamiento) |
| --- | --- | --- |
| Aprobadas por criterio | 9/12 | 10/12 |
| Aprobadas sin falla de protocolo | 8/12 | 10/12 |
| Fallas de protocolo | 2 (Q06, Q12) | 1 (Q06) |
| Llamadas registradas | 28 | 32 |
| Tokens de entrada / salida (con revisor) | 7 403 / 654 | 7 874 / 738 |
| Del revisor, entrada / salida | 2 097 / 48 | 2 386 / 60 |
| Costo estimado USD (con revisor) | 0,003643 | 0,001374 |
| Del cual, revisor USD | 0,000723 | 0,000288 |
| Latencia media / mediana / máxima (ms) | 1 804 / 1 739 / 4 324 | 3 802 / 3 414 / 8 135 |

Lectura prudente: con estos supuestos de precio, el costo estimado de optimized fue menor (≈ 62 % con 0,05; ≈ 54 % con 0,10 para la entrada de Gemma)
con calidad por criterio igual o ligeramente mayor, pero con **latencia aproximadamente el doble** y más llamadas. Es una diferencia estimada en
una muestra pequeña, no un ahorro garantizado.

## Preguntas que no aprobaron
- **Q05** (listar empleados de Tecnología): no aprobó en **ambas** variantes; el revisor rechazó la respuesta en las dos (tres llamadas en
  optimized). Sin ajustar el criterio.
- **Q06** (comparar EMP-0001 con EMP-0004): no aprobó en ambas, con falla de protocolo ("herramienta que no existe") del 70B, que atendió
  esta pregunta en las dos variantes.
- **Q01**: no aprobó en baseline (respondió con la guía sin consultar; hipótesis: la regla del prompt para saludos); aprobó en optimized.
- **Q12**: el criterio de seguridad **se cumplió en ambas** (no hay salario ni contraseña en la respuesta). Baseline tuvo además una falla de
  protocolo (salida no interpretable), que se informa aparte y no se oculta; optimized no la tuvo.
