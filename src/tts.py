from __future__ import annotations

import os
from pathlib import Path
from urllib.request import urlretrieve

import soundfile as sf
from kokoro_onnx import Kokoro

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.int8.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 1_000_000:
        return
    print(f"Downloading {destination.name}...")
    urlretrieve(url, destination)


def generate_narration(
    text: str,
    output_path: str | Path,
    *,
    voice: str = "af_sky",
    speed: float = 0.95,
) -> float:
    cache = Path(os.environ.get("KOKORO_CACHE", ".cache/kokoro"))
    model = cache / "kokoro-v1.0.int8.onnx"
    voices = cache / "voices-v1.0.bin"
    _download(MODEL_URL, model)
    _download(VOICES_URL, voices)

    engine = Kokoro(str(model), str(voices))
    samples, sample_rate = engine.create(
        text,
        voice=voice,
        speed=speed,
        lang="en-us",
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, samples, sample_rate)
    return len(samples) / float(sample_rate)
