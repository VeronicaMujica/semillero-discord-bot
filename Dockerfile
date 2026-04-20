# Imagen base de Python
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Copiar todo el código al contenedor
COPY . /app

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Comando que ejecuta el bot (-u para forzar stdout sin buffer)
CMD ["python", "-u", "bot.py"]
