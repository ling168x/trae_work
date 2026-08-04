import unittest

from perf_recorder.models import ConfidenceLevel, infer_fps_confidence


class MetricsConfidenceTest(unittest.TestCase):
    def test_high_confidence(self) -> None:
        self.assertEqual(infer_fps_confidence(60.0, 58.5), ConfidenceLevel.HIGH)

    def test_medium_confidence(self) -> None:
        self.assertEqual(infer_fps_confidence(60.0, 54.0), ConfidenceLevel.MEDIUM)

    def test_low_confidence(self) -> None:
        self.assertEqual(infer_fps_confidence(60.0, 40.0), ConfidenceLevel.LOW)

    def test_unknown_confidence(self) -> None:
        self.assertEqual(infer_fps_confidence(None, None), ConfidenceLevel.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
