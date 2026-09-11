def get_real_stream_url(url: str) -> str:
    # Se não for um link HTTP, tratar como busca do YouTube
    if not url.startswith("http://") and not url.startswith("https://"):
        search_target = f"ytsearch1:{url}"
    else:
        search_target = url

    try:
        command = [
            "yt-dlp",
            "-g",
            "-f",
            "bestaudio/best",
            "--no-playlist",
            search_target,
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
    except Exception as error:
        print(f"Erro ao extrair áudio com yt-dlp: {error}")

    return url
