FROM python:3.11-slim

# Instala o ffmpeg e dependências do sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python
RUN pip install --no-cache-dir fastapi uvicorn yt-dlp

COPY main.py .
COPY index.html .

# O Render define a variável PORT dinamicamente; o valor $PORT garante que funcione sem falhas
ENV PORT=10000
EXPOSE 10000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
