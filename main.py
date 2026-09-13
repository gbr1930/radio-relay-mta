import subprocess
import os
import re
import uuid
import time
import asyncio
import urllib.request
from typing import Dict, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# =========================================================
# CONFIG
# =========================================================

COOKIES_PATH = "/app/cookies.txt"
POT_URL = "http://127.0.0.1:4416"
STREAM_TIMEOUT = 3600  # 1h — expira streams antigos
STREAM_TTL_CHECK = 300  # checa expiração a cada 5 min

app = FastAPI(title="MTA Live Equalizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de streams ativos em memória
# { stream_id: { "proc": Popen, "yt_url": str, "filters": str, "created": float } }
active_streams: Dict[str, dict] = {}


# =========================================================
# UTILITÁRIOS
# =========================================================

def get_real_stream_url(url: str) -> Optional[str]:
    """Extrai a URL direta do áudio do YouTube usando yt-dlp + POT + cookies."""
    if not url.startswith("http://") and not url.startswith("https://"):
        search_target = f"ytsearch1:{url}"
    else:
        url = url.replace("music.youtube.com", "www.youtube.com")
        url = re.sub(r"[?&]list=[^&]+", "", url)  # remove playlist
        url = re.sub(r"[?&]start_radio=[^&]+", "", url)
        search_target = url

    command = [
        "yt-dlp",
        "-g",
        "-f", "bestaudio[ext=m4a]/bestaudio/best",
        "--no-playlist",
        "--no-warnings",
        "--extractor-args", "youtube:player_client=web_safari,mweb,tv",
        "--extractor-args", f"youtubepot-bgutilhttp:base_url={POT_URL}",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--referer", "https://www.youtube.com/",
        "--add-header", "Accept-Language:en-US,en;q=0.9",
    ]

    if os.path.exists(COOKIES_PATH):
        command.extend(["--cookies", COOKIES_PATH])
    else:
        print(f"⚠️  Sem cookies em {COOKIES_PATH}")

    command.append(search_target)

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

        if result.stderr:
            for line in result.stderr.strip().splitlines()[-10:]:
                print(f"[yt-dlp] {line}")

        if result.returncode == 0 and result.stdout.strip():
            stream_url = result.stdout.strip().splitlines()[0]
            print(f"✅ Stream: {stream_url[:100]}...")
            return stream_url

        print(f"❌ yt-dlp falhou (returncode {result.returncode})")

    except subprocess.TimeoutExpired:
        print("❌ Timeout do yt-dlp (30s)")
    except Exception as e:
        print(f"❌ Erro yt-dlp: {e}")

    return None


def build_ffmpeg_filters(
    bass: float, mid: float, treble: float,
    bassboost: float, anti: float,
    reverb: str, reverbmix: float,
) -> str:
    """Monta a cadeia de filtros do FFmpeg baseado nos parâmetros."""
    filters = []

    # Equalizador básico (3 bandas)
    if bass != 0:
        filters.append(f"bass=g={bass}:f=100:w=0.6")
    if mid != 0:
        # mid usa equalizer (frequência central 1000 Hz)
        filters.append(f"equalizer=f=1000:t=q:w=1:g={mid}")
    if treble != 0:
        filters.append(f"treble=g={treble}:f=8000:w=0.6")

    # Bass Booster (mais agressivo, sub-bass)
    if bassboost > 0:
        filters.append(f"bass=g={bassboost}:f=60:w=0.5")

    # Anti-distorção (compressor)
    # anti=0 → sem compressão; anti=100 → compressão máxima
    if anti > 0:
        # threshold vai de -3dB (pouca compressão) a -20dB (muita compressão)
        threshold = -3 - (anti / 100) * 17
        filters.append(
            f"acompressor=threshold={threshold:.1f}dB:ratio=4:attack=5:release=80:makeup=2"
        )

    # Reverb (precisa de arquivos IR em /app/ir/)
    if reverb != "off" and reverbmix > 0:
        ir_files = {
            "small":   "/app/ir/small.wav",
            "hall":    "/app/ir/hall.wav",
            "church":  "/app/ir/church.wav",
            "stadium": "/app/ir/stadium.wav",
        }
        ir_file = ir_files.get(reverb)
        if ir_file and os.path.exists(ir_file):
            mix = reverbmix / 100
            filters.append(f"afir=gtype=0:ir={ir_file}:mix={mix:.2f}")
        else:
            print(f"⚠️  Reverb '{reverb}' solicitado mas IR não encontrado em {ir_file}")

    # Se nenhum filtro aplicado, retorna nulo
    return ",".join(filters) if filters else "anull"


def stream_audio_generator(proc: subprocess.Popen, chunk_size: int = 4096):
    """Generator que lê do stdout do FFmpeg e envia em chunks."""
    try:
        while True:
            chunk = proc.stdout.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        try:
            proc.kill()
        except Exception:
            pass


def cleanup_expired_streams():
    """Remove streams antigos (>1h) para liberar memória."""
    now = time.time()
    expired = [
        sid for sid, info in active_streams.items()
        if now - info["created"] > STREAM_TIMEOUT
    ]
    for sid in expired:
        info = active_streams.pop(sid, None)
        if info:
            try:
                info["proc"].kill()
            except Exception:
                pass
            print(f"🧹 Stream {sid} expirado e removido")


async def periodic_cleanup():
    while True:
        await asyncio.sleep(STREAM_TTL_CHECK)
        cleanup_expired_streams()


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_cleanup())


# =========================================================
# ROTAS
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>index.html não encontrado</h1>"


@app.get("/health")
async def health():
    pot_ok = False
    try:
        urllib.request.urlopen(f"{POT_URL}/ping", timeout=2)
        pot_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "pot": pot_ok,
        "cookies": os.path.exists(COOKIES_PATH),
        "active_streams": len(active_streams),
    }


@app.get("/stream")
async def stream_preview(
    url: str = Query(...),
    bass: float = 0,
    mid: float = 0,
    treble: float = 0,
    bassboost: float = 0,
    anti: float = 70,
    reverb: str = "off",
    reverbmix: float = 0,
):
    """
    Preview no navegador: extrai áudio do YouTube, aplica filtros e
    envia via StreamingResponse (progressive download).
    """
    yt_url = get_real_stream_url(url)
    if not yt_url:
        raise HTTPException(status_code=500, detail="Não foi possível extrair o áudio do YouTube")

    filters = build_ffmpeg_filters(bass, mid, treble, bassboost, anti, reverb, reverbmix)
    print(f"🎛️  Filtros aplicados: {filters}")

    # FFmpeg lê do YouTube e envia MP3 via pipe
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", yt_url,
        "-af", filters,
        "-f", "mp3",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        "pipe:1",
    ]

    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    return StreamingResponse(
        stream_audio_generator(proc),
        media_type="audio/mpeg",
    )


@app.get("/api/create-stream")
async def create_stream(
    url: str = Query(...),
    bass: float = 0,
    mid: float = 0,
    treble: float = 0,
    bassboost: float = 0,
    anti: float = 70,
    reverb: str = "off",
    reverbmix: float = 0,
):
    """
    Gera um stream persistente para o MTA:SA.
    Retorna uma URL /live/<id> que pode ser consumida pelo MTA.
    """
    yt_url = get_real_stream_url(url)
    if not yt_url:
        return JSONResponse(
            {"error": "Não foi possível extrair o áudio do YouTube"},
            status_code=500,
        )

    filters = build_ffmpeg_filters(bass, mid, treble, bassboost, anti, reverb, reverbmix)
    stream_id = str(uuid.uuid4())[:8]

    # Verifica se já existe um stream idêntico (mesma URL + filtros) e reaproveita
    for sid, info in active_streams.items():
        if info["yt_url"] == yt_url and info["filters"] == filters:
            print(f"♻️  Reaproveitando stream {sid}")
            return {"stream_url": build_public_url(sid), "id": sid, "reused": True}

    # Inicia FFmpeg em modo "streaming infinito" (MP3 192k)
    # Nota: o FFmpeg vai rodar continuamente, o MTA conecta em /live/<id>
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", yt_url,
        "-af", filters,
        "-f", "mp3",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        "-listen", "1",          # Modo servidor HTTP
        f"http://0.0.0.0:0/live", # FFmpeg escolhe a porta, mas na prática usamos pipe
    ]

    # ATENÇÃO: o comando acima com "-listen 1" não é confiável.
    # Melhor abordagem: usar pipe e servir via /live/<id> com StreamingResponse.
    # Reexecuta com pipe:
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", yt_url,
        "-af", filters,
        "-f", "mp3",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        "pipe:1",
    ]

    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    active_streams[stream_id] = {
        "proc": proc,
        "yt_url": yt_url,
        "filters": filters,
        "created": time.time(),
    }

    print(f"✅ Stream {stream_id} criado | Filtros: {filters}")

    return {
        "stream_url": build_public_url(stream_id),
        "id": stream_id,
        "filters": filters,
    }


@app.get("/live/{stream_id}")
async def live_stream(stream_id: str):
    """
    Endpoint consumido pelo MTA:SA.
    Retorna o áudio processado em MP3.
    """
    info = active_streams.get(stream_id)
    if not info:
        raise HTTPException(status_code=404, detail="Stream não encontrado ou expirado")

    proc = info["proc"]
    if proc.poll() is not None:
        # Processo morreu, remove
        active_streams.pop(stream_id, None)
        raise HTTPException(status_code=410, detail="Stream expirou")

    return StreamingResponse(
        stream_audio_generator(proc),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache, no-store",
            "icy-name": "MTA Live Equalizer",
        },
    )


@app.delete("/api/stream/{stream_id}")
async def stop_stream(stream_id: str):
    info = active_streams.pop(stream_id, None)
    if not info:
        raise HTTPException(status_code=404, detail="Stream não encontrado")
    try:
        info["proc"].kill()
    except Exception:
        pass
    return {"stopped": stream_id}


# =========================================================
# HELPERS
# =========================================================

def build_public_url(stream_id: str) -> str:
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if host:
        return f"https://{host}/live/{stream_id}"
    return f"/live/{stream_id}"
