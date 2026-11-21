# Resultado Docker (19 de noviembre de 2026)

Entorno: Docker Engine 29.9.3, linux/amd64. Datos ficticios; proveedor `fake`.

## Base verificada
- Tag exacto: `python:3.12.16-slim-trixie` (coincide con `python:3.12-slim`; Python 3.12.16).
- Digest (índice): `sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b`.
- Docker Scout (`scout-base.txt`, código 0): 8 vulnerabilidades altas, 0 críticas.
  zlib 1:1.3.dfsg+really1.3.1-1 (2: CVE-2026-85091, CVE-2026-76844; corrección 1:1.3.dfsg+really1.3.1-1+deb13u1)
  y openssl 3.5.7-1~deb13u3 (6; sin versión corregida).

## Cambios al Dockerfile
- `FROM` fijado por el digest anterior.
- Dependencias desde `requirements.lock.txt` (antes `requirements.txt` con rangos abiertos y herramientas
  de prueba): versiones reproducibles. `colorama` del lock es inocua en Linux.
- `CMD` en formato JSON con `exec` (señales correctas; resuelve la advertencia de build).
- `tests/test_delivery_files.py`: ahora exige `FROM` por digest y uso del lock (aserción más estricta).
- Se conserva la actualización puntual de zlib.

## Imagen `multiagente-reto:revision`
- Build: código 0 (`build.txt`). ID local `sha256:c96d12d2b1ce755221f00fb01f7de3767ca2068a4da0da597ae8c93f86040095`;
  usuario `appuser` (uid 10001). Sin digest de registro: la imagen no se ha publicado.
- Scout final (`scout-final.txt`, código 0): 0 críticas, 6 altas, todas de openssl 3.5.7-1~deb13u3,
  "not fixed". zlib quedó corregido por la actualización puntual.
- Dependencias en Linux: 155 pruebas aprobadas dentro del contenedor (`linux-tests.txt`, código 0),
  con `tests/`, `.github/` y `.dockerignore` montados solo lectura (la imagen no los incluye).
  En Windows: 155 aprobadas y Pylint 10.00/10.
- Humo (`smoke.txt`): `/health` 200; `/ask` sin clave 401; `/ask` con clave 200, revisión aprobada.
  Proceso como `appuser`; la clave no aparece en el log; el log no contiene el texto de la pregunta
  (solo `question_chars`).

## Pendientes
- Las 6 altas de OpenSSL no tienen corrección disponible en la base: requieren decisión de riesgo o
  esperar una imagen base actualizada. No se aceptan ni se ocultan (sin VEX). Repetir el escaneo antes de entregar.
- Sin publicación, despliegue en Render, ni Linux arm64. El digest de la base puede cambiar con el tiempo.
