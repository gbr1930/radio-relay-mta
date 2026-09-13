#!/bin/bash
set -e

echo "[INFO] Iniciando BGUtil POT Provider..."

cd /app/bgutil-ytdlp-pot-provider/server
deno run \
  --allow-env \
  --allow-net \
  --allow-ffi \
  --allow-read \
  --allow-write \
  src/main.ts --host 127.0.0.1 --port 4416 &

POT_PID=$!
echo "[INFO] POT PID: $POT_PID"

for i in $(seq 1 30); do
  if curl -s http://127.0.0.1:4416/ping >/dev/null 2>&1; then
    echo "[OK] POT pronto"
    break
  fi
  echo "[WAIT] Aguardando POT... ($i/30)"
  sleep 1
done

if [ -n "$YT_COOKIES_CONTENT" ]; then
  printf '%s' "$YT_COOKIES_CONTENT" > /app/cookies.txt
  echo "[OK] cookies.txt criado"
else
  echo "[WARN] YT_COOKIES_CONTENT nao definida"
fi

cd /app
echo "[INFO] Iniciando FastAPI..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-10000}"
