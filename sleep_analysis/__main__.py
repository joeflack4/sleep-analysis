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
    export_weeks_from_dataframe,
    export_questions_table,
    _prepare_stats_for_output,
    _filter_non_empty_frames,
)
from sleep_analysis.csv_parser import parse_google_sheets_csv
from sleep_analysis.google_sheets_helper import sheets_url_to_csv


def _format_range(start: datetime.date, end: datetime.date) -> str:
    """Return date range label like '2025--01-01--01-07'."""
    return f"{start.year:04d}--{start:%m-%d}--{end:%m-%d}"


def _week_range_for_date(d: datetime.date) -> tuple[datetime.date, datetime.date]:
    """Return the Sunday-Saturday range containing ``d``."""
    start = d - datetime.timedelta(days=(d.weekday() + 1) % 7)
    end = start + datetime.timedelta(days=6)
    return start, end


def run_analysis(logfile: str, output_dir: str, label_files: bool = False, input_format: str = 'txt') -> None:
    """Parse ``logfile`` and write analysis outputs to ``output_dir``.

    When ``label_files`` is ``True`` the output filenames will include the date
    range contained in the log.
    
    Args:
        logfile: Path to the input file
        output_dir: Directory for output files  
        label_files: Whether to include date ranges in filenames
        input_format: Format of input file ('txt' for text logs, 'csv' for Google Sheets CSV)
    """
    # parse the raw log file into a dataframe
    if input_format == 'csv':
        df = parse_google_sheets_csv(logfile)
    else:
        df = parse_log(logfile)

    # ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    df['week_by_log_dates'] = df.groupby('week_label')['date'].transform(
        lambda s: _format_range(s.min(), s.max())
    )
    df['week'] = df['date'].apply(lambda d: _format_range(*_week_range_for_date(d)))

    start: datetime.date = df['date'].min()
    end: datetime.date = df['date'].max()
    range_label = _format_range(start, end)

    data_name: str = 'data.tsv'
    stats_name: str = 'stats.tsv'
    if label_files:
        # optionally include the date range in the filenames
        data_name = f'data-{range_label}.tsv'
        stats_name = f'stats-{range_label}.tsv'

    df_out = df.drop(columns=['week_label'])
    df_out.to_csv(os.path.join(output_dir, data_name), sep='\t', index=False, lineterminator="\n")
    questions_name = 'data-with-questions.tsv'
    if label_files:
        questions_name = f'data-with-questions-{range_label}.tsv'
    export_questions_table(df_out, os.path.join(output_dir, questions_name))

    weekly_stats: dict[str, pd.DataFrame] = compute_weekly_stats(df)
    export_single_weeks_csv(logfile, os.path.join(output_dir, "single-weeks-by-log-range"))
    export_weeks_from_dataframe(df, 'week_by_log_dates', os.path.join(output_dir, 'single-weeks-by-log-range'))
    export_weeks_from_dataframe(df, 'week', os.path.join(output_dir, 'by-week'))
    src = os.path.join(output_dir, 'single-weeks-by-log-range', 'stats-by-week_by_log_dates.tsv')
    if os.path.exists(src):
        os.replace(src, os.path.join(output_dir, 'stats-by-log-date-ranges.tsv'))
    src = os.path.join(output_dir, 'by-week', 'stats-by-week.tsv')
    if os.path.exists(src):
        os.replace(src, os.path.join(output_dir, 'stats-by-week.tsv'))

    if not label_files:
        # create additional stats using date ranges found in the log itself
        log_rows: list[pd.DataFrame] = []
        for label, wk_df in weekly_stats.items():
            start = df[df['week_label'] == label]['date'].min()
            end = df[df['week_label'] == label]['date'].max()
            new_label = _format_range(start, end)
            out_df = wk_df.copy()
            out_df.insert(0, 'week_by_log_dates', new_label)
            log_rows.append(out_df)

        if log_rows:
            valid_rows = _filter_non_empty_frames(log_rows)

            if valid_rows:
                by_log_df: pd.DataFrame = pd.concat(valid_rows, ignore_index=True)
                out_df = _prepare_stats_for_output(by_log_df, 'week_by_log_dates')
                out_df.to_csv(
                    os.path.join(output_dir, 'stats-by-log-date-ranges.tsv'),
                    sep='\t',
                    index=False,
                    lineterminator="\n")

    # final summary across all weeks
    overall = compute_overall_stats(weekly_stats)
    out_overall = _prepare_stats_for_output(overall)
    out_overall.to_csv(os.path.join(output_dir, stats_name), sep='\t', index=False, lineterminator="\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sleep log analysis")
    parser.add_argument('--logfile', default='input/log.txt', help='Path to sleep log txt file')
    parser.add_argument('--output-dir', default='output', help='Directory for output files')
    parser.add_argument('--single-week-logfile', default='input/log-single-week.txt', help='Optional single week log file')
    parser.add_argument('--csv-file', help='Path to Google Sheets CSV export file')
    parser.add_argument('--sheets-url', help='Google Sheets URL (will download as CSV)')
    parser.add_argument('--input-format', choices=['txt', 'csv'], default='txt', 
                       help='Input format: txt for text logs, csv for Google Sheets CSV')
    args = parser.parse_args()

    # Determine input file and format
    if args.sheets_url:
        # Download Google Sheets as CSV
        print(f"Downloading Google Sheets data from: {args.sheets_url}")
        csv_path = sheets_url_to_csv(args.sheets_url, "/tmp", "downloaded_sleep_data.csv")
        if csv_path is None:
            print("Error: Failed to download Google Sheets data")
            return
        input_file = csv_path
        input_format = 'csv'
    elif args.csv_file:
        input_file = args.csv_file
        input_format = 'csv'
    else:
        input_file = args.logfile
        input_format = args.input_format

    run_analysis(input_file, args.output_dir, label_files=False, input_format=input_format)

    single_week_out = os.path.join(args.output_dir, 'single-week')
    if os.path.exists(args.single_week_logfile):
        run_analysis(args.single_week_logfile, single_week_out, label_files=True)


if __name__ == '__main__':
    main()
