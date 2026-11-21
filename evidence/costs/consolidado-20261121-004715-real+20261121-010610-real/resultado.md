# Comparación consolidada (scripts/consolidate_comparison.py)

- optimized combina dos ejecuciones: Q01-Q04 de la primera y Q05-Q12 de la continuación.
- El tiempo de espera del gateway cambió de 30 a 60 s entre ambas.
- Costos estimados con data/model_prices.json; no son factura.
- Los intentos fallidos no entran en los totales; su consumo es desconocido.

| Métrica | baseline (70B) | optimized (Gemma + enrutamiento) |
| --- | --- | --- |
| Preguntas | 12 | 12 |
| Aprobadas por criterio | 9 | 10 |
| Aprobadas sin falla de protocolo | 8 | 10 |
| Fallas de protocolo | 2 | 1 |
| Llamadas registradas | 28 | 32 |
| Tokens de entrada (con revisor) | 7403 | 7874 |
| Tokens de salida (con revisor) | 654 | 738 |
|   de ellos, entrada del revisor | 2097 | 2386 |
|   de ellos, salida del revisor | 48 | 60 |
| Costo estimado USD (con revisor) | 0.003643 | 0.001374 |
|   del cual, revisor USD | 0.000723 | 0.000288 |
| Latencia media ms | 1804 | 3802 |
| Latencia mediana ms | 1739 | 3414 |
| Latencia máxima ms | 4324 | 8135 |

| Pregunta | baseline | optimized | modelo optimized |
| --- | --- | --- | --- |
| Q01 | NO aprobó | aprobó | gemma-4-26b-a4b-it |
| Q02 | aprobó | aprobó | gemma-4-26b-a4b-it |
| Q03 | aprobó | aprobó | gemma-4-26b-a4b-it |
| Q04 | aprobó | aprobó | gemma-4-26b-a4b-it |
| Q05 | NO aprobó | NO aprobó | gemma-4-26b-a4b-it |
| Q06 | NO aprobó (falla de protocolo) | NO aprobó (falla de protocolo) | llama-3.3-70b-instruct-fp8-fast |
| Q07 | aprobó | aprobó | llama-3.3-70b-instruct-fp8-fast |
| Q08 | aprobó | aprobó | gemma-4-26b-a4b-it |
| Q09 | aprobó | aprobó | gemma-4-26b-a4b-it |
| Q10 | aprobó | aprobó | gemma-4-26b-a4b-it |
| Q11 | aprobó | aprobó | llama-3.3-70b-instruct-fp8-fast |
| Q12 | aprobó (falla de protocolo) | aprobó | gemma-4-26b-a4b-it |

Intento excluido: optimized/Q05 de 20261121-004715-real, estado 502, 30075.3 ms; consumo desconocido.
