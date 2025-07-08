import argparse
import os

import datetime
import pandas as pd

from sleep_analysis.log_parser import (
    parse_log,
    compute_weekly_stats,
    compute_overall_stats,
)


def _format_range(start: datetime.date, end: datetime.date) -> str:
    """Return date range label like '2025--01-01--01-07'."""
    return f"{start.year:04d}--{start:%m-%d}--{end:%m-%d}"


def _week_range_for_date(d: datetime.date) -> tuple[datetime.date, datetime.date]:
    """Return the Sunday-Saturday range containing ``d``."""
    start = d - datetime.timedelta(days=(d.weekday() + 1) % 7)
    end = start + datetime.timedelta(days=6)
    return start, end


def main():
    parser = argparse.ArgumentParser(description="Sleep log analysis")
    parser.add_argument('--logfile', default='input/log.txt', help='Path to sleep log txt file')
    parser.add_argument('--output-dir', default='output', help='Directory for output files')
    args = parser.parse_args()

    df = parse_log(args.logfile)

    os.makedirs(args.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Prepare data columns
    # ------------------------------------------------------------------
    # Original week labels are in ``MMDD-MMDD`` form without the year.
    # Convert them to ``YYYY--MM-DD--MM-DD`` using the dates contained in
    # each group.  ``2025`` is used as the default year.
    df['week_by_log_dates'] = df.groupby('week_label')['date'].transform(
        lambda s: _format_range(s.min(), s.max())
    )
    # Also compute a calendar week label starting on Sunday and ending on
    # Saturday.
    df['week'] = df['date'].apply(lambda d: _format_range(*_week_range_for_date(d)))

    # Save the cleaned dataframe (drop the old ``week_label`` column).
    data_path = os.path.join(args.output_dir, 'data.tsv')
    df.drop(columns=['week_label']).to_csv(data_path, sep='\t', index=False)

    # ------------------------------------------------------------------
    # Stats by log-defined date ranges
    # ------------------------------------------------------------------
    weekly_stats = compute_weekly_stats(df)
    log_rows = []
    for label, wk_df in weekly_stats.items():
        start = df[df['week_label'] == label]['date'].min()
        end = df[df['week_label'] == label]['date'].max()
        new_label = _format_range(start, end)
        out_df = wk_df.copy()
        out_df.insert(0, 'week_by_log_dates', new_label)
        log_rows.append(out_df)
    if log_rows:
        by_log_df = pd.concat(log_rows, ignore_index=True)
        by_log_df.to_csv(
            os.path.join(args.output_dir, 'stats-by-log-date-ranges.tsv'),
            sep='\t',
            index=False,
        )

    # ------------------------------------------------------------------
    # Stats by calendar week (Sunday-Saturday)
    # ------------------------------------------------------------------
    df_week = df.copy()
    df_week['week_label'] = df_week['week']
    week_stats = compute_weekly_stats(df_week)
    by_week_rows = []
    by_week_dir = os.path.join(args.output_dir, 'by-week')
    os.makedirs(by_week_dir, exist_ok=True)
    for label, wk_df in week_stats.items():
        wk_df.to_csv(os.path.join(by_week_dir, f'stats-{label}.tsv'), sep='\t', index=False)
        out_df = wk_df.copy()
        out_df.insert(0, 'week', label)
        by_week_rows.append(out_df)
    if by_week_rows:
        by_week_df = pd.concat(by_week_rows, ignore_index=True)
        by_week_df.to_csv(
            os.path.join(args.output_dir, 'stats-by-week.tsv'),
            sep='\t',
            index=False,
        )

    # Overall stats from the log-defined date ranges
    overall = compute_overall_stats(weekly_stats)
    overall.to_csv(os.path.join(args.output_dir, 'stats.tsv'), sep='\t', index=False)


if __name__ == '__main__':
    main()
