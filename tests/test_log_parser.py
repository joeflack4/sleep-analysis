import unittest
import sys
import types

# Provide a minimal pandas stub so the module can be imported without the real
# dependency when running in constrained environments.
pd_stub = types.ModuleType("pandas")
pd_stub.to_datetime = lambda x: None
pd_stub.DataFrame = object
sys.modules.setdefault("pandas", pd_stub)

from sleep_analysis.log_parser import _parse_duration

class TestParseDuration(unittest.TestCase):
    def test_parse_duration_basic(self):
        self.assertAlmostEqual(_parse_duration('7:30'), 7.5)
        self.assertEqual(_parse_duration('8'), 8.0)

    def test_parse_duration_with_am_pm(self):
        self.assertAlmostEqual(_parse_duration('9:15pm'), 21.25)
        self.assertAlmostEqual(_parse_duration('12:05am'), 0.0833333, places=5)

if __name__ == '__main__':
    unittest.main()
