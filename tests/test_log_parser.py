import unittest
import sys
import types
import datetime
import os

"""Minimal pandas stub used when the real package isn't available."""

class _Series(list):
    def __init__(self, data=None, dtype=None):
        if data is None:
            data = []
        super().__init__(data)
    def notna(self):
        return _Series([x is not None for x in self])

    def dropna(self):
        return _Series([x for x in self if x is not None])

    def fillna(self, value):
        return _Series([value if x is None else x for x in self])

    def sum(self):
        return sum(x for x in self if x is not None)

    def tolist(self):
        return list(self)

    def mean(self):
        vals = [x for x in self if x is not None]
        return sum(vals) / len(vals) if vals else 0

    def all(self):
        return all(self)

    @property
    def iloc(self):
        class _ILoc:
            def __init__(self, data):
                self.data = data

            def __getitem__(self, idx):
                return self.data[idx]

        return _ILoc(self)

    @property
    def dtype(self):
        for x in self:
            if isinstance(x, (int, float)):
                return float
            if x is not None:
                return object
        return object


class _DataFrame:
    def __init__(self, data):
        if isinstance(data, dict):
            keys = list(data.keys())
            rows = max(len(v) for v in data.values()) if data else 0
            self._rows = [
                {k: data[k][i] if i < len(data[k]) else None for k in keys}
                for i in range(rows)
            ]
        elif isinstance(data, list):
            self._rows = [dict(row) for row in data]
        else:
            self._rows = []

    def __len__(self):
        return len(self._rows)

    def __contains__(self, key):
        return any(key in r for r in self._rows)

    def __getitem__(self, key):
        return _Series([r.get(key) for r in self._rows])

    def get(self, key, default):
        return self[key] if key in self else default

    @property
    def empty(self):
        return len(self._rows) == 0

    @property
    def columns(self):
        cols = []
        for r in self._rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        return cols

    def groupby(self, key):
        groups = {}
        for r in self._rows:
            groups.setdefault(r.get(key), []).append(r)
        for k, rows in groups.items():
            yield k, _DataFrame(rows)

    def select_dtypes(self, include=None):
        if include and (include == 'number' or include == ['number']):
            numeric = []
            for col in self.columns:
                if all(isinstance(r.get(col), (int, float, type(None))) for r in self._rows):
                    numeric.append(col)

            class _Cols(list):
                @property
                def columns(self):
                    return self

            return _Cols(numeric)
        return []

    def to_csv(self, path, sep=',', index=True):
        cols = self.columns
        with open(path, 'w', encoding='utf-8') as f:
            f.write(sep.join(cols) + '\n')
            for r in self._rows:
                f.write(sep.join('' if r.get(c) is None else str(r.get(c)) for c in cols) + '\n')


def _concat(dfs, ignore_index=True):
    rows = []
    for df in dfs:
        rows.extend(df._rows)
    return _DataFrame(rows)


def _to_datetime(val):
    if isinstance(val, datetime.time):
        return datetime.datetime.combine(datetime.date.today(), val)
    for fmt in ("%H:%M", "%I:%M%p", "%H:%M:%S"):
        try:
            return datetime.datetime.strptime(str(val), fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised time format: {val}")


pd_stub = types.ModuleType("pandas")
pd_stub.DataFrame = _DataFrame
pd_stub.Series = _Series
pd_stub.concat = _concat
pd_stub.to_datetime = _to_datetime
sys.modules.setdefault("pandas", pd_stub)

# Ensure the project root is on the import path so ``sleep_analysis`` can be
# imported when tests are executed directly.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd
import pytest

from sleep_analysis.log_parser import (
    parse_log,
    compute_weekly_stats,
    compute_overall_stats,
    _parse_duration,
    _parse_week_header,
) 
from sleep_analysis.__main__ import _format_range


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
    assert 'total_drinks_mean' not in overall.columns
    assert overall['total_drinks_median'].iloc[0] == pytest.approx(5)


def test_compute_weekly_stats_handles_missing_week_label():
    df = pd.DataFrame({'foo': [1, 2]})
    weekly = compute_weekly_stats(df)
    assert weekly == {}


def test_compute_weekly_stats_empty_dataframe():
    df = pd.DataFrame({})
    weekly = compute_weekly_stats(df)
    assert weekly == {}


def test_parse_week_header_partial_week():
    label, days = _parse_week_header('Fri4/25-Wed4/30')
    assert label == '0425-0430'
    assert len(days) == 6
    assert days[0] == datetime.date(2025, 4, 25)
    assert days[-1] == datetime.date(2025, 4, 30)


def test_parse_week_header_cross_year():
    label, days = _parse_week_header('Tue12/30-Mon1/05')
    assert label == '1230-0105'
    assert len(days) == 7
    assert days[0] == datetime.date(2025, 12, 30)
    assert days[-1] == datetime.date(2026, 1, 5)


def test_parse_log_duplicate_dates(tmp_path):
    log = tmp_path / 'log.txt'
    log.write_text(
        '    1/1-1/4\n'
        '        6. What time did you wake up? 7am 7am 7am 7am\n'
        '    1/4-1/7\n'
        '        6. What time did you wake up? 7am 7am 7am 7am\n'
    )
    with pytest.raises(ValueError):
        parse_log(str(log))


def test_single_week_range_label():
    df = parse_log('tests/input/log-single-week.txt')
    assert len(df) == 3
    start = df['date'].iloc[0]
    end = df['date'].iloc[-1]
    label = _format_range(start, end)
    assert label == '2025--06-19--06-21'


def test_parse_log_handles_blank_lines_and_notes(tmp_path):
    log = tmp_path / 'log.txt'
    log.write_text(
        '    Thu6/19-Sat21\n\n'
        '        1b. What time start winding down? 2:20am 2:50am 2:10am\n\n'
        '        1.3b. Wind-down activities (if not reading book)\n'
        '            Day 1: note\n\n'
        '        6. What time did you wake up? 7am 7am 7am\n'
        '            (comment)\n\n'
        '        7. What time did you get out of bed? 7:15am 7:15am 7:15am\n\n'
        '    ...\n'
    )
    df = parse_log(str(log))
    assert len(df) == 3


def test_parse_log_week_header_without_indent():
    df = parse_log('tests/input/long-single-week.txt')
    assert len(df) == 3
    assert set(df['week_label']) == {'0619-0621'}
    assert df['wind_down_start_time'][0] is not None
