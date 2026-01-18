
# syntax=docker/dockerfile:1

# --- Mantén imagen y librería Playwright sincronizadas ---
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

# 3) (Opcional) asegurar paquete raíz si lo necesitas
# Si ya tienes __init__.py (como muestras), no hace falta; lo dejamos por si acaso.
# RUN test -f __init__.py || touch __init__.py

# 4) Exponer el puerto (Render usará $PORT igualmente)
EXPOSE 10000

# 5) Arranque FastAPI apuntando a myMain.py en RAÍZ
# Nota: ${PORT} lo inyecta Render en runtime; usamos 10000 por defecto si no está.
CMD ["bash", "-c", "uvicorn myMain:app --host 0.0.0.0 --port ${PORT:-10000}"]
