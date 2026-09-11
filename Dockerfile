FROM python:3.11-slim

# Dependências
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instala Deno diretamente no local padrão
RUN curl -fsSL https://deno.land/install.sh | sh

# Deixa o Deno disponível para todos os comandos
ENV DENO_INSTALL=/root/.deno
ENV PATH=/root/.deno/bin:$PATH

WORKDIR /app

# Atualiza pip e instala yt-dlp + EJS
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "yt-dlp[default]" fastapi uvicorn

# Copia TODOS os arquivos do projeto
COPY . .

ENV PORT=10000

EXPOSE 10000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
