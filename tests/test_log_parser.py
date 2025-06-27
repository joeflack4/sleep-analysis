import pandas as pd
import pytest

from sleep_analysis.log_parser import parse_log, compute_weekly_stats, compute_overall_stats


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
