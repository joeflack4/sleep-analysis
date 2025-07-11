"""Analyze sleep data"""
import argparse
import os

import datetime
import pandas as pd

from sleep_analysis.log_parser import (
    parse_log,
    export_single_weeks_csv,
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


def run_analysis(logfile: str, output_dir: str, label_files: bool = False) -> None:
    """Parse ``logfile`` and write analysis outputs to ``output_dir``.

    When ``label_files`` is ``True`` the output filenames will include the date
    range contained in the log.
    """
    # parse the raw log file into a dataframe
    df = parse_log(logfile)

    # ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    df['week_by_log_dates'] = df.groupby('week_label')['date'].transform(
        lambda s: _format_range(s.min(), s.max())
    )
    df['week'] = df['date'].apply(lambda d: _format_range(*_week_range_for_date(d)))

    start = df['date'].min()
    end = df['date'].max()
    range_label = _format_range(start, end)

    data_name = 'data.tsv'
    stats_name = 'stats.tsv'
    if label_files:
        # optionally include the date range in the filenames
        data_name = f'data-{range_label}.tsv'
        stats_name = f'stats-{range_label}.tsv'

    df.drop(columns=['week_label']).to_csv(os.path.join(output_dir, data_name), sep='\t', index=False)

    weekly_stats = compute_weekly_stats(df)
    export_single_weeks_csv(logfile, os.path.join(output_dir, "single-weeks-by-log-range"))

    if not label_files:
        # create additional stats using date ranges found in the log itself
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
                os.path.join(output_dir, 'stats-by-log-date-ranges.tsv'),
                sep='\t',
                index=False,
            )

    # final summary across all weeks
    overall = compute_overall_stats(weekly_stats)
    overall.to_csv(os.path.join(output_dir, stats_name), sep='\t', index=False)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sleep log analysis")
    parser.add_argument('--logfile', default='input/log.txt', help='Path to sleep log txt file')
    parser.add_argument('--output-dir', default='output', help='Directory for output files')
    parser.add_argument('--single-week-logfile', default='input/log-single-week.txt', help='Optional single week log file')
    args = parser.parse_args()

    run_analysis(args.logfile, args.output_dir, label_files=False)

    single_week_out = os.path.join(args.output_dir, 'single-week')
    if os.path.exists(args.single_week_logfile):
        run_analysis(args.single_week_logfile, single_week_out, label_files=True)


if __name__ == '__main__':
    main()
