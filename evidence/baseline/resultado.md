# Verificación inicial del 19 de noviembre de 2026

Base: copia de sesion04/product, sin modificar el código de aplicación.
Entorno utilizado: Python 3.12.16 del entorno compartido de Modulo4.

- Pylint app tests --max-line-length=88: código 0, 10.00/10. Ver pylint.txt.
- Pytest tests --cov=app --cov-fail-under=80: 126 pruebas recolectadas;
  seis completadas y bloqueo en las pruebas de API. Ejecución interrumpida.
  No hay resultado aprobado ni cobertura final de esta corrida. Ver pytest.txt.
- Diagnóstico aislando plugins, con pytest_bdd cargado explícitamente:
  el bloqueo persiste al iniciar el portal de AnyIO desde Starlette TestClient.
  Se guardó el volcado de hilos en api-diagnostic.txt y se interrumpió el proceso.
  La causa raíz aún no está confirmada; no se atribuye al código del producto.
- No se han ejecutado E2E, proveedor real, LangSmith, concurrencia ni Docker Scout
  para esta copia. Las evidencias históricas no sustituyen esas verificaciones.

## Continuación con entorno independiente

Se creó .venv con Python 3.12.16, se instalaron las dependencias y se permitió
la red necesaria para conexiones locales. No se modificó el código de aplicación.
Pytest terminó con código 0: 126 pruebas pasadas en 7,75 segundos,
cobertura 96,61 %. Evidencia: pytest-isolated.txt.
Pylint del entorno independiente terminó con código 0 y 10.00/10;
ver pylint-isolated.txt.
Se conserva el diagnóstico previo; como cambiaron el entorno y los permisos,
no se atribuye el bloqueo a una sola causa demostrada.
requirements.lock.txt registra las versiones instaladas para reproducir el entorno.
scripts/verify-local.ps1 conserva nuevas ejecuciones en evidence/runs/.
