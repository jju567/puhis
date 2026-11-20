"""Puheentunnistimen rajapinta (`TranscriberProtocol`) ja `faster-whisper`-toteutus."""

from collections.abc import Callable, Iterable
import logging
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from puhis.core.config_store import AppConfig
from puhis.platform.paths import ensure_dir, get_models_dir
from puhis.stt.vad import DEFAULT_SAMPLE_RATE

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "small"
DEFAULT_COMPUTE_TYPE = "int8"
DEFAULT_LANGUAGE = "fi"
DEFAULT_CPU_THREADS = 4
MAX_NO_SPEECH_PROB = 0.75


class TranscriberProtocol(Protocol):
    """Vaihdettava puheentunnistimen rajapinta (paikallinen tai pilvi)."""

    def transcribe(self, audio: np.ndarray, sample_rate: int = DEFAULT_SAMPLE_RATE) -> str:
        """Muuntaa mono float32 -äänipuskurin tekstiksi."""


def build_initial_prompt(config: AppConfig) -> str:
    """Rakentaa Whisperille avainsanavihjeen suomen- ja englanninkielisille komennoille."""
    terms: list[str] = [
        config.wake_word,
        "sanele",
        "seis",
        "mykistä",
        "save t1",
        "t1",
        "t2",
        "t3",
        "fokus t1",
        "piilota t1",
        "avaa",
        "käynnistä",
    ]
    for app_alias in sorted(config.app_aliases):
        if app_alias not in terms:
            terms.append(app_alias)
    for keyword in sorted(config.keywords):
        if keyword not in terms:
            terms.append(keyword)
    return ", ".join(terms)


def _default_model_factory(
    model_size: str,
    device: str,
    compute_type: str,
    cpu_threads: int,
    download_root: Path,
) -> Any:
    from faster_whisper import WhisperModel

    ensure_dir(download_root)
    return WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
        download_root=str(download_root),
    )


class FasterWhisperTranscriber:
    """Paikallinen CPU-optimoitu (`small` INT8) `faster-whisper`-puheentunnistin."""

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = "cpu",
        compute_type: str = DEFAULT_COMPUTE_TYPE,
        language: str = DEFAULT_LANGUAGE,
        cpu_threads: int = DEFAULT_CPU_THREADS,
        download_root: Path | None = None,
        initial_prompt: str = "",
        model_factory: Callable[..., Any] = _default_model_factory,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._cpu_threads = max(1, cpu_threads)
        self._download_root = download_root if download_root is not None else get_models_dir()
        self._initial_prompt = initial_prompt
        self._model_factory = model_factory
        self._model: Any = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def initial_prompt(self) -> str:
        return self._initial_prompt

    def set_initial_prompt(self, prompt: str) -> None:
        """Päivittää Whisperin sanastovihjeen."""
        self._initial_prompt = prompt

    def load_model(self) -> None:
        """Lataa Whisper-mallin muistiin, jos sitä ei ole vielä ladattu."""
        if self._model is not None:
            return
        logger.info(
            "Ladataan faster-whisper-malli '%s' (%s, %s, hakemisto=%s)",
            self._model_size,
            self._device,
            self._compute_type,
            self._download_root,
        )
        self._model = self._model_factory(
            self._model_size,
            self._device,
            self._compute_type,
            self._cpu_threads,
            self._download_root,
        )
        logger.info("faster-whisper-malli '%s' valmis", self._model_size)

    def transcribe(self, audio: np.ndarray, sample_rate: int = DEFAULT_SAMPLE_RATE) -> str:
        """Tunnistaa puheen 16 kHz mono float32 -puskurista."""
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return ""
        if sample_rate != DEFAULT_SAMPLE_RATE:
            raise ValueError(f"Whisper odottaa {DEFAULT_SAMPLE_RATE} Hz ääntä, saatiin {sample_rate} Hz")

        self.load_model()
        normalized = normalize_audio(samples)
        segments, _info = self._model.transcribe(
            normalized,
            language=self._language,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            without_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300, "speech_pad_ms": 200},
            initial_prompt=self._initial_prompt or None,
        )
        return _collect_segments_text(segments)


def normalize_audio(samples: np.ndarray, target_peak: float = 0.7, max_gain: float = 20.0) -> np.ndarray:
    """Vahvistaa hiljaisen mikrofonisignaalin sopivalle tasolle Whisperiä varten."""
    if samples.size == 0:
        return samples
    peak = float(np.max(np.abs(samples)))
    if peak <= 1e-4 or peak >= target_peak:
        return samples
    gain = min(max_gain, target_peak / peak)
    return np.clip(samples * gain, -1.0, 1.0).astype(np.float32, copy=False)


def _collect_segments_text(segments: Iterable[Any]) -> str:
    parts: list[str] = []
    for seg in segments:
        no_speech = float(getattr(seg, "no_speech_prob", 0.0) or 0.0)
        if no_speech > MAX_NO_SPEECH_PROB:
            continue
        text = str(getattr(seg, "text", "")).strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()
