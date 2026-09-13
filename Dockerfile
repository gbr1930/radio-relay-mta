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
ENV DENO_INSTALL=/root/.deno
ENV PATH=${DENO_INSTALL}/bin:$PATH
RUN curl -fsSL https://deno.land/install.sh | sh

# =========================================================
# DIRETÓRIO
# =========================================================
WORKDIR /app

# =========================================================
# PYTHON / YT-DLP (versão mais recente sempre)
# =========================================================
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi \
    uvicorn \
    -U "yt-dlp[default]" \
    bgutil-ytdlp-pot-provider

# =========================================================
# BGUTIL PO TOKEN PROVIDER (servidor HTTP local)
# =========================================================
RUN git clone \
    --depth 1 \
    --branch 2.0.0 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    /app/bgutil-ytdlp-pot-provider

WORKDIR /app/bgutil-ytdlp-pot-provider/server
RUN deno install --allow-scripts=npm:canvas --frozen

# =========================================================
# COPIA A APLICAÇÃO
# =========================================================
WORKDIR /app
COPY . .

# =========================================================
# START SCRIPT
# =========================================================
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV PORT=10000
EXPOSE 10000

CMD ["/app/start.sh"]
