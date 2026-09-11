import os
import subprocess
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI(title="MTA/FiveM Live Equalizer")


FREQS = [
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400,
    500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000,
    6300, 8000, 10000, 12500, 16000, 20000, 22000
]


DEFAULT_GAINS = [
    6, 6, 6, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5,
    0, 0, -0.5, -1, -1, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5,
    3, 3.5, 4, 4.5, 5
]


@app.get("/", response_class=HTMLResponse)
def index():

    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:

        return """
        <h2>Arquivo index.html não encontrado!</h2>
        """


def get_real_stream_url(url: str) -> str:

    # URLs normais de rádio/stream
    if "youtube.com" not in url and "youtu.be" not in url:
        return url

    print("====================================")
    print("YOUTUBE DETECTADO")
    print("URL:", url)
    print("====================================")

    command = [
        "yt-dlp",

        "--no-playlist",

        "-f",
        "bestaudio/best",

        "--get-url",

        url
    ]

    try:

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )

        print("YT-DLP RETURN CODE:", result.returncode)

        if result.stderr:
            print("YT-DLP ERRO:")
            print(result.stderr)

        if result.returncode != 0:
            raise RuntimeError(
                "yt-dlp não conseguiu extrair o áudio."
            )

        urls = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        ]

        if not urls:
            raise RuntimeError(
                "yt-dlp não retornou nenhuma URL."
            )

        print("ÁUDIO EXTRAÍDO COM SUCESSO")

        return urls[0]

    except Exception as error:

        print("ERRO AO OBTER ÁUDIO DO YOUTUBE:")
        print(error)

        raise


def parse_bands(bands: Optional[str]):

    if not bands:
        return DEFAULT_GAINS

    try:

        gains = [
            float(value.strip())
            for value in bands.split(",")
        ]

        if len(gains) != 32:
            return DEFAULT_GAINS

        return [
            max(-12, min(12, value))
            for value in gains
        ]

    except Exception:

        return DEFAULT_GAINS


def build_filter(gains):

    filters = []

    for frequency, gain in zip(FREQS, gains):

        filters.append(
            f"equalizer="
            f"f={frequency}:"
            f"width_type=q:"
            f"w=1.414:"
            f"g={gain}"
        )

    filters.append("volume=1.8")
    filters.append("alimiter=limit=0.95")

    return ",".join(filters)


@app.get("/health")
def health():

    return {
        "status": "ok"
    }


@app.get("/stream")
def stream_audio(
    url: str = Query(...),
    bands: Optional[str] = None,
):

    print("")
    print("====================================")
    print("NOVO STREAM")
    print("URL:", url)
    print("====================================")

    gains = parse_bands(bands)

    filter_chain = build_filter(gains)

    try:

        audio_source = get_real_stream_url(url)

    except Exception as error:

        return {
            "error": "Não foi possível obter o áudio.",
            "details": str(error)
        }

    command = [
        "ffmpeg",

        "-hide_banner",

        "-loglevel",
        "warning",

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
        "128k",

        "-f",
        "adts",

        "pipe:1"
    ]

    print("INICIANDO FFMPEG")

    try:

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    except Exception as error:

        return {
            "error": "Erro ao iniciar FFmpeg.",
            "details": str(error)
        }

    return StreamingResponse(
        process.stdout,
        media_type="audio/aac",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
