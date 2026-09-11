FROM python:3.11-slim

# ==========================================
# DEPENDÊNCIAS DO SISTEMA
# ==========================================

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    git \
    unzip \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*


# ==========================================
# DENO
# ==========================================

RUN curl -fsSL https://deno.land/install.sh | sh

ENV DENO_INSTALL=/root/.deno
ENV PATH=/root/.deno/bin:$PATH


# ==========================================
# DIRETÓRIO DA APLICAÇÃO
# ==========================================

WORKDIR /app


# ==========================================
# PYTHON / YT-DLP
# ==========================================

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi \
    uvicorn \
    "yt-dlp[default]" \
    bgutil-ytdlp-pot-provider


# ==========================================
# BGUTIL PO TOKEN PROVIDER
# ==========================================

RUN git clone \
    --single-branch \
    --branch 2.0.0 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    /app/bgutil-ytdlp-pot-provider


# Instala as dependências do provider usando Deno
RUN cd /app/bgutil-ytdlp-pot-provider/server && \
    deno install --allow-scripts=npm:canvas --frozen


# ==========================================
# COPIA O PROJETO
# ==========================================

COPY . .


# ==========================================
# CONFIGURAÇÃO RENDER
# ==========================================

ENV PORT=10000

EXPOSE 10000


# ==========================================
# INICIA FASTAPI
# ==========================================

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
