# Verificación de la imagen base y vulnerabilidades

## Estado actual (21-nov-2026)

Fuente: `evidence/docker/20261121/` (`resultado.md`, `scout-base.txt`, `scout-final.txt`, `smoke.txt`).

- La afirmación heredada de "0 altas" (14-nov-2026, más abajo) **ya no describe el estado actual**.
- Base candidata `python:3.12.16-slim-trixie` (índice `sha256:5e2bdb1b…4fa5b`, sin cambios desde el 19-nov): Docker Scout, linux/amd64, 21-nov: 0 críticas y 5 altas (3 de openssl sin corrección y 2 de zlib corregibles).
- Imagen final `multiagente-reto:final` (ID local `sha256:e79f4991…2ada99`; no es un digest de registro): 0 críticas y **3 altas**, todas de `openssl 3.5.7-1~deb13u3`: CVE-2026-107493, CVE-2026-84786 y CVE-2026-107496, «not fixed».
- Escaneos anteriores: 14-nov (0 altas en la imagen final, ver historial); 19-nov (6 altas de openssl, `evidence/docker/scout-final.txt`).
- Riesgo: **aceptado temporalmente** por Eleazar Sánchez Figueroa solo para desplegar la demo académica `multiagente-reto` con datos ficticios; fecha de revisión **27-nov-2026** (ver `openssl-aplicabilidad.md`). Las vulnerabilidades **no están corregidas** y no se demostró que no afecten a la aplicación; **sin declaración VEX**.

### Las tres altas actuales (Debian Security Tracker, consultado el 21-nov-2026)
Para trixie (3.5.7-1~deb13u3) y unstable: estado «vulnerable / unfixed»; no existe versión corregida en Debian.

| CVE | Qué afecta (según el aviso) | Condición de explotación (según el aviso) | Mitigación indicada |
| --- | --- | --- | --- |
| CVE-2026-107493 | Uso de memoria liberada en `PEM_X509_INFO_read_bio_ex()` (y variantes) si falla la lectura | Solo aplicaciones que pasan una pila ya existente; OpenSSL y su código TLS pasan NULL; el atacante no puede hacer que la aplicación lo haga | Evitar esa llamada con pila existente; esperar corrección (aviso upstream 20261117) |
| CVE-2026-84786 | Cliente TLS con DANE puede caer por puntero nulo con una combinación inusual de certificado y registros TLSA | Cliente con DANE habilitado | No habilitar DANE; esperar corrección |
| CVE-2026-107496 | `CMS_encrypt()` puede entrar en bucle infinito con un certificado EC de orden de grupo 1 | La aplicación cifra con CMS a un certificado controlado por el atacante; TLS y QUIC no usan esa ruta (aviso upstream 20261110) | No cifrar CMS a certificados no confiables; esperar corrección |

Aplicabilidad al HR Assistant: **no verificada**. Los avisos describen API concretas, pero no se ha comprobado que el intérprete de Python de la imagen o nuestras dependencias no las usen. Por eso no se declara «no afectado». El servicio hace conexiones TLS salientes (Cloudflare, LangSmith) con la OpenSSL del sistema. No expone TLS propio (Render lo termina).

### Qué falta para decidir
1. Repetir el escaneo sobre el digest de registro de la imagen publicada.
2. Confirmar la aplicabilidad (uso de esas API por Python/httpx/dependencias) con evidencia, si se quiere argumentar no explotabilidad.
3. Decisión de la persona: aceptar con justificación y fecha de revisión, cambiar de base cuando exista una corregida, o emitir VEX con evidencia. Opciones técnicas: esperar una actualización de Debian (comprobar a diario con `apt-cache policy openssl` y Scout); 3.13 no mejora (misma openssl y más altas, 19-nov).

## Historial heredado (14-nov-2026; no es el estado actual)

## Estado (14-nov-2026; histórico)

- Identificación de la imagen base: VERIFICADA el 2026-11-14 (índice sin cambios, reconsultado hoy con `docker buildx imagetools inspect`): `python:3.12-slim`, índice `sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b`.
- Decisión de la persona: eligió la opción (b) el 2026-11-14 y autorizó al agente `deploy` a modificar `product/Dockerfile`.
- `product/Dockerfile`: MODIFICADO el 2026-11-14 (ver «Cambio aplicado»).
- Imagen escaneada: `hr-assistant:revision`, `linux/amd64`, reconstruida después de agregar el soporte de `CF_AIG_TOKEN` (cabecera `cf-aig-authorization`) y el registro de `status_code`. Construcción COMPLETADA, código de salida 0. Digest del índice (manifest list) local: `sha256:80b2ccecd310e8db035c33a7f9b9b81f5e3fc5f42256642548999e4671d63f72` (Scout lo muestra como `80b2ccecd310`). Es un digest local, no de registro.
- Versión de `zlib1g` instalada en la imagen final: `1:1.3.dfsg+really1.3.1-1+deb13u1`, que es la versión corregida.
- Escaneo de la imagen final: COMPLETADO. Con filtro crítica y alta, Docker Scout no detecta paquetes vulnerables (0 críticas y 0 altas). CVE-2026-85091 y CVE-2026-76844 no aparecen.
- Prueba de humo local con el contenedor: COMPLETADA con resultado satisfactorio (valida la imagen en local; no valida Render ni el proveedor gateway).
- Verificaciones locales del código de esta versión: pasan (pylint 10.00/10; 126 pruebas, cobertura 96,61 %).
- Repositorio privado `elesanchezf/hr-assistant`: EXISTE (primer commit `90f5962`, cuyo trabajo `style` de pylint falló en el CI). El commit con `CF_AIG_TOKEN` se está publicando en ese repositorio.
- Resultado del CI sobre el commit con `CF_AIG_TOKEN`: PENDIENTE.
- Despliegue en Render de ese commit: PENDIENTE.
- Carga de `CF_AIG_TOKEN` en Render: PENDIENTE.
- Prueba de `/ask` con el gateway real: PENDIENTE.
- Los cuatro puntos anteriores los verifica la persona o el orquestador después.
- Arquitectura de despliegue en Render: SIN CONFIRMAR. Se asume `linux/amd64`; la persona debe confirmarlo en su servicio.
- Advertencia `JSONArgsRecommended`: ABIERTA.
- Publicación: PENDIENTE de la aprobación de la persona y de los puntos anteriores (ver «Criterio de cierre»).

## Evidencia verificada de la imagen base (2026-11-14)

La consulta la realizó el orquestador con `docker buildx imagetools inspect python:3.12-slim`, que consulta el registro. Versión de Docker CLI: 29.9.3. Los datos se copian tal cual de esa salida.

| Dato | Valor |
| --- | --- |
| Tag de versión menor consultado | `python:3.12-slim` |
| Versión de parche (anotación `org.opencontainers.image.version`) | `3.12.16-slim-trixie` |
| Imagen base | `debian:trixie-slim` |
| Digest del índice multiarquitectura de `python:3.12-slim` | `sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b` |
| Digest del manifiesto `linux/amd64` | `sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177` |
| Fecha de creación de la imagen `linux/amd64` | 2026-11-05T07:52:11Z |
| Fecha de la consulta | 2026-11-14 (reconsultado el mismo día; el índice no cambió) |
| Arquitectura de despliegue | Se asume `linux/amd64` para Render. Es un supuesto que la persona debe confirmar en su servicio. |

Un tag es mutable: `python:3.12-slim` puede apuntar a otro digest en el futuro. Los digests anteriores identifican la imagen consultada hoy. No hay reconstrucción posterior a la creación del 2026-11-05.

## Escaneo de la imagen base

Procedencia: la persona aportó primero la salida de Docker Scout (resumen quickview). El orquestador reprodujo después la parte de severidades crítica y alta. Los datos se copian tal cual, sin cifras ni identificadores añadidos.

| Dato | Valor |
| --- | --- |
| Fecha | 2026-11-14 |
| Herramienta | Docker Scout v1.28.0 |
| Imagen analizada | Imagen base de Python, plataforma `linux/amd64`, digest `sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177` (`python:3.12-slim`, versión `3.12.16-slim-trixie`) |
| Paquetes indexados (evidencia de la persona) | 127 |
| Vulnerabilidades, quickview (evidencia de la persona) | 0 críticas, 2 altas, 6 medias, 28 bajas y 5 sin severidad conocida |
| Políticas (evidencia de la persona) | Cumplió 3 de 7 |
| Reproducción del orquestador | `docker scout cves --only-severity critical,high` confirma 0 críticas y 2 altas |

Hallazgos altos de la imagen base: CVE-2026-85091 y CVE-2026-76844. Ambos afectan al paquete zlib, versión `1:1.3.dfsg+really1.3.1-1`, con rango afectado menor que `1:1.3.dfsg+really1.3.1-1+deb13u1`. Versión corregida: `1:1.3.dfsg+really1.3.1-1+deb13u1`.

## Búsqueda de una imagen con la corrección (2026-11-14)

Resultados obtenidos por el orquestador con Docker Scout v1.28.0 (plataforma `linux/amd64`) y `docker buildx imagetools inspect`. Se copian tal cual.

| Candidata | Versión y base | Creación | Índice | Manifiesto `linux/amd64` | Resultado de Scout | Veredicto |
| --- | --- | --- | --- | --- | --- | --- |
| `python:3.12-slim` (referencia) | `3.12.16-slim-trixie`, `debian:trixie-slim` | 2026-11-05T07:52:11Z | `sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b` | `sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177` | 0 críticas y 2 altas (CVE-2026-85091 y CVE-2026-76844 en zlib) | Sin la corrección |
| `python:3.12-slim-bookworm` | `3.12.16-slim-bookworm`, `debian:bookworm-slim` | 2026-11-05T07:52:18Z | `sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df` | `sha256:0f086103b026048cc50cb5da25ec435c023c5241a83fc44daea593377abc61c4` | 156 paquetes, 0 críticas, 16 altas, 23 medias, 52 bajas, 11 sin severidad; 4 de 7 políticas | DESCARTADA |
| `python:3.12-alpine` | `3.12.16-alpine3.24`, `alpine:3.24` | 2026-11-05T19:25:47Z | `sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89` | `sha256:a61cbd76a882645de7f91423329fe43a67eed60d7da24f9e5331414bb3618b20` | 52 paquetes, 1 crítica, 9 altas, 13 medias, 1 baja, 11 sin severidad; 3 de 7 políticas; «Fixable critical or high vulnerabilities found: 1C 8H» | DESCARTADA |

Detalle de `python:3.12-slim-bookworm`: las mismas CVE-2026-85091 y CVE-2026-76844 afectan a zlib `1:1.2.13.dfsg-1` con «Fixed version: not fixed». Otras altas, todas sin corrección: krb5 (6), util-linux (3), sqlite3 (3), glibc (1), perl (1). Motivo del descarte: no incluye la corrección y tiene más altas.

Detalle de `python:3.12-alpine`: motivo del descarte: peor perfil y cambia de libc (musl), lo que exigiría validar la aplicación.

No evaluado: `python:3.12` (no slim), por no ser el alcance pedido; ni otras versiones de Python (3.13 o 3.14), por no ser compatibles con 3.12.

### Conclusión

Ninguna imagen oficial de Python 3.12 evaluada incluye la corrección de zlib. Todas las etiquetas se construyeron el 2026-11-05. Se esperaba que la corrección llegara con una reconstrucción posterior; esto era una expectativa, no un hecho verificado. Por ello se aplicó la opción (b).

## Decisión de la persona y cambio aplicado (2026-11-14)

La persona eligió la opción (b) y autorizó al agente `deploy` a modificar `product/Dockerfile`. Las opciones (a) y (c) no se aplicaron.

Cambio aplicado en `product/Dockerfile`: un `RUN` que, como root y antes de copiar la aplicación, ejecuta `apt-get update`, `apt-get install --no-install-recommends --only-upgrade -y zlib1g` y limpia `/var/lib/apt/lists/*`.

Se conserva sin cambios:

- `FROM python:3.12-slim`, sin digest.
- El usuario sin privilegios.
- El `CMD`.

Resultado: la verificación sobre la imagen final (siguiente sección) confirma que el cambio surte efecto: `zlib1g` queda en la versión corregida y las dos CVE desaparecen del escaneo.

## Resultados de la imagen final `hr-assistant:revision` (verificados el 2026-11-14)

Los resultados corresponden a la imagen reconstruida después de agregar el soporte de `CF_AIG_TOKEN` (cabecera `cf-aig-authorization`) y el registro de `status_code`. Se atribuyen únicamente a esta imagen.

| Verificación | Comando o método | Herramienta y versión | Resultado |
| --- | --- | --- | --- |
| Construcción | `docker build --platform linux/amd64 --no-cache --pull -t hr-assistant:revision .` desde `product/` | Docker Engine 29.9.3 | Código de salida 0 |
| Identificación de la imagen | Imagen local `hr-assistant:revision`, plataforma `linux/amd64`, arquitectura `amd64` | Docker | Digest del índice (manifest list) local: `sha256:80b2ccecd310e8db035c33a7f9b9b81f5e3fc5f42256642548999e4671d63f72` (Scout lo muestra como `80b2ccecd310`) |
| Imagen base | `python:3.12-slim`, sin cambio | `docker buildx imagetools inspect` | Índice `sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b` (reconsultado hoy) |
| Versión de zlib1g instalada | `dpkg -s zlib1g` | dpkg en la imagen | `1:1.3.dfsg+really1.3.1-1+deb13u1` (versión corregida) |
| Escaneo completo | `docker scout cves local://hr-assistant:revision --platform linux/amd64` | Docker Scout CLI 1.28.0 | 6 medias, 27 bajas y 5 sin clasificar, en 13 paquetes (38 vulnerabilidades en total) |
| Otras críticas o altas | Escaneo con filtro de severidad `critical,high` | Docker Scout CLI 1.28.0 | Scout informa que no detecta paquetes vulnerables (0 críticas, 0 altas) |
| CVE-2026-85091 | Salida del escaneo anterior | Docker Scout CLI 1.28.0 | No aparece |
| CVE-2026-76844 | Salida del escaneo anterior | Docker Scout CLI 1.28.0 | No aparece |
| Prueba de humo del contenedor | Prueba local con el contenedor, `ENVIRONMENT=development`, `MODEL_PROVIDER=fake`, clave ficticia | Contenedor local | `/health` 200; `/ask` sin clave 401; `/ask` con clave 200 |
| Lint | `pylint app tests --max-line-length=88` | pylint | Código de salida 0, 10.00/10 |
| Pruebas unitarias | `pytest tests --cov=app --cov-fail-under=80` | pytest | 126 pruebas, cobertura 96,61 % |

Notas sobre el alcance de estos resultados:

- El digest anterior es el del índice de la imagen local, no el de un registro. Render construye su propia imagen a partir del Dockerfile, por lo que su digest no tiene por qué coincidir con este.
- Las 6 medias, 27 bajas y 5 sin clasificar no se analizaron una por una; se registran solo como cifras del resumen.
- Imágenes anteriores reemplazadas, a las que no se atribuye este resultado: `sha256:32809aa69764...` (construida tras corregir pylint, antes de `CF_AIG_TOKEN`) y `sha256:293df22db2e0...` (la primera).
- La verificación del usuario sin privilegios (uid 10001) se registró sobre una imagen anterior y no se repitió sobre esta; el Dockerfile conserva el usuario sin privilegios.
- La prueba de humo valida la imagen en local. No valida Render ni el proveedor gateway.

### Advertencia de Docker abierta

`JSONArgsRecommended`: el `CMD` está en formato shell (línea 37 del `Dockerfile`). No bloquea la construcción ni la prueba de humo. Su corrección (formato JSON) no se ha aplicado ni decidido. Estado: abierta.

## Pendientes para cerrar

1. Terminar la publicación del commit con `CF_AIG_TOKEN` en `elesanchezf/hr-assistant` (en curso).
2. Resultado del CI sobre ese commit (PENDIENTE).
3. Confirmación por la persona de la arquitectura `linux/amd64` en su servicio de Render (SIN CONFIRMAR). No hay acceso a la cuenta de Render desde la sesión.
4. Despliegue en Render de ese commit (PENDIENTE).
5. Carga de `CF_AIG_TOKEN` en Render (PENDIENTE), a cargo de la persona, sin registrar el valor en documentos.
6. Prueba de `/ask` con el gateway real (PENDIENTE), que la prueba de humo local no cubre.
7. Decisión sobre la advertencia `JSONArgsRecommended` (opcional; no bloquea).
8. Aprobación de la persona para el cierre y la publicación (`output/approved.txt`). Este documento no registra que exista.

Los puntos 2, 4, 5 y 6 los verifica la persona o el orquestador después.

## Comandos de referencia

Con una sesión propia de Docker (`docker login`), ejecutar y registrar:

```
docker scout cves --platform linux/amd64 --only-severity critical,high docker.io/library/python@sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177
docker scout quickview docker.io/library/python@sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177
docker buildx imagetools inspect python:3.12-slim
docker build --platform linux/amd64 --no-cache --pull -t hr-assistant:revision .
docker scout cves local://hr-assistant:revision --platform linux/amd64
```

Al compartir resultados:

- Incluir fecha de la ejecución y versión de la herramienta (`docker scout version`).
- Sin credenciales, tokens ni datos de la cuenta.
- Usar solo claves y datos ficticios en el arranque y la prueba de humo.
- No pegar el informe en herramientas de IA sin autorización institucional.

## Tabla de hallazgos

| Fecha | Imagen y digest | Identificador | Severidad | Decisión | Resultado | Responsable |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-14 | Imagen base de Python (`python:3.12-slim`, `3.12.16-slim-trixie`), `linux/amd64`, `sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177` | CVE-2026-85091 (zlib `1:1.3.dfsg+really1.3.1-1`; corregida en `1:1.3.dfsg+really1.3.1-1+deb13u1`) | Alta | Opción (b) elegida por la persona: actualizar `zlib1g` en el Dockerfile | CORREGIDA en la imagen local `hr-assistant:revision` (índice local `sha256:80b2ccecd310e8db035c33a7f9b9b81f5e3fc5f42256642548999e4671d63f72`): no aparece en Docker Scout 1.28.0 | Persona que decide; ejecución a cargo de deploy |
| 2026-11-14 | Imagen base de Python (`python:3.12-slim`, `3.12.16-slim-trixie`), `linux/amd64`, `sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177` | CVE-2026-76844 (zlib `1:1.3.dfsg+really1.3.1-1`; corregida en `1:1.3.dfsg+really1.3.1-1+deb13u1`) | Alta | Opción (b) elegida por la persona: actualizar `zlib1g` en el Dockerfile | CORREGIDA en la imagen local `hr-assistant:revision` (índice local `sha256:80b2ccecd310e8db035c33a7f9b9b81f5e3fc5f42256642548999e4671d63f72`): no aparece en Docker Scout 1.28.0 | Persona que decide; ejecución a cargo de deploy |

## Recomendación (no aplicada)

Fijar `product/Dockerfile` al digest del índice multiarquitectura:

```
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
```

El índice conserva la elección de arquitectura y hace reproducible la construcción. Esta recomendación no se ha aplicado: el Dockerfile conserva `FROM python:3.12-slim` sin digest. Su aplicación requiere una decisión adicional de la persona. Al fijar el digest hay que establecer un proceso periódico para actualizarlo.

## Criterio de cierre

- Cumplido: cada hallazgo crítico o alto tiene decisión y responsable (CVE-2026-85091 y CVE-2026-76844, corregidos con la opción (b)).
- Cumplido: escaneo de la imagen final registrado (Docker Scout CLI 1.28.0, 2026-11-14), con la versión de `zlib1g` instalada y la comprobación específica de ambas CVE, sobre la imagen reconstruida con `CF_AIG_TOKEN`.
- Cumplido: prueba de humo local registrada con clave ficticia.
- Pendiente: la persona confirma que la arquitectura de despliegue en Render es `linux/amd64`.
- Pendiente: CI en verde sobre el commit con `CF_AIG_TOKEN`, despliegue de ese commit en Render, carga de `CF_AIG_TOKEN` en Render y prueba de `/ask` con el gateway real.
- Pendiente: si se fija el digest, actualizar `product/Dockerfile` y registrar el cambio.
- Pendiente: una persona aprueba el cierre antes de publicar (`output/approved.txt`).
