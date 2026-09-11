FROM python:3.11-slim

# Instala FFmpeg, Deno e dependências do sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instala Deno
RUN curl -fsSL https://deno.land/install.sh | sh

ENV DENO_INSTALL=/root/.deno
ENV PATH="/root/.deno/bin:$PATH"

WORKDIR /app

# Instala Python + yt-dlp com EJS
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    "yt-dlp[default]"

# Copia todos os arquivos
COPY . .

ENV PORT=10000

EXPOSE 10000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
