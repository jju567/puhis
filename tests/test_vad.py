import unittest

import numpy as np

from puhis.stt.vad import EnergyVadSegmenter, VadConfig, compute_rms


class VadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = VadConfig(
            sample_rate=16_000,
            frame_duration_ms=30,
            rms_threshold=0.02,
            pre_roll_ms=90,  # 3 kehystä
            min_speech_ms=90,  # 3 kehystä
            silence_duration_ms=120,  # 4 kehystä
            max_utterance_ms=600,  # 20 kehystä
        )
        self.vad = EnergyVadSegmenter(self.config)
        self.frame_len = self.config.frame_samples

    def test_compute_rms_returns_zero_on_empty_or_silent_frame(self) -> None:
        self.assertEqual(compute_rms(np.empty(0, dtype=np.float32)), 0.0)
        self.assertEqual(compute_rms(np.zeros(480, dtype=np.float32)), 0.0)

    def test_pure_silence_produces_no_segments(self) -> None:
        silence = np.zeros(self.frame_len * 30, dtype=np.float32)

        segments = self.vad.feed(silence)

        self.assertEqual(segments, [])
        self.assertFalse(self.vad.is_speaking)

    def test_short_click_below_min_speech_duration_is_ignored(self) -> None:
        pre_silence = np.zeros(self.frame_len * 5, dtype=np.float32)
        click = np.full(self.frame_len * 1, 0.1, dtype=np.float32)
        post_silence = np.zeros(self.frame_len * 6, dtype=np.float32)

        segments = self.vad.feed(np.concatenate((pre_silence, click, post_silence)))

        self.assertEqual(segments, [])

    def test_speech_followed_by_silence_emits_segment_with_pre_roll(self) -> None:
        pre_silence = np.zeros(self.frame_len * 5, dtype=np.float32)
        speech = np.full(self.frame_len * 5, 0.1, dtype=np.float32)
        post_silence = np.zeros(self.frame_len * 4, dtype=np.float32)

        segments = self.vad.feed(np.concatenate((pre_silence, speech, post_silence)))

        self.assertEqual(len(segments), 1)
        # 3 esipuskurikehystä + 5 puhekehystä + 4 loppuhiljaisuuskehystä = 12 kehystä
        self.assertEqual(segments[0].size, self.frame_len * 12)

    def test_max_utterance_duration_forces_segment_cut(self) -> None:
        continuous_speech = np.full(self.frame_len * 22, 0.1, dtype=np.float32)

        segments = self.vad.feed(continuous_speech)

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].size, self.frame_len * 20)
        # Jatkuva taustamelu nostaa adaptiivista kynnystä, jottei seuraava kehys laukaise uutta jaksoa.
        self.assertGreater(self.vad.effective_threshold, 0.1)

    def test_flush_returns_active_valid_utterance(self) -> None:
        speech = np.full(self.frame_len * 4, 0.1, dtype=np.float32)
        self.assertEqual(self.vad.feed(speech), [])
        self.assertTrue(self.vad.is_speaking)

        flushed = self.vad.flush()

        self.assertIsNotNone(flushed)
        assert flushed is not None
        self.assertEqual(flushed.size, self.frame_len * 4)
        self.assertFalse(self.vad.is_speaking)


if __name__ == "__main__":
    unittest.main()
