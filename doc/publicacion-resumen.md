# Qué se publicaría (resumen verificado el 21-nov-2026)

Repositorio destino: `elesanchezf/Multiagente-en-producci-n` (privado, hoy vacío). Nada se ha publicado.

## Ramas y commits (autoría con el correo de GitHub tipo noreply; ningún correo personal en los commits)
| Rama | Contenido |
| --- | --- |
| `main` | 1 commit inicial nuevo: base de la sesión 4 (78 archivos; árbol idéntico a `hr-assistant@6083236`, sin importar su historial) |
| `reto/produccion` | 6 commits sobre `main`: multiagente y privacidad; costos y evaluación; contenedor, CI y Render; documentación y evidencias; resumen de publicación; capturas pendientes y PDF |

El PR `reto/produccion` → `main` muestra 165 archivos: 138 añadidos y 27 modificados (14 551 inserciones, 71 eliminaciones).

## Por directorio (archivos en el PR)
app 10 · tests 19 · e2e 2 · scripts 13 · doc 16 · evidence 94 · data 2 · más Dockerfile, `.dockerignore`, `.env.example`, `.gitignore`, `.pylintrc`, `render.yaml`, `requirements.lock.txt`, `README.md` y `.github/workflows/ci.yml`.

## Los archivos de mayor tamaño
`doc/entrega/…docx` (3,4 MB), `doc/entrega/…pdf` (0,3 MB, exportado desde Word) y `evidence/load/server.log` (0,45 MB).

## No se publica (solo local)
`.env` y variantes, `.venv`, `.uv-cache`, `.playwright`, cachés, `*.pid`, y los originales con rutas personales o identificadores de cuenta: `evidence/baseline/{api-diagnostic,pytest-isolated,pytest}.txt`, `evidence/e2e-fake-20261120.txt`, `evidence/multiagent-{e2e,tests}.txt` y `evidence/langsmith-check/workspaces-20261119-223325.json`. En su lugar se publican las copias `*.anonimizado.*`, marcadas como anonimizadas.

## Qué decisión de seguridad falta
Las 3 altas de OpenSSL sin corrección (CVE-2026-107493, CVE-2026-84786 y CVE-2026-107496) siguen abiertas: riesgo **no aceptado** y **sin VEX**. Ver `doc/openssl-aplicabilidad.md`.
