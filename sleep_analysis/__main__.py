import argparse
import os

from .log_parser import parse_log, compute_weekly_stats, compute_overall_stats


def main():
    parser = argparse.ArgumentParser(description="Sleep log analysis")
    parser.add_argument('logfile', help='Path to sleep log txt file')
    parser.add_argument('--output-dir', default='output', help='Directory for output files')
    args = parser.parse_args()

    df = parse_log(args.logfile)
    os.makedirs(args.output_dir, exist_ok=True)
    data_path = os.path.join(args.output_dir, 'data.tsv')
    df.to_csv(data_path, sep='\t', index=False)

    weekly_stats = compute_weekly_stats(df)
    for label, wk_df in weekly_stats.items():
        wk_df.to_csv(os.path.join(args.output_dir, f'stats-{label}.tsv'), sep='\t', index=False)

    overall = compute_overall_stats(weekly_stats)
    overall.to_csv(os.path.join(args.output_dir, 'stats.tsv'), sep='\t', index=False)


if __name__ == '__main__':
    main()
