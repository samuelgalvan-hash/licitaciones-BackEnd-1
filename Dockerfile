# syntax=docker/dockerfile:1
 
# --- Mantén la imagen y la librería Playwright sincronizadas ---
# Cambia ambos ARG si necesitas otra versión (p.ej., v1.56.0-noble / 1.56.0)
ARG PW_IMAGE_TAG=v1.56.0-noble
ARG PW_LIB_VER=1.56.0
 
# Imagen oficial Playwright para Python con navegadores y dependencias del SO
FROM mcr.microsoft.com/playwright/python:${PW_IMAGE_TAG}
 
# Reexpón el ARG tras FROM para poder usarlo (opcional)
ARG PW_LIB_VER
 
# Buenas prácticas y puerto que inyecta Render
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=10000
 
# Directorio de trabajo
WORKDIR /app
 
# 1) Instala dependencias Python
#    - requirements.txt: tus libs (FastAPI, Uvicorn, etc.)
#    - playwright: se instala con la MISMA versión que la imagen
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
&& pip install --no-cache-dir "playwright==${PW_LIB_VER}"
 
# 2) Copia el resto del proyecto
COPY . .
 
# 3) Expón el puerto (Render usará $PORT)
EXPOSE 10000
 
# 4) Arranque FastAPI (lee $PORT o 8000 por defecto)
CMD ["bash", "-c", "uvicorn myMain:app --host 0.0.0.0 --port ${PORT:-8000}"]
