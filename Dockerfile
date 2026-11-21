# Imagen del HR Assistant. Dependencias instaladas desde requirements.lock.txt.
# Base fijada por digest (indice multiarquitectura) de python:3.12.16-slim-trixie,
# verificada el 19-nov-2026 en linux/amd64. Ver evidence/docker/resultado.md.
FROM python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

# No escribir archivos .pyc y mostrar el log sin almacenamiento intermedio.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Actualizacion puntual de zlib1g desde los repositorios oficiales de Debian
# trixie. Motivo: Docker Scout reporta en la imagen base CVE-2026-85091 y
# CVE-2026-76844 en zlib 1:1.3.dfsg+really1.3.1-1; la version corregida es
# 1:1.3.dfsg+really1.3.1-1+deb13u1. Se ejecuta como root, antes de crear el
# usuario sin privilegios y de copiar la aplicacion. No se instalan otros
# paquetes ni se hace un upgrade general. La verificacion con Docker Scout sobre
# hr-assistant:revision decide si este cambio sirve.
RUN apt-get update \
    && apt-get install --no-install-recommends --only-upgrade -y zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Las dependencias van primero para aprovechar la cache de capas.
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

# El codigo y los datos. Lo que excluye .dockerignore no entra a la imagen.
COPY . .

# Usuario sin privilegios: el proceso no corre como root.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Render define PORT; en local se usa 8000. Los secretos llegan por entorno.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
