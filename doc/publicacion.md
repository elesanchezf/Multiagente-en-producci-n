# Estrategia y comandos de publicación (preparados; no se ha hecho push ni despliegue)

## Estado local verificado el 21-nov-2026
- Repositorio de entrega `elesanchezf/Multiagente-en-producci-n`: privado, **vacío** (sin ramas), permiso de administración.
- Identidad de Git de este repositorio (configuración local): `elesanchezf` con el correo de GitHub tipo `<id>+elesanchezf@users.noreply.github.com`. La configuración global contiene un correo personal que **no** se usa aquí.
- Rama `main` (local): un único commit inicial nuevo, **sin importar los tres commits históricos**. Contiene los 78 archivos de la base de la sesión 4. Su identificador de árbol de Git (`c24e1b2e70e9…`) es idéntico al del commit `6083236` de `hr-assistant`, lo que prueba el mismo contenido.
- Rama `reto/produccion` (local): parte de ese commit y añade la contribución del reto en commits por tema. El PR hacia `main` muestra solo esa contribución.
- Se conservan en el disco todos los archivos de trabajo y evidencias; los originales con datos personales están en `.gitignore` y se publican sus copias `.anonimizado`.

## Comandos (ejecutar en este orden, desde la raíz del proyecto)
1. Revisar qué se publicaría: `git log --oneline --all`, `git diff --stat main..reto/produccion`, `git ls-tree -r --name-only reto/produccion`.
2. Búsqueda de secretos antes de publicar (no debe imprimir resultados): `git grep -IlE "cfut_|lsv2_(pt|sk)_|ghp_|github_pat_|PRIVATE KEY" reto/produccion -- . ":!app/privacy.py"`.
3. Publicar `main` (crea la rama predeterminada del repositorio vacío): `git push -u origin main`.
4. Publicar la rama de trabajo: `git push -u origin reto/produccion`.
5. Abrir el PR: `gh pr create --base main --head reto/produccion --title "<título de doc/entrega/…>" --body-file doc/pr-descripcion.md`.
6. Comprobar el CI en la pestaña Actions del PR (style, unit, e2e, docker); opcional: `gh pr checks`.
7. Etiqueta opcional `Share-OK`: solo si la persona participante lo decide.

Orden y razón: el PR necesita que `main` exista y comparta historia con la rama; por eso `main` se publica primero.

## Qué se publicaría
Ver `doc/publicacion-resumen.md` (lista de archivos por categoría y exclusiones).

## Exclusión de secretos (verificada)
`.gitignore` excluye `.env` y variantes (menos `.env.example`), entornos virtuales, cachés, `*.pid` y los originales con datos personales. Búsqueda sobre los archivos a publicar: sin tokens, claves ni identificadores de cuenta; el único acierto, `app/privacy.py`, son los patrones del detector de datos sensibles. Los UUID restantes son `request_id` aleatorios.
