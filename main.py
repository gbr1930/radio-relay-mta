import os
import subprocess
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

FREQS = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000, 22000]

def parse_bands(bands_str: str):
    try:
        gains = [float(x) for x in bands_str.split(",")]
        return gains if len(gains) == 32 else None
    except:
        return None

def build_filter(gains):
    filters = []
    for f, g in zip(FREQS, gains):
        filters.append(f"equalizer=f={f}:width_type=q:w=1.414:g={g}")
    filters.append("volume=1.8")
    filters.append("alimiter=limit=0.95")
    return ",".join(filters)

@app.get("/stream")
def stream_audio(url: str = "https://stream-175.surfernetwork.com/bev4hfkh4bstv", bands: str = None):
    default_gains = [6, 6, 6, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5, 0, 0, -0.5, -1, -1, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]
    
    gains = parse_bands(bands) if bands else default_gains
    if not gains:
        gains = default_gains
        
    filter_chain = build_filter(gains)

    cmd = [
        "ffmpeg",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", url,
        "-af", filter_chain,
        "-c:a", "aac",
        "-b:a", "128k",
        "-f", "adts",
        "pipe:1"
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def generate_bytes():
        try:
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
        finally:
            process.kill()

    return StreamingResponse(generate_bytes(), media_type="audio/aac")