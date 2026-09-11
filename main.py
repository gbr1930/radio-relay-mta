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

HTML_UI = r"""
<!DOCTYPE html>
<html lang="pt-BR">

<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Live Equalizer - MTA / FiveM</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #0d1117;
    color: #e6edf3;
    font-family: Arial, sans-serif;
}

.container {
    max-width: 1200px;
    margin: 30px auto;
    padding: 20px;
}

.card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 14px;
    padding: 22px;
    margin-bottom: 18px;
}

h1 {
    margin-top: 0;
}

h2 {
    margin-top: 0;
}

p {
    color: #8b949e;
}

label {
    display: block;
    margin-bottom: 7px;
    font-weight: bold;
}

input[type="text"] {
    width: 100%;
    padding: 12px;

    border-radius: 8px;
    border: 1px solid #30363d;

    background: #0d1117;
    color: white;
}

.buttons {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 15px;
}

button {
    border: none;
    border-radius: 8px;
    padding: 10px 15px;

    background: #238636;
    color: white;

    cursor: pointer;
    font-weight: bold;
}

button:hover {
    filter: brightness(1.15);
}

button.secondary {
    background: #30363d;
}

.equalizer {
    display: grid;

    grid-template-columns:
        repeat(16, 1fr);

    gap: 10px;

    align-items: end;
}

.band {
    height: 250px;

    display: flex;
    flex-direction: column;

    align-items: center;
    justify-content: flex-end;
}

.band input {

    writing-mode: vertical-lr;

    direction: rtl;

    width: 28px;
    height: 190px;

    accent-color: #58a6ff;
}

.value {
    font-size: 11px;
    color: #58a6ff;

    margin-bottom: 5px;
}

.frequency {

    font-size: 10px;

    color: #8b949e;

    margin-top: 5px;

    white-space: nowrap;
}

.output {

    display: flex;

    gap: 10px;
}

.output input {

    flex: 1;
}

.status {

    margin-top: 12px;

    color: #8b949e;
}

@media(max-width: 900px) {

    .equalizer {

        grid-template-columns:
            repeat(8, 1fr);

    }

}

@media(max-width: 550px) {

    .equalizer {

        grid-template-columns:
            repeat(4, 1fr);

    }

}

</style>

</head>

<body>

<div class="container">

    <div class="card">

        <h1>🎛️ Live Equalizer</h1>

        <p>
            Equalizador para gerar um stream AAC
            para MTA/FiveM.
        </p>

        <label>
            URL de origem
        </label>

        <input
            id="source"
            type="text"
            value="https://stream-175.surfernetwork.com/bev4hfkh4bstv"
            placeholder="Cole aqui uma rádio, stream ou YouTube"
        >

        <div class="buttons">

            <button onclick="preset('flat')">
                ⚖️ Flat
            </button>

            <button onclick="preset('bass')">
                🔊 Bass Boost
            </button>

            <button onclick="preset('voice')">
                🎤 Voz
            </button>

            <button onclick="preset('loud')">
                💥 Loud
            </button>

            <button
                class="secondary"
                onclick="resetEq()"
            >
                Resetar
            </button>

        </div>

    </div>


    <div class="card">

        <h2>
            🎚️ Equalizador
        </h2>

        <div
            id="equalizer"
            class="equalizer"
        ></div>

    </div>


    <div class="card">

        <h2>
            🔗 URL gerada
        </h2>

        <div class="output">

            <input
                id="output"
                type="text"
                readonly
            >

            <button onclick="copyUrl()">
                📋 Copiar
            </button>

        </div>

        <div
            id="status"
            class="status"
        >
            A URL é atualizada automaticamente.
        </div>

    </div>

</div>


<script>

const frequencies = [

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

];


const defaultValues = [

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

];


const equalizer =
    document.getElementById("equalizer");


function createEqualizer() {

    equalizer.innerHTML = "";

    frequencies.forEach(
        (frequency, index) => {

            const container =
                document.createElement("div");

            container.className =
                "band";


            container.innerHTML = `

                <div
                    class="value"
                    id="value-${index}"
                >
                    ${defaultValues[index]} dB
                </div>

                <input
                    id="band-${index}"
                    type="range"
                    min="-12"
                    max="12"
                    step="0.5"
                    value="${defaultValues[index]}"
                >

                <div class="frequency">
                    ${frequency} Hz
                </div>

            `;


            equalizer.appendChild(container);


            document
                .getElementById(
                    "band-" + index
                )
                .addEventListener(
                    "input",
                    update
                );

        }
    );


    update();

}


function getGains() {

    return frequencies.map(
        (_, index) => {

            return parseFloat(
                document
                    .getElementById(
                        "band-" + index
                    )
                    .value
            );

        }
    );

}


function update() {

    frequencies.forEach(
        (_, index) => {

            const value =
                document
                    .getElementById(
                        "band-" + index
                    )
                    .value;


            document
                .getElementById(
                    "value-" + index
                )
                .textContent =
                value + " dB";

        }
    );


    const source =
        document
            .getElementById("source")
            .value
            .trim();


    const bands =
        getGains().join(",");


    const generatedUrl =

        window.location.origin +

        "/stream?url=" +

        encodeURIComponent(source) +

        "&bands=" +

        encodeURIComponent(bands);


    document
        .getElementById("output")
        .value =
        generatedUrl;

}


document
    .getElementById("source")
    .addEventListener(
        "input",
        update
    );


function setValues(values) {

    values.forEach(
        (value, index) => {

            document
                .getElementById(
                    "band-" + index
                )
                .value = value;

        }
    );


    update();

}


function resetEq() {

    setValues(
        Array(32).fill(0)
    );

}


function preset(name) {

    if (name === "flat") {

        resetEq();

        return;

    }


    if (name === "bass") {

        setValues([

            8, 8, 7, 7,
            6, 6, 5, 4,
            3, 2, 1, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 1,
            1, 2, 2, 3,
            3, 3, 2, 1

        ]);

        return;

    }


    if (name === "voice") {

        setValues([

            -4, -4, -3, -2,
            -1, 0, 1, 2,
            3, 4, 5, 5,
            4, 3, 2, 2,
            2, 2, 3, 4,
            4, 3, 2, 1,
            0, 0, -1, -2,
            -2, -2, -2, -2

        ]);

        return;

    }


    if (name === "loud") {

        setValues([

            4, 4, 3, 3,
            2, 2, 2, 2,
            2, 2, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1,
            1, 1, 1, 1

        ]);

    }

}


async function copyUrl() {

    const output =
        document.getElementById(
            "output"
        );


    try {

        await navigator
            .clipboard
            .writeText(
                output.value
            );


        document
            .getElementById(
                "status"
            )
            .textContent =
            "✅ URL copiada!";

    }

    catch {

        output.select();

        document.execCommand(
            "copy"
        );


        document
            .getElementById(
                "status"
            )
            .textContent =
            "✅ URL copiada!";

    }

}


createEqualizer();

</script>

</body>

</html>
"""


def get_real_stream_url(url: str) -> str:

    if (
        "youtube.com" in url
        or "youtu.be" in url
    ):

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

                timeout=20

            )


            if (
                result.returncode == 0
                and result.stdout.strip()
            ):

                return (
                    result
                    .stdout
                    .strip()
                    .splitlines()[0]
                )


        except Exception as error:

            print(
                f"Erro no yt-dlp: {error}"
            )


    return url


def parse_bands(
    bands: Optional[str]
):

    if not bands:

        return DEFAULT_GAINS


    try:

        gains = [

            float(value)

            for value
            in bands.split(",")

        ]


        if len(gains) != 32:

            return DEFAULT_GAINS


        return [

            max(
                -12,
                min(12, value)
            )

            for value in gains

        ]


    except Exception:

        return DEFAULT_GAINS


def build_filter(gains):

    filters = []


    for frequency, gain in zip(
        FREQS,
        gains
    ):

        filters.append(

            f"equalizer="
            f"f={frequency}:"
            f"width_type=q:"
            f"w=1.414:"
            f"g={gain}"

        )


    filters.append(
        "volume=1.8"
    )

    filters.append(
        "alimiter=limit=0.95"
    )


    return ",".join(filters)


@app.get(
    "/",
    response_class=HTMLResponse
)
def index():

    return HTML_UI


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

    bands: Optional[str] = None

):

    gains = parse_bands(
        bands
    )


    filter_chain = build_filter(
        gains
    )


    audio_source =
        get_real_stream_url(url)


    command = [

        "ffmpeg",

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
        "128k",

        "-f",
        "adts",

        "pipe:1"

    ]


    process = subprocess.Popen(

        command,

        stdout=subprocess.PIPE,

        stderr=subprocess.DEVNULL

    )


    return StreamingResponse(

        process.stdout,

        media_type="audio/aac",

        headers={
            "Cache-Control": "no-cache"
        }

    )
