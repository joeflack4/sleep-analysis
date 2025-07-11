import datetime
import math
import re
import os
import csv
from typing import Dict, List, Iterable

import pandas as pd

QUESTION_TO_COLUMN = {
    '1b. What time start winding down?': 'wind_down_start_time',
    '1.2b. What time did you get into bed & commit to sleep?': 'bed_time',
    '2. How long do you estimate it took to fall asleep (minutes)?': 'fall_asleep_minutes',
    '3. How many times did you wake up during the night?': 'night_wake_ups',
    '4. In total, how long did these awakenings last (minutes)?': 'awake_minutes',
    '5. When awake during the night, how long did you spend out of bed (minutes)?': 'out_of_bed_minutes',
    '6. What time did you wake up?': 'wake_up_time',
    '7. What time did you get out of bed?': 'get_out_of_bed_time',
    '8. In TOTAL, how many hours of sleep did you get?': 'sleep_hours',
    '9. In TOTAL, how many hours did you spend in bed?': 'bed_hours',
    '10. Quality of your sleep (1-10)?': 'sleep_quality',
    '11. Did you take naps during the day?': 'naps',
    '12. Mood during the day (1-10)?': 'mood',
    '13. Fatigue level during the day (1-10)?': 'fatigue',
    '14. If alcohol, how many standard drinks?': 'alcohol_drinks',
    '15. - what type?': 'alcohol_type',
    '16. - what time?': 'alcohol_time',
    '17. Second wind?': 'second_wind',
}

# Reverse lookup used when exporting per-week CSVs from a dataframe
COLUMN_TO_QUESTION = {v: k for k, v in QUESTION_TO_COLUMN.items()}

TIME_COLS = [
    'wind_down_start_time',
    'bed_time',
    'wake_up_time',
    'get_out_of_bed_time',
]

NUMERIC_COLS = [
    'fall_asleep_minutes',
    'night_wake_ups',
    'awake_minutes',
    'out_of_bed_minutes',
    'sleep_hours',
    'bed_hours',
    'sleep_quality',
    'naps',
    'mood',
    'fatigue',
    'alcohol_drinks',
]

STRING_COLS = ['alcohol_type', 'alcohol_time', 'second_wind']

EXPECTED_TIMES = {
    'wind_down_start_time': datetime.time(2, 50),
    'bed_time': datetime.time(4, 0),
    'wake_up_time': datetime.time(11, 30),
    'get_out_of_bed_time': datetime.time(11, 35),
}

_TIME_RE = re.compile(r'^(\d{1,2})(?::(\d{2}))?(am|pm)?$', re.IGNORECASE)

# Matches week header lines such as ``"Fri4/25-Wed4/30"`` or ``"Thu6/19-Wed25"``
# where the day-of-week prefix is optional for both the start and end dates. The
# month/day pairs may also omit the month on the end date in which case the
# start month is assumed.
_WEEK_HEADER_RE = re.compile(
    r'^(?:[A-Za-z]{3})?\d{1,2}/\d{1,2}-'
    r'(?:[A-Za-z]{3})?(?:\d{1,2}/)?\d{1,2}$'
)


def _parse_time(value: str) -> datetime.time | None:
    """Return ``datetime.time`` parsed from ``value`` or ``None`` on failure."""

    if value in {'.', '', None}:
        return None

    value = value.strip()

    try:
        m = _TIME_RE.match(value)
        if m:
            # Basic ``hh:mm`` with optional ``am``/``pm`` handling
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

        # Fall back to ``pandas.to_datetime`` if regex parsing failed
        t = pd.to_datetime(value).time()
        return t
    except Exception:
        # Any parsing failure results in ``None``
        return None


def _parse_duration(value: str) -> float | None:
    """Return number of hours represented by ``value`` or ``None``."""

    if value in {'.', '', None}:
        return None

    value = value.strip()

    # Interpret values containing ``am``/``pm`` as a time-of-day offset
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
    """
    Return the circular (clock‐aware) mean of a list of datetime.time objects.

    This handles the “wrap‐around” at midnight correctly by treating times
    as points on the unit circle:

    1. Filter out any None entries.
    2. Convert each time to total minutes since midnight.
    3. Map minutes → angle on the circle (0 to 2π).
    4. Compute the average vector by summing sine and cosine components.
       - sin_sum = ∑ sin(angle_i)
       - cos_sum = ∑ cos(angle_i)
    5. If both sums are zero, the mean is undefined (e.g., evenly opposite times).
    6. Compute the mean angle = atan2(sin_sum / n, cos_sum / n).
       - atan2 handles correct quadrant.
    7. Normalize negative angles by adding 2π.
    8. Convert mean angle back to minutes, then to hour and minute.
    9. Round minutes; carry over if rounding hits 60.

    Returns:
        A datetime.time representing the circular average, or None if
        the list is empty or the mean is undefined.
    """

    # 1. Remove None values
    times = [t for t in times if t is not None]
    if not times:
        return None

    # 2 & 3. Build list of angles (radians) for each time
    angles = []
    for t in times:
        total_minutes = t.hour * 60 + t.minute
        # Scale minutes to fraction of full day (24*60), then to radians
        angle = (total_minutes / (24 * 60)) * 2 * math.pi
        angles.append(angle)

    # 4. Sum up sine and cosine components
    sin_sum = sum(math.sin(a) for a in angles)
    cos_sum = sum(math.cos(a) for a in angles)

    # 5. If the resultant vector is zero, mean is undefined
    if sin_sum == 0 and cos_sum == 0:
        return None

    # 6. Compute mean angle (divide by count for true average vector)
    mean_angle = math.atan2(sin_sum / len(angles), cos_sum / len(angles))
    # 7. Normalize to [0, 2π)
    if mean_angle < 0:
        mean_angle += 2 * math.pi

    # 8. Convert back to total minutes, then hours and minutes
    mean_total_minutes = (mean_angle * (24 * 60)) / (2 * math.pi)
    hour = int(mean_total_minutes // 60) % 24
    minute = int(round(mean_total_minutes % 60))

    # 9. Handle rounding up to next hour
    if minute == 60:
        hour = (hour + 1) % 24
        minute = 0

    return datetime.time(hour, minute)

def _median(values: List[float]) -> float | None:
    """Return the median of ``values`` ignoring ``None`` entries."""

    values = sorted(v for v in values if v is not None)
    if not values:
        return None

    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def _median_time(times: List[datetime.time]) -> datetime.time | None:
    """Return the median time from ``times``."""

    minutes = [t.hour * 60 + t.minute for t in times if t is not None]
    med = _median(minutes)
    if med is None:
        return None
    hour = int(med // 60) % 24
    minute = int(med % 60)
    return datetime.time(hour, minute)


def _std(values: List[float]) -> float | None:
    """Return standard deviation of ``values`` ignoring ``None``."""

    values = [v for v in values if v is not None]
    if not values:
        return None

    mean_val = sum(values) / len(values)
    var = sum((v - mean_val) ** 2 for v in values) / len(values)
    return math.sqrt(var)


def _std_time(times: List[datetime.time]) -> float | None:
    """Return standard deviation in minutes of ``times``."""

    minutes = [t.hour * 60 + t.minute for t in times if t is not None]
    return _std(minutes)


def _avg_offset(times: List[datetime.time], expected: datetime.time) -> float | None:
    """Average absolute offset from ``expected`` in minutes using circular distance."""

    times = [t for t in times if t is not None]
    if not times:
        return None

    exp_minutes = expected.hour * 60 + expected.minute

    def _circ_diff(m: int) -> int:
        diff = abs(m - exp_minutes) % (24 * 60)
        if diff > 12 * 60:
            diff = 24 * 60 - diff
        return diff

    diffs = [_circ_diff(t.hour * 60 + t.minute) for t in times]
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
    nums: list[int] = [int(n) for n in re.findall(r"\d+", line)]
    if len(nums) < 3:
        return None

    sm: int
    sd: int
    em: int
    ed: int
    sm, sd = nums[0], nums[1]
    if len(nums) >= 4:
        em, ed = nums[2], nums[3]
    else:
        em, ed = sm, nums[2]

    year: int = 2025
    start: datetime.date = datetime.date(year, sm, sd)
    end: datetime.date = datetime.date(year, em, ed)
    # number of days in the range inclusive
    delta: int = (end - start).days
    if delta < 0:
        # If the end date wraps to the next month, assume it is within the same
        # year and add a month rollover
        # Example: "12/30-01/04" -> end month < start month
        end = datetime.date(year + (1 if em < sm else 0), em, ed)
        delta = (end - start).days
    days: list[datetime.date] = [start + datetime.timedelta(days=i) for i in range(delta + 1)]
    label: str = f"{start.month:02d}{start.day:02d}-{em:02d}{ed:02d}"
    return label, days


def parse_log(path: str) -> pd.DataFrame:
    """Parse a sleep log text file and return a dataframe of daily records."""

    with open(path, 'r', encoding='utf-8') as f:
        lines: list[str] = f.readlines()

    # ``records`` accumulates a dictionary per day which becomes our dataframe
    records: list[dict] = []

    # tracking variables for the current week block
    week_label: str | None = None
    week_days: list[datetime.date] = []
    week_data: dict[str, list] = {}

    # iterate over every line in the log
    for raw_line in lines:
        line = raw_line.rstrip('\n')

        if not line.strip() or line.strip().startswith('...'):
            # skip blank lines and divider rows
            continue

        expanded = line.replace('\t', '    ')
        indent = len(expanded) - len(expanded.lstrip(' '))
        stripped = line.strip()

        if _WEEK_HEADER_RE.match(stripped):  # week header
            if week_label and week_days:
                # flush the previous week's accumulated data
                for i, day in enumerate(week_days):
                    record: dict[str, object] = {'date': day, 'week_label': week_label}
                    for q, values in week_data.items():
                        if i < len(values):
                            record[q] = values[i]
                    records.append(record)
                week_data = {}

            res = _parse_week_header(stripped)
            if res:
                week_label, week_days = res
            else:
                week_label = None
                week_days = []
        elif indent >= 4 and week_label:
            if '?' in stripped:
                # question line containing data for the current week
                q_part, values_part = stripped.split('?', 1)
                question = (q_part + '?').strip()
                values: list[str] = values_part.strip().split()
                col = QUESTION_TO_COLUMN.get(question)
                parsed_vals: list = []

                # parse each value for the question column
                for v in values:
                    if col in TIME_COLS:
                        parsed_vals.append(_parse_time(v))
                    elif col in STRING_COLS:
                        parsed_vals.append(None if v == '.' else v)
                    elif col == 'alcohol_drinks':
                        parsed_vals.append(float(v) if v != '.' else 0.0)
                    else:
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
        # flush the final week after processing all lines
        for i, day in enumerate(week_days):
            record: dict[str, object] = {'date': day, 'week_label': week_label}
            for q, values in week_data.items():
                if i < len(values):
                    record[q] = values[i]
            records.append(record)

    df = pd.DataFrame(records)

    # Detect duplicate dates which would indicate a parsing bug in the log
    if len(df):
        seen: set[datetime.date] = set()
        dup_set: set[datetime.date] = set()
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
    """Return per-week statistics grouped by ``week_label``."""

    weekly_dfs: dict[str, pd.DataFrame] = {}
    if df.empty or 'week_label' not in df.columns:
        return weekly_dfs

    # iterate over each week block in the dataframe
    for label, wk_df in df.groupby('week_label'):
        stats: dict[str, list] = {}

        # total number of alcoholic drinks for the week
        stats['total_drinks'] = [wk_df.get('alcohol_drinks', pd.Series(dtype=float)).fillna(0).sum()]

        for col in TIME_COLS:
            times: list[datetime.time] = wk_df[col].dropna().tolist() if col in wk_df else []
            avg_t: datetime.time | None = _avg_time(times) if times else None
            med_t: datetime.time | None = _median_time(times) if times else None
            std_t = _std_time(times) if times else None

            stats[f'{col}_avg'] = [avg_t.strftime('%I:%M%p').lower() if avg_t else None]
            stats[f'{col}_median'] = [med_t.strftime('%I:%M%p').lower() if med_t else None]
            stats[f'{col}_std'] = [std_t]

            offsets: list[int] = []
            if times:
                for t in times:
                    diff = abs((t.hour * 60 + t.minute) - (EXPECTED_TIMES[col].hour * 60 + EXPECTED_TIMES[col].minute)) % (24 * 60)
                    if diff > 12 * 60:
                        diff = 24 * 60 - diff
                    offsets.append(diff)
            avg_off: float | None = sum(offsets) / len(offsets) if offsets else None
            med_off = _median(offsets) if offsets else None
            std_off = _std(offsets) if offsets else None
            stats[f'{col}_offset_avg'] = [avg_off]
            stats[f'{col}_offset_median'] = [med_off]
            stats[f'{col}_offset_std'] = [std_off]

        for col in NUMERIC_COLS:
            vals: list[float] = wk_df[col].dropna().tolist() if col in wk_df else []
            avg_val: float | None = sum(vals) / len(vals) if vals else None
            med_val = _median(vals) if vals else None
            std_val = _std(vals) if vals else None
            stats[f'{col}_avg'] = [avg_val]
            stats[f'{col}_median'] = [med_val]
            stats[f'{col}_std'] = [std_val]

        week_stats_df = pd.DataFrame(stats)
        weekly_dfs[label] = week_stats_df

    return weekly_dfs


def _filter_non_empty_frames(frames: Iterable[pd.DataFrame]) -> list[pd.DataFrame]:
    """Return frames that are not completely empty or all ``NaN``."""

    valid: list[pd.DataFrame] = []
    for df in frames:
        try:
            empty_df = df.dropna(how="all").empty
        except Exception:
            empty_df = df.empty or all(
                all(val is None for val in df[col]) for col in df.columns
            )
        if not empty_df:
            valid.append(df)
    return valid


def compute_overall_stats(weekly_stats: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Aggregate ``weekly_stats`` into a single overall statistics dataframe."""

    if not weekly_stats:
        return pd.DataFrame()

    valid_stats = _filter_non_empty_frames(weekly_stats.values())

    if not valid_stats:
        return pd.DataFrame()

    combined: pd.DataFrame = pd.concat(valid_stats, ignore_index=True)
    numeric_cols = combined.select_dtypes(include='number').columns
    time_cols: list[str] = []

    if not combined.empty:
        for c in combined.columns:
            if combined[c].dtype == object:
                first = next((v for v in combined[c] if isinstance(v, str) and ':' in v), None)
                if first is not None:
                    time_cols.append(c)

    overall: dict[str, float | str] = {}

    for col in numeric_cols:
        values: list[float] = [v for v in combined[col] if v is not None]
        mean_val: float | None = sum(values) / len(values) if values else None
        overall[col] = mean_val

    if 'total_drinks' in combined.columns:
        vals = [v for v in combined['total_drinks'] if v is not None]
        overall['total_drinks_median'] = _median(vals) if vals else None

    # time columns
    for col in time_cols:
        times: list[datetime.time] = [
            pd.to_datetime(t).time() for t in combined[col] if isinstance(t, str)
        ]
        if times:
            avg_t: datetime.time | None = _avg_time(times)
            if avg_t:
                overall[col] = avg_t.strftime('%I:%M%p').lower()

    return pd.DataFrame([overall])


def _prepare_stats_for_output(df: pd.DataFrame, label_col: str | None = None) -> pd.DataFrame:
    """Return ``df`` in vertical layout with rounded numeric values."""
    if df.empty:
        return df

    def _round(v: object) -> object:
        if isinstance(v, float):
            try:
                return float(f"{v:.3g}")
            except Exception:
                return v
        return v

    if label_col and label_col in df.columns:
        rows = []
        for _, r in df.iterrows():
            label = r[label_col]
            for col in df.columns:
                if col == label_col:
                    continue
                rows.append({label_col: label, 'stat': col, 'value': _round(r[col])})
        return pd.DataFrame(rows)

    out = {'stat': [], 'value': []}
    row = df.iloc[0]
    for col in df.columns:
        out['stat'].append(col)
        out['value'].append(_round(row[col]))
    return pd.DataFrame(out)



def _format_range(start: datetime.date, end: datetime.date) -> str:
    """Return date range label like '2025--01-01--01-07'."""
    return f"{start.year:04d}--{start:%m-%d}--{end:%m-%d}"


def _format_raw_value(value: str) -> str:
    """Format ``value`` for CSV output, normalizing times when possible."""
    if value is None:
        return ''
    value = value.strip()
    if '|' not in value and value.lower().endswith(('am', 'pm')):
        t = _parse_time(value)
        if t is not None:
            formatted = datetime.datetime.combine(datetime.date(1900, 1, 1), t).strftime('%I:%M %p')
            return formatted.lstrip('0')  # Remove leading zero from hour
    return value


def export_single_weeks_csv(logfile: str, output_dir: str) -> None:
    """Write per-week CSVs of raw log values extracted from ``logfile``."""
    with open(logfile, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    week_label = None
    week_days: List[datetime.date] = []
    week_data: Dict[str, List[str]] = {}
    week_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip('\n')
        if not line.strip() or line.strip().startswith('...'):
            continue

        expanded = line.replace('\t', '    ')
        indent = len(expanded) - len(expanded.lstrip(' '))
        stripped = line.strip()

        if _WEEK_HEADER_RE.match(stripped):
            if week_label and week_days:
                _write_week_csv(output_dir, week_days, week_data, "".join(week_lines))
                week_data = {}
                week_lines = []
            res = _parse_week_header(stripped)
            if res:
                week_label, week_days = res
                week_lines = [raw_line]
            else:
                week_label = None
                week_days = []
                week_lines = []
        elif indent >= 4 and week_label:
            if '?' in stripped:
                q_part, values_part = stripped.split('?', 1)
                question = (q_part + '?').strip()
                values = values_part.strip().split()
                week_data[question] = values
                week_lines.append(' ' * indent + question + '\n')
            else:
                week_lines.append(raw_line)
        elif week_label:
            week_lines.append(raw_line)

    if week_label and week_days:
        _write_week_csv(output_dir, week_days, week_data, "".join(week_lines))


def save_week_log_annotations_as_markdown(
    log_text: str, output_dir: str = "output/single-weeks-by-log-range"
) -> None:
    """
    Extracts indented annotations under each question in a weekly sleep log snippet and
    saves them as a markdown file.

    The log_text must start with a week header matching _WEEK_HEADER_RE (e.g. 'Thu6/19-Wed25' or '6/19-7/02').
    Questions are lines beginning with a question number (e.g. '1.3b. Wind-down activities...').
    Any lines indented deeper than the question line are treated as annotations. If an annotation line
    starts with 'Day', the 'Day X, Date' portion is italicized in markdown.

    https://chatgpt.com/c/68709a0e-5684-800c-b59e-3709d6e58e56

    The output markdown file is written to ``output_dir`` using the pattern
      ``annotations-YYYY--MM-DD--MM2-DD2.md``
    where YYYY is the current year, MM-DD is taken from the header's date range,
    and if the second date omits the month, it inherits the first month's value.
    """
    lines = log_text.splitlines()
    if not lines:
        raise ValueError("Empty log text provided")

    header = lines[0].strip()
    if not _WEEK_HEADER_RE.match(header):
        raise ValueError(f"Header '{header}' does not match expected week header pattern")

    # Parse the month/day pairs from the header
    m = re.search(r"(\d{1,2})/(\d{1,2})-(?:[A-Za-z]{3})?(?:(\d{1,2})/)?(\d{1,2})", header)
    if not m:
        raise ValueError(f"Could not parse dates from header '{header}'")
    month1, day1, month2, day2 = m.group(1), m.group(2), m.group(3), m.group(4)
    month2 = month2 if month2 else month1

    # Build output filename
    year = datetime.date.today().year
    mm1, dd1 = month1.zfill(2), day1.zfill(2)
    mm2, dd2 = month2.zfill(2), day2.zfill(2)
    os.makedirs(output_dir, exist_ok=True)
    filename = f"annotations-{year}--{mm1}-{dd1}--{mm2}-{dd2}.md"
    filepath = os.path.join(output_dir, filename)

    # Build header line for the markdown file
    header_line = f"## Annotations: {mm1}/{dd1} - {mm2}/{dd2}  "

    # Extract annotations
    annotations = {}
    current_question = None
    question_indent = None
    question_re = re.compile(r'^\s*\d+(?:\.\d+)*[a-z]?\.\s')

    for line in lines[1:]:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(' '))
        # Detection of a question line
        if question_re.match(line):
            current_question = line.strip()
            question_indent = indent
            annotations[current_question] = []
        # Collect annotation lines indented under the current question
        elif current_question is not None and indent > question_indent:
            text = line.strip()
            if not text:
                continue
            # Italicize 'Day X, Date' if present
            if text.startswith('Day') and ':' in text:
                prefix, rest = text.split(':', 1)
                text = f"_{prefix}_:{rest}"
            annotations[current_question].append(text)

    # Generate markdown content
    md_lines = [header_line]
    for question, notes in annotations.items():
        if not notes:
            continue
        md_lines.append(f"**{question}**  ")
        for note in notes:
            md_lines.append(f"{note}  ")
        md_lines.append("")  # blank line between sections
    md_content = "\n".join(md_lines)
    if not md_content.endswith("\n"):
        md_content += "\n"

    # Write out the markdown file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md_content)



def _write_week_csv(
    output_dir: str, days: List[datetime.date], data: Dict[str, List[str]], week_text: str
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    start = days[0]
    end = days[-1]
    label = _format_range(start, end)
    path = os.path.join(output_dir, f'data-with-questions-{label}.csv')
    header = [''] + [f'{d.month}/{d.day}' for d in days]
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(header)
        for question, values in data.items():
            row = [question]
            for i in range(len(days)):
                val = values[i] if i < len(values) else ''
                row.append(_format_raw_value(val))
            writer.writerow(row)

    # Save annotations for this week
    save_week_log_annotations_as_markdown(week_text, output_dir)


def _write_week_csv_from_df(
    df: pd.DataFrame, output_dir: str, label: str, *, delimiter: str = ",", ext: str = "csv"
) -> None:
    """Write a table similar to ``_write_week_csv`` using dataframe values."""

    os.makedirs(output_dir, exist_ok=True)
    rows = [
        {col: df[col].iloc[i] if i < len(df[col]) else None for col in df.columns}
        for i in range(len(df['date']))
    ]
    rows.sort(key=lambda r: r['date'])
    days = [r['date'] for r in rows]
    header = [''] + [f'{d.month}/{d.day}' for d in days]
    path = os.path.join(output_dir, f'data-with-questions-{label}.{ext}')
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n', delimiter=delimiter)
        writer.writerow(header)
        for col in [c for c in df.columns if c != 'date']:
            question = COLUMN_TO_QUESTION.get(col, col)
            row = [question]
            for r in rows:
                val = r.get(col)
                if isinstance(val, datetime.time):
                    text = datetime.datetime.combine(datetime.date(1900, 1, 1), val).strftime('%I:%M %p').lstrip('0')
                elif val is None:
                    text = ''
                else:
                    text = str(val)
                row.append(text)
            writer.writerow(row)


def export_weeks_from_dataframe(df: pd.DataFrame, label_col: str, output_dir: str) -> None:
    """Export per-week CSVs, TSVs and stats using ``label_col`` for grouping."""

    os.makedirs(output_dir, exist_ok=True)

    df_stats = df.copy()
    df_stats['week_label'] = df[label_col]
    weekly_stats = compute_weekly_stats(df_stats)

    combined_rows = []
    for label, wk_df in weekly_stats.items():
        out_df = _prepare_stats_for_output(wk_df)
        out_df.to_csv(os.path.join(output_dir, f'stats-{label}.tsv'), sep='\t', index=False, lineterminator="\n")
        out_df.insert(0, label_col, label)
        combined_rows.append(out_df)

    for label, group in df.groupby(label_col):
        group.to_csv(os.path.join(output_dir, f'data-{label}.tsv'), sep='\t', index=False, lineterminator="\n")
        _write_week_csv_from_df(group, output_dir, label)

    if combined_rows:
        combined = pd.concat(combined_rows, ignore_index=True)
        combined.to_csv(os.path.join(output_dir, f'stats-by-{label_col}.tsv'), sep='\t', index=False)


def export_questions_table(df: pd.DataFrame, path: str) -> None:
    """Write ``df`` to ``path`` in the same question-oriented layout."""

    rows = [
        {col: df[col].iloc[i] if i < len(df[col]) else None for col in df.columns}
        for i in range(len(df['date']))
    ]
    rows.sort(key=lambda r: r['date'])
    days = [r['date'] for r in rows]
    header = [''] + [f"{d.month}/{d.day}" for d in days]
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n', delimiter='\t')
        writer.writerow(header)
        for col in [c for c in df.columns if c != 'date']:
            question = COLUMN_TO_QUESTION.get(col, col)
            row = [question]
            for r in rows:
                val = r.get(col)
                if isinstance(val, datetime.time):
                    text = datetime.datetime.combine(datetime.date(1900, 1, 1), val).strftime('%I:%M %p').lstrip('0')
                elif val is None:
                    text = ''
                else:
                    text = str(val)
                row.append(text)
            writer.writerow(row)

