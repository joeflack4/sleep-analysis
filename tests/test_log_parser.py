import unittest
import sys
import types

import pandas as pd
import pytest

from sleep_analysis.log_parser import parse_log, compute_weekly_stats, compute_overall_stats, _parse_duration

# Provide a minimal pandas stub so the module can be imported without the real
# dependency when running in constrained environments.
pd_stub = types.ModuleType("pandas")
pd_stub.to_datetime = lambda x: None
pd_stub.DataFrame = object
sys.modules.setdefault("pandas", pd_stub)


class TestParseDuration(unittest.TestCase):
    def test_parse_duration_basic(self):
        self.assertAlmostEqual(_parse_duration('7:30'), 7.5)
        self.assertEqual(_parse_duration('8'), 8.0)

    def test_parse_duration_with_am_pm(self):
        self.assertAlmostEqual(_parse_duration('9:15pm'), 21.25)
        self.assertAlmostEqual(_parse_duration('12:05am'), 0.0833333, places=5)

@pytest.fixture

def sample_log_path():
    return 'tests/input/logs.txt'


def test_parse_log(sample_log_path):
    df = parse_log(sample_log_path)
    assert len(df) == 14
    assert set(df['week_label']) == {'0101-0107', '0108-0114'}
    assert df['wind_down_start_time'].notna().all()


def test_compute_weekly_stats(sample_log_path):
    df = parse_log(sample_log_path)
    weekly = compute_weekly_stats(df)
    assert set(weekly.keys()) == {'0101-0107', '0108-0114'}
    assert weekly['0101-0107']['total_drinks'].iloc[0] == 3
    assert weekly['0108-0114']['total_drinks'].iloc[0] == 7


def test_compute_overall_stats(sample_log_path):
    df = parse_log(sample_log_path)
    weekly = compute_weekly_stats(df)
    overall = compute_overall_stats(weekly)
    assert len(overall) == 1
    assert overall['total_drinks'].iloc[0] == pytest.approx((3 + 7) / 2)
