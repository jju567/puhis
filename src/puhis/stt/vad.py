"""Kevyt energiapohjainen puheaktiivisuuden tunnistus (VAD) ja puhejaksojen leikkaus."""

from collections import deque
from dataclasses import dataclass
import math

import numpy as np

DEFAULT_SAMPLE_RATE = 16_000
NOISE_FLOOR_ALPHA = 0.95
NOISE_FLOOR_MULTIPLIER = 3.0
MAX_NOISE_FLOOR = 0.25


@dataclass(frozen=True, slots=True)
class VadConfig:
    """VAD-leikkurin asetukset (16 kHz mono float32 -äänelle)."""

    sample_rate: int = DEFAULT_SAMPLE_RATE
    frame_duration_ms: int = 30
    rms_threshold: float = 0.0035
    pre_roll_ms: int = 450
    min_speech_ms: int = 240
    silence_duration_ms: int = 700
    max_utterance_ms: int = 8_000

    @property
    def frame_samples(self) -> int:
        return max(1, (self.sample_rate * self.frame_duration_ms) // 1000)

    @property
    def pre_roll_frames(self) -> int:
        return max(1, math.ceil(self.pre_roll_ms / self.frame_duration_ms))

    @property
    def min_speech_frames(self) -> int:
        return max(1, math.ceil(self.min_speech_ms / self.frame_duration_ms))

    @property
    def silence_frames(self) -> int:
        return max(1, math.ceil(self.silence_duration_ms / self.frame_duration_ms))

    @property
    def max_utterance_frames(self) -> int:
        return max(1, math.ceil(self.max_utterance_ms / self.frame_duration_ms))


def compute_rms(frame: np.ndarray) -> float:
    """Laskee äänikehyksen tehollisarvon (RMS)."""
    if frame.size == 0:
        return 0.0
    mean_sq = float(np.mean(np.square(frame, dtype=np.float64)))
    return math.sqrt(max(0.0, mean_sq))


class EnergyVadSegmenter:
    """Leikkaa jatkuvasta äänivirrasta puhejaksot esipuskurilla ja adaptiivisella kohinakynnyksellä."""

    def __init__(self, config: VadConfig | None = None) -> None:
        self._config = config or VadConfig()
        self._frame_size = self._config.frame_samples
        self._remainder = np.empty(0, dtype=np.float32)
        self._pre_roll: deque[np.ndarray] = deque(maxlen=self._config.pre_roll_frames)
        self._active_frames: list[np.ndarray] = []
        self._active_rms_sum = 0.0
        self._speaking = False
        self._voiced_count = 0
        self._trailing_silence = 0
        self._noise_floor = 0.0

    @property
    def config(self) -> VadConfig:
        return self._config

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    @property
    def effective_threshold(self) -> float:
        """Aktiivinen puhekynnys, joka huomioi mitatun taustakohinan."""
        return max(self._config.rms_threshold, self._noise_floor * NOISE_FLOOR_MULTIPLIER)

    def reset(self) -> None:
        """Tyhjentää puskurit ja palauttaa lepotilaan."""
        self._remainder = np.empty(0, dtype=np.float32)
        self._pre_roll.clear()
        self._reset_utterance()

    def feed(self, samples: np.ndarray) -> list[np.ndarray]:
        """Syöttää uusia ääninäytteitä ja palauttaa valmistuneet puhejaksot."""
        flat = np.asarray(samples, dtype=np.float32).reshape(-1)
        if flat.size == 0:
            return []

        if self._remainder.size > 0:
            data = np.concatenate((self._remainder, flat))
        else:
            data = flat

        completed: list[np.ndarray] = []
        total = data.size
        offset = 0
        while offset + self._frame_size <= total:
            frame = data[offset : offset + self._frame_size].copy()
            offset += self._frame_size
            segment = self._process_frame(frame)
            if segment is not None:
                completed.append(segment)

        self._remainder = data[offset:].copy()
        return completed

    def flush(self) -> np.ndarray | None:
        """Pakottaa keskeneräisen puhejakson valmiiksi (esim. kuuntelun pysähtyessä)."""
        if not self._speaking:
            self._reset_utterance()
            return None
        segment = self._finalize_if_valid()
        self._reset_utterance()
        return segment

    def _process_frame(self, frame: np.ndarray) -> np.ndarray | None:
        rms = compute_rms(frame)
        threshold = self.effective_threshold
        voiced = rms >= threshold

        if not self._speaking:
            if not voiced:
                self._update_noise_floor(rms)
                self._pre_roll.append(frame)
                return None

            # Puhe alkoi: otetaan esipuskuri mukaan, jottei sanan alku leikkaudu.
            self._speaking = True
            self._active_frames = list(self._pre_roll)
            self._pre_roll.clear()
            self._active_frames.append(frame)
            self._active_rms_sum = rms
            self._voiced_count = 1
            self._trailing_silence = 0
            return None

        self._active_frames.append(frame)
        self._active_rms_sum += rms
        if voiced:
            self._voiced_count += 1
            self._trailing_silence = 0
        else:
            self._trailing_silence += 1

        if self._trailing_silence >= self._config.silence_frames:
            segment = self._finalize_if_valid()
            self._reset_utterance()
            return segment

        if len(self._active_frames) >= self._config.max_utterance_frames:
            # Jos jakso katkesi aikarajaan ilman hiljaisuutta, kyseessä voi olla
            # kohonnut taustamelu -> nostetaan kohinatasoa, jottei Whisper jää silmukkaan.
            avg_rms = self._active_rms_sum / max(1, len(self._active_frames))
            self._noise_floor = min(MAX_NOISE_FLOOR, max(self._noise_floor, avg_rms * 0.85))
            segment = self._finalize_if_valid()
            self._reset_utterance()
            return segment

        return None

    def _update_noise_floor(self, rms: float) -> None:
        if self._noise_floor <= 0.0:
            self._noise_floor = min(MAX_NOISE_FLOOR, rms)
        else:
            updated = NOISE_FLOOR_ALPHA * self._noise_floor + (1.0 - NOISE_FLOOR_ALPHA) * rms
            self._noise_floor = min(MAX_NOISE_FLOOR, updated)

    def _finalize_if_valid(self) -> np.ndarray | None:
        if self._voiced_count < self._config.min_speech_frames or not self._active_frames:
            return None
        return np.concatenate(self._active_frames).astype(np.float32, copy=False)

    def _reset_utterance(self) -> None:
        self._active_frames.clear()
        self._active_rms_sum = 0.0
        self._speaking = False
        self._voiced_count = 0
        self._trailing_silence = 0
