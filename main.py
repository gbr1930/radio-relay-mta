import os
import re
import subprocess
import shutil
from urllib.parse import urlparse

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse


app = FastAPI(
    title="MTA/FiveM Live Equalizer",
    version="1.0"
)


# =========================================================
# CONFIGURAÇÕES
# =========================================================

FREQS = [
    20,
    25,
    31.5,
    40,
    50,
    63,
    80,
    100,
    125,
    160,
    200,
    250,
    315,
    400,
    500,
    630,
    800,
    1000,
    1250,
    1600,
    2000,
    2500,
    3150,
    4000,
    5000,
    6300,
    8000,
    10000,
    12500,
    16000,
    20000,
    22000
]


DEFAULT_GAINS = [
    6,
    6,
    6,
    5.5,
    5,
    4.5,
    4,
    3.5,
    3,
    2.5,
    2,
    1.5,
    1,
    0.5,
    0,
    0,
    -0.5,
    -1,
    -1,
    -1,
    -0.5,
    0,
    0.5,
    1,
    1.5,
    2,
    2.5,
    3,
    3.5,
    4,
    4.5,
    5
]


# =========================================================
# CAMINHOS
# =========================================================

DENO_PATH = shutil.which("deno") or "/root/.deno/bin/deno"
YTDLP_PATH = shutil.which("yt-dlp") or "/usr/local/bin/yt-dlp"
FFMPEG_PATH = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

BGUTIL_HOME = "/app/bgutil-ytdlp-pot-provider/server"


# =========================================================
# VERIFICAÇÃO DO SISTEMA
# =========================================================

print("")
print("==========================================")
print("SISTEMA")
print("==========================================")
print("DENO:", DENO_PATH)
print("YT-DLP:", YTDLP_PATH)
print("FFMPEG:", FFMPEG_PATH)
print("BGUTIL:", BGUTIL_HOME)
print("DENO EXISTE:", os.path.exists(DENO_PATH))
print("YT-DLP EXISTE:", os.path.exists(YTDLP_PATH))
print("FFMPEG EXISTE:", os.path.exists(FFMPEG_PATH))
print("BGUTIL EXISTE:", os.path.exists(BGUTIL_HOME))
print("==========================================")
print("")


# =========================================================
# IDENTIFICA YOUTUBE
# =========================================================

def is_youtube_url(url: str) -> bool:

    url_lower = url.lower()

    return (
        "youtube.com" in url_lower
        or "youtu.be" in url_lower
        or "music.youtube.com" in url_lower
    )


# =========================================================
# LIMPA URL DO YOUTUBE
# =========================================================

def clean_youtube_url(url: str) -> str:

    """
    Remove parâmetros desnecessários de playlist/radio.

    Exemplo:

    https://www.youtube.com/watch?v=ABC&list=RDABC&start_radio=1

    vira:

    https://www.youtube.com/watch?v=ABC
    """

    if "youtube.com/watch" not in url:
        return url

    match = re.search(r"(?:v=)([^&]+)", url)

    if match:
        video_id = match.group(1)

        return f"https://www.youtube.com/watch?v={video_id}"

    return url


# =========================================================
# OBTÉM URL REAL DO ÁUDIO
# =========================================================

def get_real_stream_url(url: str) -> str:

    if not is_youtube_url(url):

        print("URL NÃO É YOUTUBE")
        print("USANDO URL DIRETAMENTE")

        return url


    original_url = url

    url = clean_youtube_url(url)


    print("")
    print("==========================================")
    print("YOUTUBE DETECTADO")
    print("==========================================")
    print("URL ORIGINAL:")
    print(original_url)
    print("")
    print("URL LIMPA:")
    print(url)
    print("==========================================")


    # -----------------------------------------------------
    # Comando yt-dlp
    # -----------------------------------------------------

    command = [

        YTDLP_PATH,

        "--no-playlist",

        "--no-warnings",

        "--quiet",

        "--no-check-certificates",

        "--js-runtimes",
        f"deno:{DENO_PATH}",

        "--extractor-args",
        f"youtubepot-bgutilscript:server_home={BGUTIL_HOME}",

        "-f",
        "bestaudio/best",

        "--get-url",

        url
    ]


    print("")
    print("EXECUTANDO YT-DLP:")
    print(" ".join(command))
    print("")


    try:

        result = subprocess.run(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            timeout=90
        )


    except subprocess.TimeoutExpired:

        print("YT-DLP TIMEOUT")

        raise RuntimeError(
            "O YouTube demorou demais para responder."
        )


    except Exception as e:

        print("ERRO EXECUTANDO YT-DLP:")
        print(str(e))

        raise RuntimeError(
            f"Erro executando yt-dlp: {e}"
        )


    print("YT-DLP RETURN CODE:", result.returncode)


    if result.stderr:

        print("")
        print("YT-DLP STDERR:")
        print(result.stderr)


    if result.returncode != 0:

        print("")
        print("==========================================")
        print("YT-DLP FALHOU")
        print("==========================================")
        print("")

        raise RuntimeError(
            "yt-dlp não conseguiu extrair o áudio do YouTube."
        )


    # -----------------------------------------------------
    # Obtém URL retornada
    # -----------------------------------------------------

    audio_url = result.stdout.strip()


    if not audio_url:

        print("YT-DLP NÃO RETORNOU URL")

        raise RuntimeError(
            "yt-dlp não retornou uma URL de áudio."
        )


    # Caso existam várias linhas, pegar a última válida
    lines = [
        line.strip()
        for line in audio_url.splitlines()
        if line.strip()
    ]


    if not lines:

        raise RuntimeError(
            "yt-dlp retornou uma resposta vazia."
        )


    audio_url = lines[-1]


    print("")
    print("==========================================")
    print("ÁUDIO EXTRAÍDO COM SUCESSO")
    print("==========================================")
    print("URL OBTIDA:")
    print(audio_url[:300])
    print("==========================================")
    print("")


    return audio_url


# =========================================================
# CONSTRÓI FILTRO DO EQUALIZADOR
# =========================================================

def build_filter(
    gains=None,
    bass_boost=0,
    volume=1.0,
    reverb=False,
    surround=False
):

    if gains is None:
        gains = DEFAULT_GAINS


    # Garantir 32 bandas

    gains = list(gains)

    if len(gains) < len(FREQS):

        gains += [0] * (
            len(FREQS) - len(gains)
        )

    gains = gains[:len(FREQS)]


    filters = []


    # -----------------------------------------------------
    # 32 BANDAS
    # -----------------------------------------------------

    for freq, gain in zip(FREQS, gains):

        try:

            gain = float(gain)

        except:

            gain = 0


        # Limita ganho para evitar valores absurdos

        gain = max(-15, min(15, gain))


        if gain != 0:

            filters.append(

                f"equalizer="
                f"f={freq}:"
                f"width_type=q:"
                f"width=1.414:"
                f"g={gain}"

            )


    # -----------------------------------------------------
    # BASS BOOST
    # -----------------------------------------------------

    try:

        bass_boost = float(bass_boost)

    except:

        bass_boost = 0


    bass_boost = max(0, min(15, bass_boost))


    if bass_boost > 0:

        filters.append(

            "bass="
            f"g={bass_boost}:"
            "f=100:"
            "width_type=q:"
            "width=1"

        )


    # -----------------------------------------------------
    # REVERB
    # -----------------------------------------------------

    if reverb:

        filters.append(

            "aecho="
            "in_gain=0.8:"
            "out_gain=0.6:"
            "delays=80|160:"
            "decays=0.25|0.12"

        )


    # -----------------------------------------------------
    # EFEITO 3D / SURROUND
    # -----------------------------------------------------

    if surround:

        filters.append(

            "stereotools="
            "mlev=1:"
            "mwid=1.4"

        )


    # -----------------------------------------------------
    # VOLUME
    # -----------------------------------------------------

    try:

        volume = float(volume)

    except:

        volume = 1.0


    volume = max(0.1, min(3.0, volume))


    filters.append(
        f"volume={volume}"
    )


    # -----------------------------------------------------
    # LIMITER
    # -----------------------------------------------------

    filters.append(
        "alimiter=limit=0.95"
    )


    return ",".join(filters)


# =========================================================
# HOME
# =========================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
async def home():

    try:

        with open(
            "index.html",
            "r",
            encoding="utf-8"
        ) as f:

            return f.read()

    except FileNotFoundError:

        return """
        <html>
        <body>
        <h1>MTA/FiveM Live Equalizer</h1>
        <p>Arquivo index.html não encontrado.</p>
        </body>
        </html>
        """


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
async def health():

    return {

        "status": "ok",

        "deno": os.path.exists(DENO_PATH),

        "yt_dlp": os.path.exists(YTDLP_PATH),

        "ffmpeg": os.path.exists(FFMPEG_PATH),

        "bgutil": os.path.exists(BGUTIL_HOME)

    }


# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
async def stream(

    url: str = Query(...),

    bass: float = 0,

    volume: float = 1.0,

    reverb: int = 0,

    surround: int = 0

):

    print("")
    print("==========================================")
    print("NOVO STREAM")
    print("==========================================")
    print("URL:", url)
    print("Bass:", bass)
    print("Volume:", volume)
    print("Reverb:", reverb)
    print("Surround:", surround)
    print("==========================================")
    print("")


    # -----------------------------------------------------
    # Obtém fonte
    # -----------------------------------------------------

    try:

        audio_source = get_real_stream_url(url)

    except Exception as e:

        print("")
        print("ERRO AO OBTER ÁUDIO:")
        print(str(e))
        print("")

        return JSONResponse(

            status_code=500,

            content={

                "error": "Não foi possível obter o áudio.",

                "details": str(e)

            }

        )


    # -----------------------------------------------------
    # Equalizador
    # -----------------------------------------------------

    filter_chain = build_filter(

        gains=DEFAULT_GAINS,

        bass_boost=bass,

        volume=volume,

        reverb=(reverb == 1),

        surround=(surround == 1)

    )


    print("")
    print("==========================================")
    print("FILTRO FFMPEG")
    print("==========================================")
    print(filter_chain)
    print("==========================================")
    print("")


    # -----------------------------------------------------
    # FFmpeg
    # -----------------------------------------------------

    command = [

        FFMPEG_PATH,

        "-hide_banner",

        "-loglevel",
        "error",

        "-reconnect",
        "1",

        "-reconnect_streamed",
        "1",

        "-reconnect_delay_max",
        "5",

        "-i",
        audio_source,

        "-vn",

        "-af",
        filter_chain,

        "-c:a",
        "aac",

        "-b:a",
        "192k",

        "-ar",
        "48000",

        "-ac",
        "2",

        "-f",
        "adts",

        "pipe:1"

    ]


    print("")
    print("==========================================")
    print("INICIANDO FFMPEG")
    print("==========================================")
    print("")


    try:

        process = subprocess.Popen(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            bufsize=0

        )

    except Exception as e:

        print("ERRO INICIANDO FFMPEG:")
        print(str(e))

        return JSONResponse(

            status_code=500,

            content={

                "error": "Não foi possível iniciar o FFmpeg.",

                "details": str(e)

            }

        )


    return StreamingResponse(

        process.stdout,

        media_type="audio/aac",

        headers={

            "Cache-Control": "no-cache",

            "Connection": "keep-alive",

            "Accept-Ranges": "none"

        }

    )
