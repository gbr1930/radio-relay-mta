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
STREAM_TIMEOUT = 7200        # 2h — streams antigos são limpos
STREAM_TTL_CHECK = 300       # checa a cada 5 min

app = FastAPI(title="MTA Live Equalizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# { stream_id: { "proc", "cmd", "yt_url", "original_url", "filters", "created" } }
active_streams: Dict[str, dict] = {}


# =========================================================
# COOKIES
# =========================================================

def ensure_cookies_file():
    """Garante que o cookies.txt existe e tem formato válido."""
    if os.path.exists(COOKIES_PATH):
        return True

    content = os.getenv("YT_COOKIES_CONTENT", "")
    if not content:
        print("⚠️  YT_COOKIES_CONTENT não definida")
        return False

    content = content.replace("\\n", "\n").replace("\r\n", "\n")

    if not content.startswith("# Netscape HTTP Cookie File"):
        print("⚠️  cookies.txt não está em formato Netscape!")
        if "\t" in content:
            content = "# Netscape HTTP Cookie File\n" + content

    with open(COOKIES_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    lines = content.strip().splitlines()
    cookie_lines = [l for l in lines if l and not l.startswith("#")]
    print(f"✅ cookies.txt criado: {len(cookie_lines)} cookies, {len(content)} bytes")

    for ess in ["SID\t", "__Secure-1PSID\t", "SAPISID\t", "LOGIN_INFO\t"]:
        if ess in content:
            print(f"   ✅ {ess.strip()}")
        else:
            print(f"   ❌ FALTANDO: {ess.strip()}")
    return True


# =========================================================
# EXTRAÇÃO DO YOUTUBE
# =========================================================

def get_real_stream_url(url: str) -> Optional[str]:
    """Extrai a URL direta do áudio do YouTube usando yt-dlp + POT + cookies."""
    if not url.startswith("http://") and not url.startswith("https://"):
        search_target = f"ytsearch1:{url}"
    else:
        url = url.replace("music.youtube.com", "www.youtube.com")
        url = re.sub(r"[?&]list=[^&]+", "", url)
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
            timeout=45,
        )

        if result.stderr:
            print("=" * 60)
            print(f"[yt-dlp] returncode: {result.returncode}")
            for line in result.stderr.strip().splitlines():
                print(f"  [yt-dlp] {line}")
            print("=" * 60)

        if result.returncode == 0 and result.stdout.strip():
            stream_url = result.stdout.strip().splitlines()[0]
            print(f"✅ Stream: {stream_url[:100]}...")
            return stream_url

        print(f"❌ yt-dlp falhou (returncode {result.returncode})")

    except subprocess.TimeoutExpired:
        print("❌ Timeout do yt-dlp (45s)")
    except Exception as e:
        print(f"❌ Erro yt-dlp: {e}")

    return None


# =========================================================
# FILTROS FFMPEG
# =========================================================

def build_ffmpeg_filters(
    bass: float, mid: float, treble: float,
    bassboost: float, anti: float,
    reverb: str, reverbmix: float,
) -> str:
    filters = []

    if bass != 0:
        filters.append(f"bass=g={bass}:f=100:w=0.6")
    if mid != 0:
        filters.append(f"equalizer=f=1000:t=q:w=1:g={mid}")
    if treble != 0:
        filters.append(f"treble=g={treble}:f=8000:w=0.6")

    if bassboost > 0:
        filters.append(f"bass=g={bassboost}:f=60:w=0.5")

    if anti > 0:
        threshold = -3 - (anti / 100) * 17
        filters.append(
            f"acompressor=threshold={threshold:.1f}dB:ratio=4:attack=5:release=80:makeup=2"
        )

    if reverb != "off" and reverbmix > 0:
        mix = reverbmix / 100
        reverb_presets = {
            "small":   "0.6:0.4:40:0.3:0.2:60:0.15",
            "hall":    "0.7:0.6:100:0.5:0.3:150:0.25",
            "church":  "0.8:0.7:200:0.6:0.4:300:0.35",
            "stadium": "0.9:0.8:400:0.7:0.5:600:0.45",
        }
        preset = reverb_presets.get(reverb)
        if preset:
            filters.append(f"aecho={preset}")
            filters.append(f"volume={1.0 + mix * 0.3:.2f}")

    return ",".join(filters) if filters else "anull"


def build_ffmpeg_cmd(yt_url: str, filters: str) -> list:
    """Monta o comando do FFmpeg (leve, para caber em 1 GB)."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-threads", "1",
        "-filter_threads", "1",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", yt_url,
        "-af", filters,
        "-f", "mp3",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-bufsize", "64k",
        "-max_muxing_queue_size", "64",
        "pipe:1",
    ]


# =========================================================
# HELPERS
# =========================================================

def stream_audio_generator(proc: subprocess.Popen, chunk_size: int = 4096):
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


def build_public_url(stream_id: str) -> str:
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if host:
        return f"https://{host}/live/{stream_id}"
    return f"/live/{stream_id}"


@app.on_event("startup")
async def startup_event():
    ensure_cookies_file()
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
    """Preview no navegador."""
    yt_url = get_real_stream_url(url)
    if not yt_url:
        raise HTTPException(status_code=500, detail="Não foi possível extrair o áudio")

    filters = build_ffmpeg_filters(bass, mid, treble, bassboost, anti, reverb, reverbmix)
    print(f"🎛️  Filtros: {filters}")

    proc = subprocess.Popen(
        build_ffmpeg_cmd(yt_url, filters),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    return StreamingResponse(stream_audio_generator(proc), media_type="audio/mpeg")


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
    """Cria um stream persistente para o MTA."""
    yt_url = get_real_stream_url(url)
    if not yt_url:
        return JSONResponse(
            {"error": "Não foi possível extrair o áudio do YouTube"},
            status_code=500,
        )

    filters = build_ffmpeg_filters(bass, mid, treble, bassboost, anti, reverb, reverbmix)

    # Reaproveita stream idêntico se existir e estiver vivo
    for sid, info in active_streams.items():
        if (
            info["original_url"] == url
            and info["filters"] == filters
            and info["proc"].poll() is None
        ):
            print(f"♻️  Reaproveitando stream {sid}")
            return {"stream_url": build_public_url(sid), "id": sid, "reused": True}

    stream_id = str(uuid.uuid4())[:8]
    cmd = build_ffmpeg_cmd(yt_url, filters)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    active_streams[stream_id] = {
        "proc": proc,
        "cmd": cmd,
        "yt_url": yt_url,
        "original_url": url,
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
    Se o FFmpeg morreu, reinicia automaticamente pegando URL fresca do YouTube.
    """
    info = active_streams.get(stream_id)
    if not info:
        raise HTTPException(status_code=404, detail="Stream não encontrado")

    proc = info["proc"]

    # Se o FFmpeg morreu, reinicia com URL nova
    if proc.poll() is not None:
        print(f"♻️  FFmpeg morreu para {stream_id}, reiniciando...")

        new_yt_url = get_real_stream_url(info["original_url"])
        if not new_yt_url:
            print(f"❌ Não conseguiu nova URL para {stream_id}")
            active_streams.pop(stream_id, None)
            raise HTTPException(status_code=500, detail="Não foi possível renovar o stream")

        new_cmd = build_ffmpeg_cmd(new_yt_url, info["filters"])

        try:
            proc.kill()
        except Exception:
            pass

        new_proc = subprocess.Popen(
            new_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        info["proc"] = new_proc
        info["cmd"] = new_cmd
        info["yt_url"] = new_yt_url
        info["created"] = time.time()
        proc = new_proc

        print(f"✅ FFmpeg reiniciado para {stream_id}")

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
