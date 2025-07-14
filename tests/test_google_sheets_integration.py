"""Tests for Google Sheets integration."""

import datetime
import pytest
from unittest.mock import Mock, patch

# Try to import the Google Sheets integration, skip tests if not available
try:
    from sleep_analysis.google_sheets_integration import (
        GoogleFormsDataConverter,
        GoogleSheetsDataFetcher,
        GOOGLE_SHEETS_AVAILABLE
    )
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False


@pytest.mark.skipif(not GOOGLE_SHEETS_AVAILABLE, reason="Google Sheets API not available")
class TestGoogleFormsDataConverter:
    """Test Google Forms data conversion."""
    
    def test_question_mapping(self):
        """Test that Google Form questions are correctly mapped to standard questions."""
        # Sample Google Forms data
        header = [
            'Timestamp',
            'What time do you start winding down for sleep?',
            'What time did you get into bed and commit to sleep?',
            'What time did you wake up?',
            'Rate your sleep quality (1-10)',
            'How many alcoholic drinks did you have?'
        ]
        
        data = [header]
        converter = GoogleFormsDataConverter(data)
        mapping = converter.map_form_questions()
        
        # Check that questions are properly mapped
        assert mapping[1] == '1b. What time start winding down?'
        assert mapping[2] == '1.2b. What time did you get into bed & commit to sleep?'
        assert mapping[3] == '6. What time did you wake up?'
        assert mapping[4] == '10. Quality of your sleep (1-10)?'
        assert mapping[5] == '14. If alcohol, how many standard drinks?'
    
    def test_timestamp_parsing(self):
        """Test parsing of timestamp column."""
        data = [
            ['Timestamp', 'Question 1'],
            ['12/25/2024 14:30:00', 'Answer 1'],
            ['12/26/2024 15:45:30', 'Answer 2'],
            ['invalid date', 'Answer 3'],  # Should be skipped
        ]
        
        converter = GoogleFormsDataConverter(data)
        dates = converter.parse_timestamp_column()
        
        assert len(dates) == 2  # Third row should be skipped
        assert dates[0] == datetime.date(2024, 12, 25)
        assert dates[1] == datetime.date(2024, 12, 26)
    
    def test_value_parsing(self):
        """Test parsing of different value types."""
        data = [
            ['Timestamp', 'Sleep Time', 'Quality', 'Hours'],
            ['12/25/2024 14:30:00', '11:30 PM', '8', '7.5'],
        ]
        
        converter = GoogleFormsDataConverter(data)
        
        # Test time parsing
        time_val = converter._parse_time('11:30 PM')
        assert time_val == datetime.time(23, 30)
        
        # Test numeric parsing
        numeric_val = converter._parse_numeric('7.5')
        assert numeric_val == 7.5
        
        # Test invalid values
        assert converter._parse_time('invalid') is None
        assert converter._parse_numeric('not a number') is None


@pytest.mark.skipif(not GOOGLE_SHEETS_AVAILABLE, reason="Google Sheets API not available")
class TestGoogleSheetsDataFetcher:
    """Test Google Sheets data fetching."""
    
    def test_extract_spreadsheet_id(self):
        """Test extracting spreadsheet ID from various URL formats."""
        fetcher = GoogleSheetsDataFetcher()
        
        # Standard URL format
        url1 = "https://docs.google.com/spreadsheets/d/1dOFbfTFReRhJUxjj8TdLvsyOnBJ_WlPvpqXwj48WgVU/edit"
        assert fetcher.extract_spreadsheet_id(url1) == "1dOFbfTFReRhJUxjj8TdLvsyOnBJ_WlPvpqXwj48WgVU"
        
        # URL with additional parameters
        url2 = "https://docs.google.com/spreadsheets/d/1ABC123/edit?resourcekey=xyz&gid=123#gid=456"
        assert fetcher.extract_spreadsheet_id(url2) == "1ABC123"
        
        # Invalid URL should raise error
        with pytest.raises(ValueError):
            fetcher.extract_spreadsheet_id("https://invalid-url.com")


def test_question_mapping_patterns():
    """Test question mapping patterns without Google Sheets dependencies."""
    # This test can run even without Google Sheets API
    
    # Mock the converter class
    class MockConverter:
        FORM_QUESTION_MAPPING = {
            r'.*wind.*down.*time.*': '1b. What time start winding down?',
            r'.*bed.*time.*commit.*sleep.*': '1.2b. What time did you get into bed & commit to sleep?',
            r'.*sleep.*quality.*': '10. Quality of your sleep (1-10)?',
        }
    
    # Test pattern matching
    test_questions = [
        ("What time do you start winding down?", '1b. What time start winding down?'),
        ("When did you get into bed and commit to sleep?", '1.2b. What time did you get into bed & commit to sleep?'),
        ("Rate your sleep quality", '10. Quality of your sleep (1-10)?'),
    ]
    
    import re
    converter = MockConverter()
    
    for test_question, expected in test_questions:
        test_lower = test_question.lower()
        matched = False
        
        for pattern, standard_question in converter.FORM_QUESTION_MAPPING.items():
            if re.search(pattern, test_lower):
                assert standard_question == expected
                matched = True
                break
        
        assert matched, f"No pattern matched for: {test_question}"


if __name__ == '__main__':
    pytest.main([__file__])