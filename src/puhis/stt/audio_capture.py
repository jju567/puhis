"""Jatkuva mikrofonin taustakuuntelu (`sounddevice`), VAD-leikkaus ja STT-työsäie."""

from collections.abc import Callable
from contextlib import AbstractContextManager
import logging
import queue
import threading
from typing import Any

import numpy as np

from puhis.stt.transcriber import TranscriberProtocol
from puhis.stt.vad import EnergyVadSegmenter, VadConfig

logger = logging.getLogger(__name__)

QUEUE_MAX_CHUNKS = 256
# Jos jonoon on kertynyt yli ~1 s ääntä tunnistuksen aikana, vanha häntä
# tyhjennetään, jottei CPU jää 100 %:n kuormalla purkamaan jonoa silmukassa.
MAX_BACKLOG_CHUNKS = 35
WORKER_POLL_TIMEOUT_S = 0.1
STOP_JOIN_TIMEOUT_S = 2.0

type UtteranceCallback = Callable[[str], None]
type ErrorCallback = Callable[[str], None]
type StreamFactory = Callable[[int, int, Callable[[np.ndarray], None]], AbstractContextManager[Any]]


def _default_stream_factory(
    sample_rate: int,
    block_size: int,
    on_audio: Callable[[np.ndarray], None],
) -> AbstractContextManager[Any]:
    import sounddevice as sd

    def _callback(indata: np.ndarray, _frames: int, _time_info: Any, status: Any) -> None:
        if status:
            logger.debug("sounddevice-tila: %s", status)
        on_audio(indata[:, 0].copy())

    return sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=block_size,
        callback=_callback,
    )


class AudioListener:
    """Kaappaa mikrofonin ääntä taustasäikeessä, leikkaa puheen VAD:lla ja kutsuu STT:tä."""

    def __init__(
        self,
        transcriber: TranscriberProtocol,
        on_utterance: UtteranceCallback,
        on_error: ErrorCallback | None = None,
        vad_config: VadConfig | None = None,
        stream_factory: StreamFactory = _default_stream_factory,
    ) -> None:
        self._transcriber = transcriber
        self._on_utterance = on_utterance
        self._on_error = on_error
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
        try:
            text = self._transcriber.transcribe(segment, sample_rate=sample_rate).strip()
        except Exception as exc:
            logger.exception("Puheentunnistus epäonnistui")
            if self._on_error is not None:
                self._on_error(f"Puheentunnistusvirhe: {exc}")
            return

        if text:
            logger.info("Tunnistettu puhe: %r", text)
            self._on_utterance(text)

    def _drain_queue(self) -> None:
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
