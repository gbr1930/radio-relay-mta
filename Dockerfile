FROM python:3.11-slim

# =========================================================
# DEPENDÊNCIAS DO SISTEMA
# =========================================================

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    git \
    unzip \
    && rm -rf /var/lib/apt/lists/*


# =========================================================
# DENO
# =========================================================

RUN curl -fsSL https://deno.land/install.sh | sh

ENV DENO_INSTALL=/root/.deno
ENV PATH=/root/.deno/bin:$PATH


# =========================================================
# DIRETÓRIO
# =========================================================

WORKDIR /app


# =========================================================
# PYTHON / YT-DLP
# =========================================================

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi \
    uvicorn \
    "yt-dlp[default]" \
    bgutil-ytdlp-pot-provider


# =========================================================
# BGUTIL PO TOKEN PROVIDER
# =========================================================

RUN git clone \
    --depth 1 \
    --branch 2.0.0 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    /app/bgutil-ytdlp-pot-provider


# Instala as dependências do servidor BGUtil
RUN cd /app/bgutil-ytdlp-pot-provider/server && \
    deno install --allow-scripts=npm:canvas --frozen


# =========================================================
# COPIA A APLICAÇÃO
# =========================================================

COPY . .


# =========================================================
# RENDER
# =========================================================

ENV PORT=10000

EXPOSE 10000


# =========================================================
# INICIA BGUTIL + FASTAPI
# =========================================================

CMD cd /app/bgutil-ytdlp-pot-provider/server/node_modules && \
    deno run \
    --allow-env \
    --allow-net \
    --allow-ffi=. \
    --allow-read=. \
    ../src/main.ts --host 127.0.0.1 --port 4416 & \
    sleep 5 && \
    uvicorn main:app --host 0.0.0.0 --port ${PORT}
