# Imagen del HR Assistant. Se usa un tag de version menor. PENDIENTE: verificar
# el tag exacto, el digest y las vulnerabilidades reportadas de la imagen base;
# no se hicieron por falta de acceso a la red.
FROM python:3.12-slim

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
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# El codigo y los datos. Lo que excluye .dockerignore no entra a la imagen.
COPY . .

# Usuario sin privilegios: el proceso no corre como root.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Render define PORT; en local se usa 8000. Los secretos llegan por entorno.
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
