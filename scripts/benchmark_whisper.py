"""Suorituskyky- ja viivetesti paikalliselle `faster-whisper` (INT8 CPU) -mallille.

Käyttö:
    # Oikea CPU-nopeustesti (lataa small INT8 -mallin %LOCALAPPDATA%\\puhis\\models-kansioon):
    .\\.venv\\Scripts\\python.exe scripts\\benchmark_whisper.py

    # Kevyt kuiva-ajo ilman mallin latausta:
    .\\.venv\\Scripts\\python.exe scripts\\benchmark_whisper.py --dry-run
"""

import argparse
import sys
import time
from typing import Any

import numpy as np

from puhis.core.config_store import AppConfig
from puhis.stt.transcriber import FasterWhisperTranscriber, build_initial_prompt
from puhis.stt.vad import DEFAULT_SAMPLE_RATE, EnergyVadSegmenter


class _FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text
        self.no_speech_prob = 0.05


class _FakeWhisperModel:
    def transcribe(self, _audio: np.ndarray, **_kwargs: Any) -> tuple[list[_FakeSegment], object]:
        return [_FakeSegment("puhis avaa laskin")], object()


def _make_synthetic_speech(duration_s: float, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0.0, duration_s, int(sample_rate * duration_s), endpoint=False, dtype=np.float32)
    carrier = 0.12 * np.sin(2.0 * np.pi * 180.0 * t) + 0.06 * np.sin(2.0 * np.pi * 360.0 * t)
    return carrier.astype(np.float32)


def run_benchmark(model_size: str, threads: int, dry_run: bool) -> int:
    config = AppConfig()
    prompt = build_initial_prompt(config)
    print(f"Alustetaan benchmark (model={model_size}, compute_type=int8, threads={threads}, dry_run={dry_run})")
    print(f"initial_prompt: {prompt}")

    vad = EnergyVadSegmenter()
    silence = np.zeros(DEFAULT_SAMPLE_RATE, dtype=np.float32)
    speech_2s = _make_synthetic_speech(2.0)

    t0 = time.perf_counter()
    vad.feed(silence)
    vad.feed(speech_2s)
    segments = vad.feed(silence)
    vad_ms = (time.perf_counter() - t0) * 1000.0
    print(f"VAD-leikkaus (4.0 s ääntä -> {len(segments)} puhejaksoa): {vad_ms:.2f} ms")

    if dry_run:
        transcriber = FasterWhisperTranscriber(
            model_size=model_size,
            cpu_threads=threads,
            initial_prompt=prompt,
            model_factory=lambda *_args: _FakeWhisperModel(),
        )
    else:
        transcriber = FasterWhisperTranscriber(
            model_size=model_size,
            cpu_threads=threads,
            initial_prompt=prompt,
        )

    t_load_start = time.perf_counter()
    transcriber.load_model()
    load_s = time.perf_counter() - t_load_start
    print(f"Mallin latausaika: {load_s:.2f} s")

    for duration_s in (2.0, 4.0):
        clip = _make_synthetic_speech(duration_s)
        t_start = time.perf_counter()
        text = transcriber.transcribe(clip)
        elapsed_s = time.perf_counter() - t_start
        rtf = elapsed_s / duration_s
        print(
            f"Clip {duration_s:.1f} s -> viive {elapsed_s:.2f} s "
            f"(RTF={rtf:.2f}x, tulos={text!r})"
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="small", help="Whisper-mallin koko (oletus: small)")
    parser.add_argument("--threads", type=int, default=2, help="CPU-säikeiden määrä (oletus: 2)")
    parser.add_argument("--dry-run", action="store_true", help="Aja ilman oikean mallin latausta")
    args = parser.parse_args()
    return run_benchmark(args.model, args.threads, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
