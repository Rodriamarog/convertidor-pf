FROM python:3.9-slim

# Instalar dependencias del sistema necesarias para el procesamiento de PDF
RUN apt-get update && apt-get install -y \
    ghostscript \
    pdftk \
    poppler-utils \
    imagemagick \
    qpdf \
    && rm -rf /var/lib/apt/lists/*

# Configurar ImageMagick para permitir operaciones con PDF
RUN sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml

WORKDIR /app

# Copiar los archivos de requisitos primero para aprovechar la caché de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn==21.2.0

# Copiar el resto de la aplicación
COPY . .

# Crear directorios necesarios
RUN mkdir -p uploads results jobs
RUN chmod 777 uploads results jobs

# Exponer el puerto
EXPOSE 5001

# Comando para ejecutar la aplicación con Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app:app", "--workers", "4", "--timeout", "300", "--log-level", "debug"] 