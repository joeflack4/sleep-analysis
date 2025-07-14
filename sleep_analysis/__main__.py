"""Analyze sleep data"""
import argparse
import os
import tempfile

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

try:
    from sleep_analysis.google_sheets_integration import (
        fetch_google_forms_data,
        save_google_forms_as_log,
        GOOGLE_SHEETS_AVAILABLE
    )
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False


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


def run_google_sheets_analysis(
    sheets_url: str,
    output_dir: str,
    credentials_path: str = 'credentials.json'
) -> None:
    """Fetch Google Sheets data and run analysis on it.
    
    Args:
        sheets_url: Google Sheets URL
        output_dir: Directory for output files
        credentials_path: Path to Google API credentials
    """
    if not GOOGLE_SHEETS_AVAILABLE:
        raise ImportError(
            "Google Sheets integration not available. "
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
    
    print(f"Fetching data from Google Sheets: {sheets_url}")
    
    # Create a temporary log file from Google Sheets data
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
        temp_log_path = temp_file.name
    
    try:
        # Convert Google Sheets data to log format
        save_google_forms_as_log(sheets_url, temp_log_path, credentials_path)
        print(f"Converted Google Sheets data to temporary log: {temp_log_path}")
        
        # Run standard analysis on the converted data
        run_analysis(temp_log_path, output_dir, label_files=False)
        
        print(f"Analysis complete. Results saved to: {output_dir}")
        
    finally:
        # Clean up temporary file
        if os.path.exists(temp_log_path):
            os.unlink(temp_log_path)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sleep log analysis")
    parser.add_argument('--logfile', default='input/log.txt', help='Path to sleep log txt file')
    parser.add_argument('--output-dir', default='output', help='Directory for output files')
    parser.add_argument('--single-week-logfile', default='input/log-single-week.txt', help='Optional single week log file')
    
    # Google Sheets integration options
    parser.add_argument('--google-sheets-url', help='Google Sheets URL to fetch data from')
    parser.add_argument('--credentials-path', default='credentials.json', 
                       help='Path to Google API credentials JSON file')
    
    args = parser.parse_args()

    # Handle Google Sheets input
    if args.google_sheets_url:
        run_google_sheets_analysis(args.google_sheets_url, args.output_dir, args.credentials_path)
        return
    
    # Handle standard log file input
    run_analysis(args.logfile, args.output_dir, label_files=False)

    single_week_out = os.path.join(args.output_dir, 'single-week')
    if os.path.exists(args.single_week_logfile):
        run_analysis(args.single_week_logfile, single_week_out, label_files=True)


if __name__ == '__main__':
    main()
