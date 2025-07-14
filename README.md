# sleep-analysis

[![CI](https://github.com/joeflack4/sleep-analysis/actions/workflows/tests.yml/badge.svg)](https://github.com/joeflack4/sleep-analysis/actions/workflows/tests.yml)

Tools for parsing semi-structured sleep logs and producing weekly and overall statistics.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

The main entry point is the `sleep_analysis` module. Provide it with a log file and an output directory:

```bash
python -m sleep_analysis --logfile input/log.txt --output-dir output
```

If you have an additional single week log you can provide it with `--single-week-logfile`. The results for that log are written under `<output>/single-week`.

## Input format

Logs are text files organised by week. Each week begins with a header line containing a date range:

```
    Thu6/19-Wed25
```

Day of week prefixes are optional. The month/day pairs are interpreted as occurring in the year 2025. Lines beginning with `...` are ignored.

Within each week the questions of interest are indented two levels and followed by seven values (one for each day). For example:

```
        1b. What time start winding down? 2:20am 2:50am 2:10am 2:10am 2:20am 3:20am 3:40am
        1.2b. What time did you get into bed & commit to sleep? 3:34am 4:22am 3:33am 4:13am 4:02am 4:25am 4:25am
        6. What time did you wake up? 11:30am 11:30am 11:30am 11:30am 11:30am 11:30am 11:30am
        7. What time did you get out of bed? 11:45am 12:35pm 11:40am 12:01pm 11:43am 11:57am 11:40am
```

A single dot (`.`) represents a missing value. Additional notes may appear indented beneath a question; these are ignored by the parser.

## Output

Running the analysis creates several files in the output directory:

- `data.tsv` – parsed daily records across all weeks.
- `stats.tsv` – overall statistics computed from all weeks.
- `stats-by-log-date-ranges.tsv` – per‑week statistics using the date ranges found in the log.
- `single-weeks-by-log-range/` – directory containing raw CSV files for each week.

When a single week log is supplied an additional directory `<output>/single-week` is created containing `data-<range>.tsv` and `stats-<range>.tsv` for that log.

Below is a truncated example of a weekly CSV produced in `single-weeks-by-log-range`:

```
,6/19,6/20,6/21,6/22,6/23,6/24,6/25
1b. What time start winding down?,2:20 AM,2:50 AM,2:10 AM,2:10 AM,2:20 AM,3:20 AM,3:40 AM
1.2b. What time did you get into bed & commit to sleep?,3:34 AM,4:22 AM,3:33 AM,4:13 AM,4:02 AM,4:25 AM,4:25 AM
```

These values correspond to the questions and dates in the original log file.

## Google Sheets Integration

The tool now supports fetching sleep data directly from Google Sheets (e.g., Google Forms responses).

### Setup

1. Install additional dependencies:
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

2. Set up Google Sheets API credentials:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Sheets API
   - Create credentials (OAuth 2.0 client ID) for a desktop application
   - Download the credentials JSON file and save it as `credentials.json`

### Usage

```bash
python -m sleep_analysis --google-sheets-url "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit" --output-dir output
```

The tool will:
1. Authenticate with Google (opens browser for first-time setup)
2. Fetch data from your Google Sheets
3. Automatically map Google Form questions to sleep analysis questions
4. Convert the data to the standard format
5. Run the full analysis pipeline

### Google Form Question Mapping

The integration automatically maps common Google Form questions to the standard sleep questions:

- **Wind down time**: Questions containing "wind down" and "time"
- **Bedtime**: Questions about "bed time" and "commit to sleep"
- **Wake up time**: Questions about "wake up" and "time"
- **Sleep quality**: Questions about "sleep quality" (1-10 scale)
- **Alcohol consumption**: Questions about "alcohol" and "drinks"
- And many more...

### Supported Data Formats

The Google Sheets integration handles various response formats:
- Times: "2:30 AM", "14:30", "2:30pm"
- Durations: "7:30" (hours:minutes), "7.5" (decimal hours)
- Numbers: Ratings, counts, etc.
- Text: Free-form responses with "|" separators for multiple values
