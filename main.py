import subprocess
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI(title="MTA/FiveM Live Equalizer")


# Frequências do equalizador
FREQS = [
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400,
    500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000,
    6300, 8000, 10000, 12500, 16000, 20000, 22000
]


# Ganhos padrão
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
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Erro</title>
        </head>
        <body>
            <h2>Arquivo index.html não encontrado!</h2>
            <p>Coloque o arquivo index.html na mesma pasta do main.py.</p>
        </body>
        </html>
        """


def get_real_stream_url(url: str) -> str:
    """
    Se a URL for do YouTube, tenta obter a URL real
    do áudio usando yt-dlp.

    Para outras URLs, retorna a própria URL.
    """

    if "youtube.com" in url or "youtu.be" in url:

        try:
            command = [
                "yt-dlp",
                "-g",
                "-f",
                "bestaudio/best",
                url
            ]

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().splitlines()[0]

            print("yt-dlp não conseguiu obter o stream.")
            print(result.stderr)

        except Exception as error:
            print(f"Erro no yt-dlp: {error}")

    return url


def parse_bands(bands: Optional[str]):
    """
    Converte a string:

    6,6,5.5,5,...

    em uma lista de números.
    """

    if not bands:
        return DEFAULT_GAINS

    try:
        gains = [
            float(value.strip())
            for value in bands.split(",")
        ]

        # Precisamos exatamente das 32 bandas
        if len(gains) != 32:
            print(
                f"Número incorreto de bandas: "
                f"{len(gains)}. Esperado: 32."
            )

            return DEFAULT_GAINS

        # Limita cada banda entre -12 dB e +12 dB
        gains = [
            max(-12, min(12, value))
            for value in gains
        ]

        return gains

    except Exception as error:
        print(f"Erro ao interpretar bandas: {error}")
        return DEFAULT_GAINS


def build_filter(gains):
    """
    Monta a cadeia de filtros do FFmpeg.
    """

    filters = []

    for frequency, gain in zip(FREQS, gains):

        filters.append(
            f"equalizer="
            f"f={frequency}:"
            f"width_type=q:"
            f"w=1.414:"
            f"g={gain}"
        )

    # Volume
    filters.append("volume=1.8")

    # Limiter para evitar clipping
    filters.append("alimiter=limit=0.95")

    return ",".join(filters)


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/stream")
def stream_audio(
    url: str = Query(
        ...,
        description="URL da rádio, stream ou YouTube"
    ),
    bands: Optional[str] = None,
):

    # Lê as bandas do equalizador
    gains = parse_bands(bands)

    # Monta os filtros
    filter_chain = build_filter(gains)

    # Obtém o stream real
    audio_source = get_real_stream_url(url)

    print("Fonte original:")
    print(url)

    print("Fonte utilizada pelo FFmpeg:")
    print(audio_source)

    # Comando FFmpeg
    command = [
        "ffmpeg",

        "-hide_banner",
        "-loglevel",
        "error",

        # Reconexão automática
        "-reconnect",
        "1",

        "-reconnect_streamed",
        "1",

        "-reconnect_delay_max",
        "5",

        # Entrada
        "-i",
        audio_source,

        # Sem vídeo
        "-vn",

        # Equalizador + volume + limiter
        "-af",
        filter_chain,

        # Codec AAC
        "-c:a",
        "aac",

        # Bitrate
        "-b:a",
        "128k",

        # Formato
        "-f",
        "adts",

        # Envia o áudio pelo stdout
        "pipe:1",
    ]

    try:

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

    except Exception as error:

        print(f"Erro ao iniciar FFmpeg: {error}")

        return {
            "error": "Não foi possível iniciar o FFmpeg",
            "details": str(error)
        }

    return StreamingResponse(
        process.stdout,
        media_type="audio/aac",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
