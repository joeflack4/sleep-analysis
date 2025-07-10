import datetime
import math
import re
from typing import Dict, List

import pandas as pd

QUESTION_TO_COLUMN = {
    '1b. What time start winding down?': 'wind_down_start_time',
    '1.2b. What time did you get into bed & commit to sleep?': 'bed_time',
    '6. What time did you wake up?': 'wake_up_time',
    '7. What time did you get out of bed?': 'get_out_of_bed_time',
    '14. If alcohol, how many standard drinks?': 'alcohol_drinks',
}

EXPECTED_TIMES = {
    'wind_down_start_time': datetime.time(2, 50),
    'bed_time': datetime.time(4, 0),
    'wake_up_time': datetime.time(11, 30),
    'get_out_of_bed_time': datetime.time(11, 35),
}

# Time of day considered the start of a new sleep-wake cycle. Times
# earlier than this are treated as belonging to the *next* calendar
# day when computing averages.
EVENING_START = datetime.time(17, 0)
_EVENING_START_MINUTES = EVENING_START.hour * 60 + EVENING_START.minute

_TIME_RE = re.compile(r'^(\d{1,2})(?::(\d{2}))?(am|pm)?$', re.IGNORECASE)


def _parse_time(value: str) -> datetime.time | None:
    if value in {'.', '', None}:
        return None
    value = value.strip()
    try:
        m = _TIME_RE.match(value)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2) or 0)
            ampm = m.group(3)
            if ampm:
                ampm = ampm.lower()
                if ampm == 'pm' and hour != 12:
                    hour += 12
                if ampm == 'am' and hour == 12:
                    hour = 0
            return datetime.time(hour % 24, minute)
        # Fallback to pandas to_datetime
        t = pd.to_datetime(value).time()
        return t
    except Exception:
        return None


def _parse_duration(value: str) -> float | None:
    """Parse duration like '7:31' as hours."""
    if value in {'.', '', None}:
        return None
    value = value.strip()
    # If the value looks like a time of day with am/pm, interpret it as hours
    # since midnight rather than failing with a ValueError. This allows values
    # such as ``9:42pm`` to be parsed even when they were not recognised as
    # time fields by the caller.
    m = _TIME_RE.match(value)
    if m and m.group(3):  # has am/pm
        t = _parse_time(value)
        if t is not None:
            return t.hour + t.minute / 60
    parts = value.split(':')
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        h, m = parts
        return int(h) + int(m) / 60
    try:
        return float(value)
    except ValueError:
        return None


def _avg_time(times: List[datetime.time]) -> datetime.time | None:
    """Return the circular mean of the given times of day."""
    times = [t for t in times if t is not None]
    if not times:
        return None
    angles = [
        2 * math.pi * (((t.hour * 60 + t.minute) - _EVENING_START_MINUTES) % 1440) / 1440
        for t in times
    ]
    avg_x = sum(math.cos(a) for a in angles) / len(angles)
    avg_y = sum(math.sin(a) for a in angles) / len(angles)
    avg_angle = math.atan2(avg_y, avg_x)
    if avg_angle < 0:
        avg_angle += 2 * math.pi
    avg_minutes = (_EVENING_START_MINUTES + (avg_angle / (2 * math.pi)) * 1440) % 1440
    hour = int(avg_minutes // 60)
    minute = int(avg_minutes % 60)
    return datetime.time(hour, minute)


def _avg_offset(times: List[datetime.time], expected: datetime.time) -> float | None:
    """Return the average absolute deviation from ``expected`` in minutes."""
    times = [t for t in times if t is not None]
    if not times:
        return None
    exp_angle = 2 * math.pi * (((expected.hour * 60 + expected.minute) - _EVENING_START_MINUTES) % 1440) / 1440
    diffs = []
    for t in times:
        angle = 2 * math.pi * (((t.hour * 60 + t.minute) - _EVENING_START_MINUTES) % 1440) / 1440
        diff_angle = math.atan2(math.sin(angle - exp_angle), math.cos(angle - exp_angle))
        diffs.append(abs(diff_angle / (2 * math.pi) * 1440))
    return sum(diffs) / len(diffs)


def _parse_week_header(line: str) -> tuple[str, List[datetime.date]] | None:
    """Parse a week header line.

    The log sometimes prefixes the month/day pairs with a day-of-week, e.g.
    ``"Fri4/25-Wed4/30"``.  The previous implementation expected the day of
    week to be absent which caused a failure to match and resulted in an empty
    dataframe.  This version extracts all numbers from the line and interprets
    them as month/day pairs.
    """

    line = line.strip()
    nums = [int(n) for n in re.findall(r"\d+", line)]
    if len(nums) < 3:
        return None

    sm, sd = nums[0], nums[1]
    if len(nums) >= 4:
        em, ed = nums[2], nums[3]
    else:
        em, ed = sm, nums[2]

    year = 2025
    start = datetime.date(year, sm, sd)
    end = datetime.date(year, em, ed)
    # number of days in the range inclusive
    delta = (end - start).days
    if delta < 0:
        # If the end date wraps to the next month, assume it is within the same
        # year and add a month rollover
        # Example: "12/30-01/04" -> end month < start month
        end = datetime.date(year + (1 if em < sm else 0), em, ed)
        delta = (end - start).days
    days = [start + datetime.timedelta(days=i) for i in range(delta + 1)]
    label = f"{start.month:02d}{start.day:02d}-{em:02d}{ed:02d}"
    return label, days


def parse_log(path: str) -> pd.DataFrame:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    records: List[Dict] = []
    week_label = None
    week_days: List[datetime.date] = []
    week_data: Dict[str, List] = {}

    for raw_line in lines:
        line = raw_line.rstrip('\n')
        if not line.strip() or line.strip().startswith('...'):
            continue
        expanded = line.replace('\t', '    ')
        indent = len(expanded) - len(expanded.lstrip(' '))
        stripped = line.strip()
        if indent == 4:  # week header
            if week_label and week_days:
                # flush previous week
                for i, day in enumerate(week_days):
                    record = {'date': day, 'week_label': week_label}
                    for q, values in week_data.items():
                        if i < len(values):
                            record[q] = values[i]
                    bed = record.get('bed_time')
                    if isinstance(bed, datetime.time) and bed < EVENING_START:
                        record['date_real'] = day + datetime.timedelta(days=1)
                    else:
                        record['date_real'] = day
                    records.append(record)
                week_data = {}
            res = _parse_week_header(stripped)
            if res:
                week_label, week_days = res
            else:
                week_label = None
                week_days = []
        elif indent == 8 and week_label:
            if '?' in stripped:
                q_part, values_part = stripped.split('?', 1)
                question = (q_part + '?').strip()
                values = values_part.strip().split()
                col = QUESTION_TO_COLUMN.get(question)
                parsed_vals = []
                for v in values:
                    if col and 'time' in col:
                        parsed_vals.append(_parse_time(v))
                    elif col == 'alcohol_drinks':
                        parsed_vals.append(float(v) if v != '.' else 0.0)
                    else:
                        # generic: try duration or float
                        val = _parse_duration(v)
                        if val is None:
                            try:
                                val = float(v)
                            except ValueError:
                                val = None
                        parsed_vals.append(val)
                if col:
                    week_data.setdefault(col, parsed_vals)
        else:
            # deeper indents are notes -> ignore
            continue

    if week_label and week_days:
        for i, day in enumerate(week_days):
            record = {'date': day, 'week_label': week_label}
            for q, values in week_data.items():
                if i < len(values):
                    record[q] = values[i]
            bed = record.get('bed_time')
            if isinstance(bed, datetime.time) and bed < EVENING_START:
                record['date_real'] = day + datetime.timedelta(days=1)
            else:
                record['date_real'] = day
            records.append(record)

    df = pd.DataFrame(records)
    # Detect duplicate dates which would indicate a parsing bug in the log.
    if len(df):
        seen = set()
        dup_set = set()
        for d in df['date']:
            if d in seen:
                dup_set.add(d)
            else:
                seen.add(d)
        if dup_set:
            raise ValueError(
                f"Duplicate dates found in log: {sorted(dup_set)}"
            )

    return df


def compute_weekly_stats(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    weekly_dfs = {}
    if df.empty or 'week_label' not in df.columns:
        return weekly_dfs
    for label, wk_df in df.groupby('week_label'):
        stats: Dict[str, List] = {}
        stats['total_drinks'] = [wk_df.get('alcohol_drinks', pd.Series(dtype=float)).fillna(0).sum()]
        for col in ['wind_down_start_time', 'bed_time', 'wake_up_time', 'get_out_of_bed_time']:
            times = wk_df[col].dropna().tolist() if col in wk_df else []
            avg_t = _avg_time(times)
            if avg_t:
                stats[f'avg_{col}'] = [avg_t.strftime('%H:%M')]
                off = _avg_offset(times, EXPECTED_TIMES[col])
                stats[f'avg_offset_{col}'] = [off]
        week_stats_df = pd.DataFrame(stats)
        weekly_dfs[label] = week_stats_df
    return weekly_dfs


def compute_overall_stats(weekly_stats: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    if not weekly_stats:
        return pd.DataFrame()
    combined = pd.concat(weekly_stats.values(), ignore_index=True)
    numeric_cols = combined.select_dtypes(include='number').columns
    time_cols = []
    if not combined.empty:
        for c in combined.columns:
            if c.startswith('avg_') and combined[c].dtype == object:
                first = next((v for v in combined[c] if v is not None), None)
                if isinstance(first, str) and ':' in first:
                    time_cols.append(c)
    overall = {}
    for col in numeric_cols:
        overall[col] = combined[col].mean()
    for col in time_cols:
        times = [pd.to_datetime(t).time() for t in combined[col] if isinstance(t, str)]
        avg_t = _avg_time(times)
        if avg_t:
            overall[col] = avg_t.strftime('%H:%M')
    return pd.DataFrame([overall])

