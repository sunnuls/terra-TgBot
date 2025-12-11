# Dockerfile для развертывания Telegram бота

FROM python:3.11-slim

# Установка рабочей директории
WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всех файлов проекта
COPY . .

# Создание директории для базы данных
RUN mkdir -p /app/data

# Переменные окружения (будут перезаписаны через docker run или docker-compose)
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Moscow

# Запуск бота
CMD ["python", "bot_polya.py"]



