FROM python:3.10-slim

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV USE_LOCAL_AI=true
ENV OLLAMA_URL=http://ollama:11434

# Порт для веб-сервера
EXPOSE 8080

# Запуск
CMD ["python", "main.py"]
