import datetime
import math
import re
import os
import csv
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
    """Return the average time of day from ``times``."""

    # filter out ``None`` entries
    times = [t for t in times if t is not None]
    if not times:
        return None

    total_minutes = sum(t.hour * 60 + t.minute for t in times)
    avg_minutes = total_minutes / len(times)
    hour = int(avg_minutes // 60) % 24
    minute = int(avg_minutes % 60)
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
    """Return average absolute difference from ``expected``."""

    times = [t for t in times if t is not None]
    if not times:
        return None

    exp_minutes = expected.hour * 60 + expected.minute
    diffs = [abs((t.hour * 60 + t.minute) - exp_minutes) for t in times]
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
                    if col and 'time' in col:
                        parsed_vals.append(_parse_time(v))
                    elif col == 'alcohol_drinks':
                        parsed_vals.append(float(v) if v != '.' else 0.0)
                    else:
                        # generic: try duration or numeric value
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

        # process all time-based metrics
        for col in ['wind_down_start_time', 'bed_time', 'wake_up_time', 'get_out_of_bed_time']:
            times: list[datetime.time] = wk_df[col].dropna().tolist() if col in wk_df else []
            if not times:
                continue

            avg_t: datetime.time | None = _avg_time(times)
            med_t: datetime.time | None = _median_time(times)
            std_t = _std_time(times)

            if avg_t:
                stats[f'{col}_avg'] = [avg_t.strftime('%I:%M%p').lower()]
            if med_t:
                stats[f'{col}_median'] = [med_t.strftime('%I:%M%p').lower()]
            if std_t is not None:
                stats[f'{col}_std'] = [std_t]

            offsets: list[int] = [
                abs(
                    (t.hour * 60 + t.minute)
                    - (EXPECTED_TIMES[col].hour * 60 + EXPECTED_TIMES[col].minute)
                )
                for t in times
            ]
            avg_off: float = sum(offsets) / len(offsets)
            med_off = _median(offsets)
            std_off = _std(offsets)

            stats[f'{col}_offset_avg'] = [avg_off]
            if med_off is not None:
                stats[f'{col}_offset_median'] = [med_off]
            if std_off is not None:
                stats[f'{col}_offset_std'] = [std_off]

        week_stats_df = pd.DataFrame(stats)
        weekly_dfs[label] = week_stats_df

    return weekly_dfs


def compute_overall_stats(weekly_stats: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Aggregate ``weekly_stats`` into a single overall statistics dataframe."""

    if not weekly_stats:
        return pd.DataFrame()

    combined: pd.DataFrame = pd.concat(weekly_stats.values(), ignore_index=True)
    numeric_cols = combined.select_dtypes(include='number').columns
    time_cols: list[str] = []

    if not combined.empty:
        for c in combined.columns:
            if c.endswith('_avg') and combined[c].dtype == object:
                first: object | None = next((v for v in combined[c] if v is not None), None)
                if isinstance(first, str) and ':' in first:
                    time_cols.append(c)

    overall: dict[str, float | str] = {}

    # numeric columns
    for col in numeric_cols:
        base = col[:-4] if col.endswith('_avg') else col
        values: list[float] = [v for v in combined[col] if v is not None]
        mean_val: float = sum(values) / len(values) if values else 0
        median_val = _median(values) if values else 0
        overall[f'{col}'] = mean_val  # preserve original avg column
        if median_val is not None:
            overall[f'{base}_median'] = median_val

    # time columns
    for col in time_cols:
        base = col[:-4]
        times: list[datetime.time] = [
            pd.to_datetime(t).time() for t in combined[col] if isinstance(t, str)
        ]
        if times:
            avg_t: datetime.time | None = _avg_time(times)
            med_t: datetime.time | None = _median_time(times)
            if avg_t:
                overall[col] = avg_t.strftime('%I:%M%p').lower()
            if med_t:
                overall[f'{base}_median'] = med_t.strftime('%I:%M%p').lower()

    return pd.DataFrame([overall])



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
    md_lines = []
    for question, notes in annotations.items():
        if not notes:
            continue
        md_lines.append(f"**{question}**")
        for note in notes:
            md_lines.append(note)
        md_lines.append("")  # blank line between sections
    md_content = "\n".join(md_lines).strip() + "\n"

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
    path = os.path.join(output_dir, f'data-{label}.csv')
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

