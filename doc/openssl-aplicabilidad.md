# Aplicabilidad de las tres CVE de OpenSSL al HR Assistant (21-nov-2026)

Revisión informativa. **No es una declaración VEX ni una aceptación de riesgo**: ninguna prueba aquí demuestra que el producto "no esté afectado".
Evidencia: `evidence/docker/20261121/openssl-aplicabilidad.txt`, `debian-tracker-extract.txt`, `scout-final.txt`. Paquete: `openssl 3.5.7-1~deb13u3` (Debian trixie), sin versión corregida.

## Vocabulario
- **No se encontró uso:** se buscó y no apareció; depende del alcance de la búsqueda.
- **No afectado demostrado:** habría que probar que la condición de explotación es imposible. No se alcanzó para ninguna CVE.

## Qué se revisó
1. **Código propio (`app/`):** sin `import ssl`, `SSLContext`, `subprocess` ni `os.system`; no hay manejo de certificados ni cifrado CMS. Las conexiones TLS salen por `httpx`/`langsmith` hacia Cloudflare y LangSmith, con las raíces de confianza por omisión.
2. **Dependencias Python (`requirements.lock.txt`):** no hay `cryptography` ni `pyOpenSSL` (no traen OpenSSL propio). `truststore` y `certifi` son paquetes de raíces de confianza (su código no se revisó línea por línea). El intérprete usa la OpenSSL del sistema (`ssl.OPENSSL_VERSION` = 3.5.7, `_ssl` y `_hashlib` enlazados con ella).
3. **Binarios de la imagen:** búsqueda binaria de `PEM_X509_INFO_read*`, `CMS_encrypt`, `SSL_CTX_dane_enable`, `SSL_dane_enable` y `SSL_dane_tlsa_add` en `/usr`, `/app` y `/opt`, excluyendo `libcrypto` y `libssl`. Aparecen solo en `/usr/bin/openssl` (herramienta de línea de comandos) y en `playwright/driver/node` (Node con OpenSSL propio, no la de Debian). **No aparecen** en `_ssl`, `_hashlib` ni en otras extensiones nativas de Python.
4. **Avisos de Debian y de OpenSSL** (condiciones de explotación; ver más abajo).
5. **Experimento de mitigación:** quitar `/usr/bin/openssl` (`apt-get purge openssl`) en un contenedor temporal mantiene `libssl3t64` y Scout informa **las mismas 3 altas**. No sirve para limpiar el escaneo; la imagen de prueba se eliminó.

## Por CVE
| CVE | Condición de explotación (según el aviso) | Resultado de la revisión | Incertidumbre |
| --- | --- | --- | --- |
| CVE-2026-107493 (uso tras liberación en `PEM_X509_INFO_read_bio_ex` y variantes) | Solo aplicaciones que pasan una pila no nula y siguen usándola tras un fallo; OpenSSL y su código TLS pasan NULL | No se encontró uso en `app/` ni en los módulos nativos de Python | No se inspeccionaron los argumentos de las llamadas internas de OpenSSL; el aviso afirma que pasan NULL. El CLI `openssl` sí enlaza la API, pero la aplicación no lo invoca |
| CVE-2026-84786 (caída de cliente TLS con DANE) | Cliente con DANE habilitado | No se encontró uso de DANE en `app/` ni en `_ssl`; Python no lo expone | No se verificó con una prueba de ejecución que ningún componente lo active por configuración |
| CVE-2026-107496 (bucle infinito en `CMS_encrypt`) | La aplicación cifra con CMS a un certificado EC controlado por un atacante; TLS y QUIC no usan esa ruta | No se encontró cifrado CMS en `app/` ni en Python | `/usr/bin/openssl cms` podría ejecutarse manualmente dentro del contenedor, pero nadie lo invoca desde la aplicación |

## Incertidumbres generales
- La búsqueda de símbolos no cubre carga dinámica por nombre ni código de terceros no listado en el lock.
- Se revisó el código del 21-nov-2026; un cambio posterior podría introducir el uso.
- Los avisos describen la condición de explotación según el equipo de OpenSSL; no se reprodujo ninguna.
- La imagen incluye Node de Playwright y herramientas de prueba porque el lock mezcla dependencias de ejecución y desarrollo. No se corrigió: no es parte de estas CVE, pero amplía la superficie.

## Mitigaciones aplicables
- Sin servidor TLS propio: Render termina TLS; la aplicación solo es cliente TLS hacia dos destinos conocidos (Cloudflare y LangSmith).
- Proceso sin privilegios (UID 10001), herramientas del agente de solo lectura, sin ejecución de procesos externos.
- Vigilar la corrección: repetir `docker scout cves` y `apt-cache policy openssl libssl3t64` antes de entregar y tras cada reconstrucción; reconstruir sobre la base cuando Debian publique el parche.
- Opcional, requiere decisión: separar dependencias de ejecución y de desarrollo para reducir la superficie (no mitiga estas CVE).

## Decisión que sigue pendiente
Aceptar el riesgo con justificación y fecha de revisión, esperar a la corrección de Debian, o emitir VEX con evidencia adicional (por ejemplo, pruebas de ejecución). Hasta entonces el estado es: **tres altas abiertas, sin riesgo aceptado y sin VEX**.
