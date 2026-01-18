
# syntax=docker/dockerfile:1

# Mantén imagen y librería Playwright sincronizadas
ARG PW_IMAGE_TAG=v1.56.0-noble
ARG PW_LIB_VER=1.56.0

# Imagen Playwright para Python (con navegadores y dependencias del SO)
FROM mcr.microsoft.com/playwright/python:${PW_IMAGE_TAG}

# Reexpón el ARG tras FROM
ARG PW_LIB_VER

# Buenas prácticas y puerto para Render
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=10000 \
    PYTHONPATH=/app

# Directorio de trabajo
WORKDIR /app

# 1) Instalar dependencias Python
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "playwright==${PW_LIB_VER}"

# 2) Copiar el resto del proyecto
COPY . .

# 3) Exponer el puerto (Render usará $PORT)
EXPOSE 10000

# 4) Arranque FastAPI apuntando a myMain.py en RAÍZ
CMD ["bash", "-c", "uvicorn myMain:app --host 0.0.0.0 --port ${PORT:-10000}"]
