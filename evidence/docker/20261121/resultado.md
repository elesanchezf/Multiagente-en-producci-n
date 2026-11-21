# Resultado Docker (21-nov-2026)

Entorno: Docker Engine 29.9.3 (Docker Desktop), linux/amd64, Docker Scout CLI 1.28.0. Datos ficticios; proveedor `fake`. No se publicó nada.

## Etiquetas oficiales de Python (`python-tags.txt`, consulta del 21-nov)
| Etiqueta | Versión | Digest del índice | Creación (amd64) |
| --- | --- | --- | --- |
| `python:3.12-slim` = `3.12-slim-trixie` | 3.12.16-slim-trixie | `sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b` | 2026-11-05T07:52:11Z |
| `python:3.13-slim` | 3.13.18-slim-trixie | `sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90` | 2026-11-05T07:51:48Z |
| `python:3.14-slim` | 3.14.10-slim-trixie | `sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f` | 2026-11-05T07:51:43Z |

El índice de 3.12-slim no cambió desde el 19-nov: la base candidata sigue siendo la fijada en el `Dockerfile`. No hay una base más reciente.

## Correcciones disponibles (`debian-apt-policy.txt`)
En la base fijada, tras `apt-get update`: `openssl` y `libssl3t64` instalados 3.5.7-1~deb13u3; versión candidata en los repositorios de trixie: la misma. **No hay en Debian trixie una versión corregida de OpenSSL.** zlib se corrige con la actualización puntual del `Dockerfile` (`1:1.3.dfsg+really1.3.1-1+deb13u1`).

## Imagen final
- Nombre local: `multiagente-reto:final`. **ID local de imagen:** `sha256:e79f499166bc63beeb90527b7fba1eb318bc759f4a0cbb97c2eb0951c72ada99` (código final del 21-nov; `image-inspect.txt`). Usuario `appuser` (UID 10001), Python 3.12.16.
- **No es un digest de registro:** la imagen no se ha publicado en ningún registro. Docker Desktop muestra `RepoDigests` con el mismo hash local; no identifica nada en un registro. El digest de registro solo existirá tras publicarla (p. ej. en Render o en un registro), y el escaneo definitivo deberá repetirse por ese digest.
- Build: código 0 (`build.txt`).

## Escaneos Docker Scout (filtro crítica y alta, linux/amd64)
| Objeto | Críticas | Altas | Detalle |
| --- | --- | --- | --- |
| Base candidata `python@sha256:5e2bdb1b…4fa5b` (`scout-base.txt`, código de salida 2) | 0 | 5 | openssl 3.5.7-1~deb13u3: CVE-2026-107493, CVE-2026-84786, CVE-2026-107496 (sin corrección); zlib 1:1.3.dfsg+really1.3.1-1: CVE-2026-85091 y CVE-2026-76844 (corrección deb13u1) |
| Imagen final `multiagente-reto:final` (`scout-final.txt`, código de salida 2) | 0 | **3** | openssl 3.5.7-1~deb13u3: CVE-2026-107493, CVE-2026-84786, CVE-2026-107496, «not fixed» |

Cambio frente al 19-nov (seis altas de OpenSSL: CVE-2026-95691, -107493, -95692, -88823, -124709, -107496): ya no aparecen cuatro de ellas y aparece CVE-2026-84786. El paquete instalado es el mismo; el cambio proviene de los datos de vulnerabilidades de Scout, no de la imagen. Hipótesis no verificada: reclasificación o actualización de datos de Debian. Siguen **tres altas sin corrección**, no cero.

## Prueba de humo (`smoke.txt`, contenedor local, `fake`, clave ficticia)
`/health` 200; `/ask` sin clave 401; `/ask` con clave 200 con coordinador, directorio y revisor (`approved`); `/docs` (Swagger) 200; proceso con UID 10001 (no root); la clave aparece 0 veces en el log y el texto de la pregunta 0 veces. Valida la imagen local, no Render ni el proveedor real.

## Fuentes oficiales de Debian (`debian-tracker-extract.txt`)
Consultadas el 21-nov: `security-tracker.debian.org/tracker/<CVE>`. Las tres figuran para trixie (3.5.7-1~deb13u3) como **vulnerable** y para unstable como **unfixed**. Resumen y límites en `doc/image-vulnerabilities.md`.
