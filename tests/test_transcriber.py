from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any
import unittest

import numpy as np

from puhis.core.config_store import AppConfig, SttEngine
from puhis.stt.transcriber import (
    FasterWhisperTranscriber,
    GoogleWebSpeechTranscriber,
    SwitchableTranscriber,
    _extract_google_alternatives,
    build_initial_prompt,
)


@dataclass(frozen=True, slots=True)
class _FakeSegment:
    text: str
    no_speech_prob: float = 0.05


class _FakeModel:
    def __init__(self, segments: list[_FakeSegment]) -> None:
        self.segments = segments
        self.calls: list[dict[str, Any]] = []

    def transcribe(self, audio: np.ndarray, **kwargs: Any) -> tuple[list[_FakeSegment], object]:
        self.calls.append({"samples": audio.size, **kwargs})
        return self.segments, object()


class TranscriberTests(unittest.TestCase):
    def test_build_initial_prompt_includes_wake_word_commands_and_keywords(self) -> None:
        config = AppConfig(wake_word="kissa")
        prompt = build_initial_prompt(config)

        self.assertIn("kissa", prompt)
        self.assertIn("save t1", prompt)
        self.assertIn("pilkku", prompt)
        self.assertIn("laskin", prompt)

    def test_transcribe_loads_model_lazily_and_joins_segments(self) -> None:
        fake_model = _FakeModel([
            _FakeSegment(text=" moi pilkku "),
            _FakeSegment(text="maailma enter "),
        ])
        factory_calls: list[tuple[Any, ...]] = []

        def fake_factory(*args: Any) -> _FakeModel:
            factory_calls.append(args)
            return fake_model

        with tempfile.TemporaryDirectory() as tmp:
            transcriber = FasterWhisperTranscriber(
                model_size="small",
                download_root=Path(tmp),
                initial_prompt="puhis, pilkku, enter",
                model_factory=fake_factory,
            )
            self.assertFalse(transcriber.is_loaded)

            audio = np.ones(1600, dtype=np.float32) * 0.1
            result = transcriber.transcribe(audio)

            self.assertTrue(transcriber.is_loaded)
            self.assertEqual(len(factory_calls), 1)
            self.assertEqual(result, "moi pilkku maailma enter")
            self.assertEqual(fake_model.calls[0]["initial_prompt"], "puhis, pilkku, enter")

    def test_transcribe_filters_out_high_no_speech_probability_segments(self) -> None:
        fake_model = _FakeModel([
            _FakeSegment(text="Kiitos.", no_speech_prob=0.92),
            _FakeSegment(text="puhis t1", no_speech_prob=0.10),
        ])
        transcriber = FasterWhisperTranscriber(model_factory=lambda *_args: fake_model)

        text = transcriber.transcribe(np.ones(800, dtype=np.float32))

        self.assertEqual(text, "puhis t1")

    def test_transcribe_empty_audio_returns_empty_without_loading_model(self) -> None:
        called = False

        def fail_factory(*_args: Any) -> object:
            nonlocal called
            called = True
            return object()

        transcriber = FasterWhisperTranscriber(model_factory=fail_factory)
        self.assertEqual(transcriber.transcribe(np.empty(0, dtype=np.float32)), "")
        self.assertFalse(called)

    def test_transcribe_wrong_sample_rate_raises_value_error(self) -> None:
        transcriber = FasterWhisperTranscriber(model_factory=lambda *_args: _FakeModel([]))
        with self.assertRaises(ValueError):
            transcriber.transcribe(np.ones(100, dtype=np.float32), sample_rate=44_100)

    def test_google_web_speech_transcriber_converts_float32_to_pcm16(self) -> None:
        captured: list[tuple[int, int, str]] = []

        def fake_recognize(pcm_bytes: bytes, sr: int, lang: str) -> str:
            captured.append((len(pcm_bytes), sr, lang))
            return "  puhis avaa laskin "

        web = GoogleWebSpeechTranscriber(recognize_fn=fake_recognize)
        audio = np.ones(800, dtype=np.float32) * 0.2
        result = web.transcribe(audio, sample_rate=16_000)

        self.assertEqual(result, "puhis avaa laskin")
        self.assertEqual(captured, [(1600, 16_000, "fi-FI")])

    def test_switchable_transcriber_switches_between_web_and_whisper(self) -> None:
        web = GoogleWebSpeechTranscriber(recognize_fn=lambda _b, _sr, _l: "selain tulos")
        whisper = FasterWhisperTranscriber(
            model_factory=lambda *_args: _FakeModel([_FakeSegment(text="whisper tulos")])
        )
        switcher = SwitchableTranscriber(
            initial_engine=SttEngine.WEB,
            web_transcriber=web,
            whisper_transcriber=whisper,
        )
        audio = np.ones(480, dtype=np.float32) * 0.1

        self.assertEqual(switcher.transcribe(audio), "selain tulos")
        self.assertFalse(whisper.is_loaded)

        switcher.set_engine(SttEngine.WHISPER)
        self.assertIs(switcher.engine, SttEngine.WHISPER)
        self.assertEqual(switcher.transcribe(audio), "whisper tulos")
        self.assertTrue(whisper.is_loaded)

    def test_extract_google_alternatives_returns_unique_transcripts(self) -> None:
        raw = {
            "alternative": [
                {"transcript": "Puhis save Teboil", "confidence": 0.8},
                {"transcript": "Puhis save Depo"},
                {"transcript": "Puhis save Teboil"},
            ]
        }
        self.assertEqual(
            _extract_google_alternatives(raw),
            ["Puhis save Teboil", "Puhis save Depo"],
        )


if __name__ == "__main__":
    unittest.main()
