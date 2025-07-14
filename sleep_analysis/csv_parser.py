"""Parse Google Sheets CSV exports into the same format as log_parser."""

import csv
import datetime
import pandas as pd
from typing import Dict, List, Optional

from .log_parser import (
    _parse_time,
    _parse_duration,
    TIME_COLS,
    NUMERIC_COLS,
    STRING_COLS,
)

# Mapping from common Google Forms question text to our internal column names
GOOGLE_FORMS_QUESTION_MAP = {
    # Basic mappings - these should match common question phrasings
    'What time start winding down?': 'wind_down_start_time',
    'What time did you get into bed & commit to sleep?': 'bed_time',
    'How long do you estimate it took to fall asleep (minutes)?': 'fall_asleep_minutes',
    'How many times did you wake up during the night?': 'night_wake_ups',
    'In total, how long did these awakenings last (minutes)?': 'awake_minutes',
    'In total how long did these awakenings last (minutes)?': 'awake_minutes',  # Alternative phrasing
    'When awake during the night, how long did you spend out of bed (minutes)?': 'out_of_bed_minutes',
    'When awake during the night how long did you spend out of bed (minutes)?': 'out_of_bed_minutes',  # Alternative phrasing
    'What time did you wake up?': 'wake_up_time',
    'What time did you get out of bed?': 'get_out_of_bed_time',
    'In TOTAL, how many hours of sleep did you get?': 'sleep_hours',
    'In TOTAL how many hours of sleep did you get?': 'sleep_hours',  # Alternative phrasing
    'In TOTAL, how many hours did you spend in bed?': 'bed_hours',
    'In TOTAL how many hours did you spend in bed?': 'bed_hours',  # Alternative phrasing
    'Quality of your sleep (1-10)?': 'sleep_quality',
    'Did you take naps during the day?': 'naps',
    'Mood during the day (1-10)?': 'mood',
    'Fatigue level during the day (1-10)?': 'fatigue',
    'If alcohol, how many standard drinks?': 'alcohol_drinks',
    'If alcohol how many standard drinks?': 'alcohol_drinks',  # Alternative phrasing
    'Second wind?': 'second_wind',
}


def _normalize_question(question: str) -> str:
    """Normalize question text for mapping."""
    # Remove extra whitespace and normalize punctuation
    question = question.strip()
    # Handle common variations
    question = question.replace(',', ', ')  # Ensure space after commas
    return question


def _parse_csv_value(value: str, column: str) -> object:
    """Parse a CSV value based on the column type."""
    if not value or value.strip() == '':
        return None
    
    value = value.strip()
    
    if column in TIME_COLS:
        return _parse_time(value)
    elif column in STRING_COLS:
        return value
    elif column == 'alcohol_drinks':
        try:
            return float(value) if value else 0.0
        except ValueError:
            return 0.0
    elif column in NUMERIC_COLS:
        # Try to parse as float first, then as duration
        try:
            return float(value)
        except ValueError:
            return _parse_duration(value)
    else:
        # Default case - try to parse as number, otherwise string
        try:
            return float(value)
        except ValueError:
            return value


def parse_google_sheets_csv(path: str, question_map: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """
    Parse a Google Sheets CSV export into the same DataFrame format as parse_log.
    
    Args:
        path: Path to the CSV file
        question_map: Optional custom mapping from question text to column names.
                     If not provided, uses GOOGLE_FORMS_QUESTION_MAP.
    
    Returns:
        DataFrame with the same structure as parse_log output
    """
    if question_map is None:
        question_map = GOOGLE_FORMS_QUESTION_MAP
    
    records = []
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            record = {}
            
            # Extract timestamp/date if present
            timestamp = None
            if 'Timestamp' in row and row['Timestamp']:
                try:
                    # Try to parse common timestamp formats
                    timestamp_str = row['Timestamp']
                    # Handle ISO format with T separator
                    if 'T' in timestamp_str:
                        timestamp = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        # Try pandas parsing for other formats
                        timestamp = pd.to_datetime(timestamp_str)
                    record['date'] = timestamp.date()
                except Exception:
                    # If timestamp parsing fails, use today's date
                    record['date'] = datetime.date.today()
            else:
                # No timestamp - use today's date
                record['date'] = datetime.date.today()
            
            # Map questions to internal column names
            for question_text, value in row.items():
                if question_text == 'Timestamp':
                    continue
                
                # Normalize the question text and try to find a mapping
                normalized_question = _normalize_question(question_text)
                column_name = question_map.get(normalized_question)
                
                if column_name:
                    parsed_value = _parse_csv_value(value, column_name)
                    record[column_name] = parsed_value
            
            # Add a week label based on the date (we'll use the date as identifier)
            if 'date' in record:
                date = record['date']
                # Use Sunday-to-Saturday week grouping like the main parser
                start_of_week = date - datetime.timedelta(days=(date.weekday() + 1) % 7)
                end_of_week = start_of_week + datetime.timedelta(days=6)
                record['week_label'] = f"{start_of_week.month:02d}{start_of_week.day:02d}-{end_of_week.month:02d}{end_of_week.day:02d}"
            
            records.append(record)
    
    return pd.DataFrame(records)


def update_question_mapping(additional_mappings: Dict[str, str]) -> None:
    """
    Update the global question mapping with additional mappings.
    
    Args:
        additional_mappings: Dictionary mapping question text to column names
    """
    GOOGLE_FORMS_QUESTION_MAP.update(additional_mappings)


def get_available_mappings() -> Dict[str, str]:
    """Return the current question mappings."""
    return GOOGLE_FORMS_QUESTION_MAP.copy()