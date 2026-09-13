import subprocess
import os
import re
import tempfile

# Caminho do cookies.txt (via variável de ambiente no Render)
COOKIES_PATH = os.getenv("YT_COOKIES_PATH", "/app/cookies.txt")

def get_real_stream_url(url: str) -> str:
    # Se não for um link HTTP, tratar como busca do YouTube
    if not url.startswith("http://") and not url.startswith("https://"):
        search_target = f"ytsearch1:{url}"
    else:
        # Normalizar link do YouTube Music para YouTube comum
        url = url.replace("music.youtube.com", "www.youtube.com")
        search_target = url

    # Argumentos essenciais do yt-dlp para funcionar no Render
    command = [
        "yt-dlp",
        "-g",                              # Apenas retorna a URL do stream
        "-f", "bestaudio[ext=m4a]/bestaudio/best",  # Prioriza m4a (melhor qualidade)
        "--no-playlist",
        "--no-warnings",
        "--geo-bypass",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--extractor-args", "youtube:player_client=mweb,tv,web",
        "--extractor-args", "youtubepot-bgutilhttp:base_url=http://127.0.0.1:4416",
        "--referer", "https://www.youtube.com/",
        "--add-header", "Accept-Language:en-US,en;q=0.9",
    ]

    # Adiciona cookies se o arquivo existir
    if os.path.exists(COOKIES_PATH):
        command.extend(["--cookies", COOKIES_PATH])
    else:
        print(f"⚠️ AVISO: cookies.txt não encontrado em {COOKIES_PATH}")

    command.append(search_target)

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

        # Log detalhado para debug
        if result.stderr:
            print(f"[yt-dlp stderr]: {result.stderr[:500]}")

        if result.returncode == 0 and result.stdout.strip():
            # Pega a primeira URL válida (pode vir mais de uma)
            urls = result.stdout.strip().splitlines()
            stream_url = urls[0]
            print(f"✅ Stream extraído: {stream_url[:80]}...")
            return stream_url
        else:
            print(f"❌ yt-dlp falhou (código {result.returncode})")

    except subprocess.TimeoutExpired:
        print("❌ Timeout ao extrair áudio (30s)")
    except Exception as error:
        print(f"❌ Erro ao extrair áudio: {error}")

    return url
