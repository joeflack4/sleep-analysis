"""Tests for CSV parsing functionality."""

import unittest
import tempfile
import os
import datetime
import sys

# Ensure the project root is on the import path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Remove pandas stub if it exists and import real pandas
if 'pandas' in sys.modules:
    del sys.modules['pandas']

import pandas as pd
from sleep_analysis.csv_parser import (
    parse_google_sheets_csv,
    _normalize_question,
    _parse_csv_value,
    GOOGLE_FORMS_QUESTION_MAP
)


class TestCSVParser(unittest.TestCase):
    
    def setUp(self):
        """Create a temporary CSV file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.csv_file = os.path.join(self.temp_dir, 'test.csv')
        
        # Sample CSV content
        csv_content = """Timestamp,What time start winding down?,What time did you get into bed & commit to sleep?,How long do you estimate it took to fall asleep (minutes)?,What time did you wake up?,What time did you get out of bed?,Quality of your sleep (1-10)?,If alcohol how many standard drinks?
2025-01-01T22:30:00,10:30 PM,11:00 PM,15,7:00 AM,7:15 AM,8,0
2025-01-02T22:45:00,10:45 PM,11:15 PM,20,7:30 AM,7:45 AM,7,1
2025-01-03T22:20:00,10:20 PM,10:50 PM,10,6:45 AM,7:00 AM,9,0"""
        
        with open(self.csv_file, 'w', encoding='utf-8') as f:
            f.write(csv_content)
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_parse_csv_basic(self):
        """Test basic CSV parsing functionality."""
        df = parse_google_sheets_csv(self.csv_file)
        
        # Check we got the right number of records
        self.assertEqual(len(df), 3)
        
        # Check date parsing
        self.assertEqual(df['date'].iloc[0], datetime.date(2025, 1, 1))
        self.assertEqual(df['date'].iloc[1], datetime.date(2025, 1, 2))
        self.assertEqual(df['date'].iloc[2], datetime.date(2025, 1, 3))
        
        # Check time parsing
        self.assertEqual(df['wind_down_start_time'].iloc[0], datetime.time(22, 30))
        self.assertEqual(df['bed_time'].iloc[0], datetime.time(23, 0))
        self.assertEqual(df['wake_up_time'].iloc[0], datetime.time(7, 0))
        
        # Check numeric values
        self.assertEqual(df['fall_asleep_minutes'].iloc[0], 15)
        self.assertEqual(df['sleep_quality'].iloc[0], 8)
        self.assertEqual(df['alcohol_drinks'].iloc[0], 0.0)
        self.assertEqual(df['alcohol_drinks'].iloc[1], 1.0)
    
    def test_week_label_generation(self):
        """Test that week labels are generated correctly."""
        df = parse_google_sheets_csv(self.csv_file)
        
        # All dates should be in the same week (Jan 1-3, 2025)
        # Week should start on Sunday (Dec 29, 2024) and end Saturday (Jan 4, 2025)
        expected_week_label = "1229-0104"  # Dec 29 to Jan 4
        
        # Check that all records have the same week label since they're consecutive dates
        week_labels = df['week_label'].unique()
        self.assertEqual(len(week_labels), 1)
        self.assertEqual(week_labels[0], expected_week_label)
    
    def test_normalize_question(self):
        """Test question normalization."""
        self.assertEqual(
            _normalize_question("  What time start winding down?  "),
            "What time start winding down?"
        )
        self.assertEqual(
            _normalize_question("In total,how long did these awakenings last?"),
            "In total, how long did these awakenings last?"
        )
    
    def test_parse_csv_value(self):
        """Test individual value parsing."""
        # Time values
        self.assertEqual(_parse_csv_value("10:30 PM", "wind_down_start_time"), datetime.time(22, 30))
        self.assertEqual(_parse_csv_value("7:00 AM", "wake_up_time"), datetime.time(7, 0))
        
        # Numeric values
        self.assertEqual(_parse_csv_value("15", "fall_asleep_minutes"), 15.0)
        self.assertEqual(_parse_csv_value("8", "sleep_quality"), 8.0)
        
        # String values
        self.assertEqual(_parse_csv_value("No", "second_wind"), "No")
        
        # Empty values
        self.assertIsNone(_parse_csv_value("", "wind_down_start_time"))
        self.assertIsNone(_parse_csv_value("   ", "sleep_quality"))
    
    def test_custom_question_mapping(self):
        """Test using custom question mappings."""
        # Create a CSV with custom question names
        custom_csv = os.path.join(self.temp_dir, 'custom.csv')
        csv_content = """Timestamp,Custom Bedtime Question?,Custom Wake Time?
2025-01-01T22:30:00,11:00 PM,7:00 AM"""
        
        with open(custom_csv, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        
        # Custom mapping
        custom_map = {
            'Custom Bedtime Question?': 'bed_time',
            'Custom Wake Time?': 'wake_up_time'
        }
        
        df = parse_google_sheets_csv(custom_csv, question_map=custom_map)
        
        self.assertEqual(len(df), 1)
        self.assertEqual(df['bed_time'].iloc[0], datetime.time(23, 0))
        self.assertEqual(df['wake_up_time'].iloc[0], datetime.time(7, 0))


class TestQuestionMapping(unittest.TestCase):
    
    def test_default_mappings_exist(self):
        """Test that default question mappings are comprehensive."""
        expected_columns = [
            'wind_down_start_time',
            'bed_time', 
            'fall_asleep_minutes',
            'night_wake_ups',
            'awake_minutes',
            'out_of_bed_minutes',
            'wake_up_time',
            'get_out_of_bed_time',
            'sleep_hours',
            'bed_hours',
            'sleep_quality',
            'naps',
            'mood',
            'fatigue',
            'alcohol_drinks',
            'second_wind'
        ]
        
        mapped_columns = set(GOOGLE_FORMS_QUESTION_MAP.values())
        
        for col in expected_columns:
            self.assertIn(col, mapped_columns, f"Column {col} not found in question mappings")


if __name__ == '__main__':
    unittest.main()