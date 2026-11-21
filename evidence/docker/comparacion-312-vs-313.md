# Comparación de bases: Python 3.12 slim vs 3.13 slim (19 de noviembre de 2026)

Solo comparación. El Dockerfile no se modificó y no se aceptó ningún riesgo. linux/amd64, Docker Scout.

| | Actual: 3.12.16-slim-trixie | Candidata: 3.13.18-slim-trixie |
| --- | --- | --- |
| Digest (índice) | sha256:5e2bdb1b…4fa5b | sha256:e48f59cd…ed90 |
| Críticas | 0 | 0 |
| Altas | 8 | 14 |
| openssl 3.5.7-1~deb13u3 | 6, sin corrección | 6, sin corrección |
| zlib 1.3.1-1 | 2, corregible (deb13u1) | 2, corregible (deb13u1) |
| msgpack 1.1.2 | no aparece | 3 |
| urllib3 2.7.0 | no aparece | 2 (corrección 2.8.0) |
| setuptools 70.3.0 | no aparece | 1 (CVE-2025-47273; corrección 78.1.1) |

Archivos: `scout-base.txt`, `scout-base-313.txt`, `scout-compare-312-vs-313.txt`.

## Lectura
- 3.13 no reduce los hallazgos del sistema operativo (mismo openssl y zlib de Debian trixie) y añade 6 altas de paquetes Python.
- msgpack y urllib3 se localizaron en `site-packages/pip/_vendor` (copia empaquetada dentro de pip 26.2.2). El lock instala urllib3 2.8.0 en `site-packages`, pero eso no modifica la copia vendorizada. La ubicación de setuptools 70.3.0 no se confirmó.
- No se escaneó una imagen final basada en 3.13, por lo que no se sabe cuántas de esas 6 persistirían; es una verificación pendiente. Con la base actual, la imagen final solo tenía las 6 de openssl.
- Conclusión provisional: con estos datos 3.13 no mejora la postura de seguridad. La decisión sobre openssl sigue siendo suya.

## Compatibilidad (sin cambiar el proyecto)
- Comprobado: `pip install -r requirements.lock.txt` en la base 3.13 terminó con código 0 y las 155 pruebas pasaron (`compat-313.txt`).
- No comprobado: Pylint y las 7 pruebas de navegador con 3.13; humo de contenedor; las dependencias podrían resolver distinto si se regenerara el lock.
- Riesgos: el lock y la verificación de Windows fueron con 3.12.16; CI (`.github/workflows/ci.yml`), README y los documentos ADR/arquitectura indican 3.12 y habría que actualizarlos; 3.13 retira módulos obsoletos de la biblioteca estándar y cambia el comportamiento de algunas dependencias, por lo que una actualización de paquetes futura debe revalidarse.
- Cambiar de rama exigiría actualizar el Dockerfile, CI y documentación y repetir el escaneo final: no se hizo.
