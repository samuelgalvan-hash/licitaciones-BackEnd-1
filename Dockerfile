# Imagen base oficial de Python con soporte slim
FROM python:3.11-slim

# 1) Dependencias necesarias para Chromium y Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcb-dri3-0 \
    libxext6 \
    libxi6 \
    && rm -rf /var/lib/apt/lists/*

# 2) Directorio de trabajo
WORKDIR /app

# 3) Copiar e instalar dependencias de Python
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 4) Instalar el CLI de Playwright (IMPORTANTE)
RUN pip install playwright

# 5) Instalar los navegadores  
RUN playwright install --with-deps chromium

# 6) Copiar el resto del proyecto
COPY . .

# 7) Exponer puerto
EXPOSE 8000

# 8) Ejecutar FastAPI
CMD ["uvicorn", "myMain:app", "--host", "0.0.0.0", "--port", "8000"]
