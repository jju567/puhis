"""Jatkuva mikrofonin taustakuuntelu (`sounddevice`), VAD-leikkaus ja STT-työsäie."""

from collections.abc import Callable
from contextlib import AbstractContextManager
import logging
import queue
import threading
from typing import Any

import numpy as np

from puhis.stt.transcriber import TranscriberProtocol
from puhis.stt.vad import EnergyVadSegmenter, VadConfig, compute_rms

logger = logging.getLogger(__name__)

QUEUE_MAX_CHUNKS = 256
# Jos jonoon on kertynyt yli ~1 s ääntä tunnistuksen aikana, vanha häntä
# tyhjennetään, jottei CPU jää 100 %:n kuormalla purkamaan jonoa silmukassa.
MAX_BACKLOG_CHUNKS = 35
WORKER_POLL_TIMEOUT_S = 0.1
STOP_JOIN_TIMEOUT_S = 2.0

type UtteranceCallback = Callable[[str], None]
type CandidatesCallback = Callable[[list[str]], None]
type ErrorCallback = Callable[[str], None]
type ProcessingCallback = Callable[[bool], None]
type ReadyCallback = Callable[[], None]
type StreamFactory = Callable[[int, int, Callable[[np.ndarray], None]], AbstractContextManager[Any]]


def resample_audio(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Muuntaa mono float32 -äänen kohdenäytteenottotaajuuteen lineaarisesti."""
    if src_rate <= 0 or dst_rate <= 0 or src_rate == dst_rate or samples.size == 0:
        return np.asarray(samples, dtype=np.float32)
    dst_len = max(1, int(round(samples.size * (dst_rate / src_rate))))
    src_positions = np.linspace(0.0, float(samples.size - 1), num=dst_len, dtype=np.float64)
    indices = np.arange(samples.size, dtype=np.float64)
    return np.interp(src_positions, indices, samples).astype(np.float32, copy=False)


def _select_preferred_input(sd_module: Any, target_rate: int) -> tuple[int | None, int]:
    """Valitsee Windowsissa WASAPI-oletusmikrofonin natiivitaajuudella, jos saatavilla."""
    try:
        hostapis = sd_module.query_hostapis()
        default_in = sd_module.query_devices(kind="input")
        default_name = str(default_in.get("name", "")).strip()
        for api_idx, api in enumerate(hostapis):
            if "WASAPI" not in str(api.get("name", "")).upper():
                continue
            for dev_idx in api.get("devices", ()):
                dev = sd_module.query_devices(dev_idx)
                if int(dev.get("max_input_channels", 0)) <= 0:
                    continue
                if default_name and default_name[:18].lower() in str(dev.get("name", "")).lower():
                    native_rate = int(dev.get("default_samplerate", target_rate)) or target_rate
                    return int(dev_idx), native_rate
            fallback_dev = api.get("default_input_device", -1)
            if isinstance(fallback_dev, int) and fallback_dev >= 0:
                dev = sd_module.query_devices(fallback_dev)
                native_rate = int(dev.get("default_samplerate", target_rate)) or target_rate
                return fallback_dev, native_rate
    except Exception:
        logger.debug("WASAPI-laitteen valinta ohitettiin, käytetään oletusmikrofonia", exc_info=True)
    return None, target_rate


def _default_stream_factory(
    sample_rate: int,
    block_size: int,
    on_audio: Callable[[np.ndarray], None],
) -> AbstractContextManager[Any]:
    import sounddevice as sd

    device_idx, stream_rate = _select_preferred_input(sd, sample_rate)
    stream_block = max(1, int(round(block_size * (stream_rate / sample_rate))))

    def _callback(indata: np.ndarray, _frames: int, _time_info: Any, status: Any) -> None:
        if status:
            logger.debug("sounddevice-tila: %s", status)
        mono = indata[:, 0].copy()
        if stream_rate != sample_rate:
            mono = resample_audio(mono, stream_rate, sample_rate)
        on_audio(mono)

    logger.info(
        "Avataan äänivirta (laite=%s, %d Hz -> %d Hz)",
        device_idx if device_idx is not None else "oletus",
        stream_rate,
        sample_rate,
    )
    return sd.InputStream(
        device=device_idx,
        samplerate=stream_rate,
        channels=1,
        dtype="float32",
        blocksize=stream_block,
        callback=_callback,
    )


class AudioListener:
    """Kaappaa mikrofonin ääntä taustasäikeessä, leikkaa puheen VAD:lla ja kutsuu STT:tä."""

    def __init__(
        self,
        transcriber: TranscriberProtocol,
        on_utterance: UtteranceCallback,
        on_error: ErrorCallback | None = None,
        on_processing: ProcessingCallback | None = None,
        on_ready: ReadyCallback | None = None,
        on_candidates: CandidatesCallback | None = None,
        vad_config: VadConfig | None = None,
        stream_factory: StreamFactory = _default_stream_factory,
    ) -> None:
        self._transcriber = transcriber
        self._on_utterance = on_utterance
        self._on_error = on_error
        self._on_processing = on_processing
        self._on_ready = on_ready
        self._on_candidates = on_candidates
        self._vad = EnergyVadSegmenter(vad_config)
        self._stream_factory = stream_factory

        self._audio_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=QUEUE_MAX_CHUNKS)
        self._stop_event = threading.Event()
        self._muted_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    @property
    def is_muted(self) -> bool:
        return self._muted_event.is_set()

    def set_muted(self, muted: bool) -> None:
        """Mykistää tai poistaa mykistyksen taustakuuntelijalta."""
        if muted:
            self._muted_event.set()
            self._drain_queue()
        else:
            self._muted_event.clear()

    def start(self) -> None:
        """Käynnistää taustakuuntelusäikeen, jos se ei ole jo käynnissä."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._drain_queue()
        self._vad.reset()
        self._worker_thread = threading.Thread(
            target=self._run_worker,
            name="puhis-audio-listener",
            daemon=True,
        )
        self._worker_thread.start()

    def stop(self) -> None:
        """Pysäyttää taustakuuntelusäikeen hallitusti ja vapauttaa mikrofonin."""
        self._stop_event.set()
        try:
            self._audio_queue.put_nowait(None)
        except queue.Full:
            pass

        thread = self._worker_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=STOP_JOIN_TIMEOUT_S)
            if thread.is_alive():
                logger.warning("Taustakuuntelusäie ei pysähtynyt määräajassa")
        self._worker_thread = None

    def enqueue_audio(self, samples: np.ndarray) -> None:
        """Lisää äänipuskurin käsittelyjonoon (käytetään äänivirrasta ja yksikkötesteistä)."""
        if self._stop_event.is_set() or self._muted_event.is_set():
            return
        try:
            self._audio_queue.put_nowait(np.asarray(samples, dtype=np.float32))
        except queue.Full:
            logger.debug("Äänipuskurijono täynnä, pudotetaan kehys")

    def _run_worker(self) -> None:
        sample_rate = self._vad.config.sample_rate
        block_size = self._vad.config.frame_samples
        try:
            load_fn = getattr(self._transcriber, "load_model", None)
            if callable(load_fn):
                load_fn()
            if self._stop_event.is_set():
                return

            with self._stream_factory(sample_rate, block_size, self.enqueue_audio):
                logger.info("Mikrofonikuuntelu käynnistyi (%d Hz)", sample_rate)
                if self._on_ready is not None:
                    self._on_ready()
                self._process_loop(sample_rate)
        except Exception as exc:
            logger.exception("Mikrofonikuuntelun käynnistys tai ajo epäonnistui")
            if self._on_error is not None:
                self._on_error(f"Mikrofonivirhe: {exc}")

    def _process_loop(self, sample_rate: int) -> None:
        while not self._stop_event.is_set():
            try:
                chunk = self._audio_queue.get(timeout=WORKER_POLL_TIMEOUT_S)
            except queue.Empty:
                continue

            if chunk is None:
                break

            if self._muted_event.is_set():
                self._vad.reset()
                continue

            segments = self._vad.feed(chunk)
            for segment in segments:
                if self._stop_event.is_set() or self._muted_event.is_set():
                    break
                self._transcribe_and_emit(segment, sample_rate)
                if self._audio_queue.qsize() > MAX_BACKLOG_CHUNKS:
                    logger.debug("Tyhjennetään tunnistuksen aikana kertynyt äänijono")
                    self._drain_queue()
                    self._vad.reset()
                    break

    def _transcribe_and_emit(self, segment: np.ndarray, sample_rate: int) -> None:
        duration_s = segment.size / max(1, sample_rate)
        rms = compute_rms(segment)
        logger.debug("Puhejakso havaittu (%.1f s, rms=%.4f), tunnistetaan...", duration_s, rms)
        if self._on_processing is not None:
            self._on_processing(True)
        try:
            cand_fn = getattr(self._transcriber, "transcribe_candidates", None)
            if callable(cand_fn):
                candidates = [
                    str(item).strip()
                    for item in cand_fn(segment, sample_rate=sample_rate)
                    if str(item).strip()
                ]
            else:
                single = self._transcriber.transcribe(segment, sample_rate=sample_rate).strip()
                candidates = [single] if single else []
        except Exception as exc:
            logger.exception("Puheentunnistus epäonnistui")
            if self._on_processing is not None:
                self._on_processing(False)
            if self._on_error is not None:
                self._on_error(f"Puheentunnistusvirhe: {exc}")
            return

        if candidates:
            logger.info("Tunnistettu puhe (%.1f s): %r", duration_s, candidates[0])
            if self._on_candidates is not None:
                self._on_candidates(candidates)
            else:
                self._on_utterance(candidates[0])
        elif self._on_processing is not None:
            self._on_processing(False)

    def _drain_queue(self) -> None:
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
