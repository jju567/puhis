from collections.abc import Callable, Iterator
from contextlib import contextmanager
import threading
import unittest

import numpy as np

from puhis.stt.audio_capture import AudioListener
from puhis.stt.vad import VadConfig


class _FakeTranscriber:
    def __init__(self, reply: str = "puhis avaa laskin") -> None:
        self.reply = reply
        self.calls = 0

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16_000) -> str:
        self.calls += 1
        return self.reply


class AudioCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vad_config = VadConfig(
            sample_rate=16_000,
            frame_duration_ms=30,
            rms_threshold=0.02,
            pre_roll_ms=30,
            min_speech_ms=60,
            silence_duration_ms=60,
            max_utterance_ms=1000,
        )
        self.frame_len = self.vad_config.frame_samples

    def test_listener_processes_speech_segment_and_stops_cleanly(self) -> None:
        received: list[str] = []
        done = threading.Event()
        ready = threading.Event()
        transcriber = _FakeTranscriber("puhis save t1")

        @contextmanager
        def fake_stream(
            _sr: int,
            _bs: int,
            _on_audio: Callable[[np.ndarray], None],
        ) -> Iterator[object]:
            yield object()

        def on_utterance(text: str) -> None:
            received.append(text)
            done.set()

        listener = AudioListener(
            transcriber=transcriber,
            on_utterance=on_utterance,
            on_ready=ready.set,
            vad_config=self.vad_config,
            stream_factory=fake_stream,
        )
        listener.start()
        try:
            self.assertTrue(ready.wait(timeout=2.0))
            speech = np.full(self.frame_len * 3, 0.1, dtype=np.float32)
            silence = np.zeros(self.frame_len * 3, dtype=np.float32)
            listener.enqueue_audio(np.concatenate((speech, silence)))
            self.assertTrue(done.wait(timeout=2.0))
            self.assertEqual(received, ["puhis save t1"])
        finally:
            listener.stop()

        self.assertFalse(listener.is_running)

    def test_muted_listener_drops_incoming_audio(self) -> None:
        received: list[str] = []
        transcriber = _FakeTranscriber("puhis t1")

        @contextmanager
        def fake_stream(
            _sr: int,
            _bs: int,
            _on_audio: Callable[[np.ndarray], None],
        ) -> Iterator[object]:
            yield object()

        listener = AudioListener(
            transcriber=transcriber,
            on_utterance=received.append,
            vad_config=self.vad_config,
            stream_factory=fake_stream,
        )
        listener.set_muted(True)
        listener.start()
        try:
            speech = np.full(self.frame_len * 4, 0.1, dtype=np.float32)
            silence = np.zeros(self.frame_len * 4, dtype=np.float32)
            listener.enqueue_audio(np.concatenate((speech, silence)))
        finally:
            listener.stop()

        self.assertEqual(transcriber.calls, 0)
        self.assertEqual(received, [])

    def test_stream_open_failure_invokes_on_error_callback(self) -> None:
        errors: list[str] = []
        error_event = threading.Event()

        @contextmanager
        def failing_stream(
            _sr: int,
            _bs: int,
            _on_audio: Callable[[np.ndarray], None],
        ) -> Iterator[object]:
            raise OSError("Mikrofonia ei löytynyt")
            yield object()

        def on_error(msg: str) -> None:
            errors.append(msg)
            error_event.set()

        listener = AudioListener(
            transcriber=_FakeTranscriber(),
            on_utterance=lambda _t: None,
            on_error=on_error,
            vad_config=self.vad_config,
            stream_factory=failing_stream,
        )
        listener.start()
        try:
            self.assertTrue(error_event.wait(timeout=2.0))
            self.assertEqual(len(errors), 1)
            self.assertIn("Mikrofonia ei löytynyt", errors[0])
        finally:
            listener.stop()


if __name__ == "__main__":
    unittest.main()
