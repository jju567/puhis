import math
import unittest

from puhis.core.eye_math import pupil_offset


class PupilOffsetTests(unittest.TestCase):
    def test_target_at_eye_center_returns_zero(self) -> None:
        self.assertEqual(pupil_offset(10, 10, 10, 10, max_offset=5), (0.0, 0.0))

    def test_far_target_is_clamped_to_max_offset(self) -> None:
        ox, oy = pupil_offset(0, 0, 1000, 1000, max_offset=4)

        self.assertAlmostEqual(math.hypot(ox, oy), 4.0)
        self.assertAlmostEqual(ox, oy)

    def test_directions_follow_target(self) -> None:
        cases = {
            "oikea": ((500, 0), (1, 0)),
            "vasen": ((-500, 0), (-1, 0)),
            "alas": ((0, 500), (0, 1)),
            "ylös": ((0, -500), (0, -1)),
        }
        for name, ((tx, ty), (ex, ey)) in cases.items():
            with self.subTest(suunta=name):
                ox, oy = pupil_offset(0, 0, tx, ty, max_offset=3)
                self.assertAlmostEqual(ox, ex * 3)
                self.assertAlmostEqual(oy, ey * 3)

    def test_near_target_scales_linearly(self) -> None:
        ox, oy = pupil_offset(0, 0, 50, 0, max_offset=6, follow_distance=100)

        self.assertAlmostEqual(ox, 3.0)
        self.assertAlmostEqual(oy, 0.0)

    def test_zero_max_offset_keeps_pupil_centered(self) -> None:
        self.assertEqual(pupil_offset(0, 0, 100, 100, max_offset=0), (0.0, 0.0))

    def test_invalid_arguments_raise_value_error(self) -> None:
        with self.assertRaises(ValueError):
            pupil_offset(0, 0, 1, 1, max_offset=-1)
        with self.assertRaises(ValueError):
            pupil_offset(0, 0, 1, 1, max_offset=1, follow_distance=0)


if __name__ == "__main__":
    unittest.main()
