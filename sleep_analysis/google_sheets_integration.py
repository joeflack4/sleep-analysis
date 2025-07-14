"""Google Sheets integration for sleep analysis data."""

import datetime
import re
from typing import Dict, List, Optional, Any
import pandas as pd

try:
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False

from sleep_analysis.log_parser import QUESTION_TO_COLUMN, TIME_COLS, NUMERIC_COLS, STRING_COLS


# Google Sheets API scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


class GoogleSheetsDataFetcher:
    """Fetches and processes sleep data from Google Sheets."""
    
    def __init__(self, credentials_path: str = 'credentials.json', token_path: str = 'token.json'):
        """Initialize the Google Sheets data fetcher.
        
        Args:
            credentials_path: Path to Google API credentials JSON file
            token_path: Path to store OAuth token
        """
        if not GOOGLE_SHEETS_AVAILABLE:
            raise ImportError(
                "Google Sheets API libraries not available. "
                "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
        
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        
    def authenticate(self) -> None:
        """Authenticate with Google Sheets API."""
        creds = None
        
        # Load existing token if available
        try:
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        except FileNotFoundError:
            pass
        
        # If no valid credentials, run OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('sheets', 'v4', credentials=creds)
    
    def fetch_data(self, spreadsheet_id: str, range_name: str = 'A:Z') -> List[List[str]]:
        """Fetch data from Google Sheets.
        
        Args:
            spreadsheet_id: The Google Sheets spreadsheet ID
            range_name: The range to fetch (e.g., 'Sheet1!A:Z')
            
        Returns:
            List of rows, where each row is a list of cell values
        """
        if not self.service:
            self.authenticate()
        
        result = self.service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        return result.get('values', [])
    
    def extract_spreadsheet_id(self, url: str) -> str:
        """Extract spreadsheet ID from Google Sheets URL.
        
        Args:
            url: Google Sheets URL
            
        Returns:
            Spreadsheet ID
        """
        # Extract ID from URLs like:
        # https://docs.google.com/spreadsheets/d/1dOFbfTFReRhJUxjj8TdLvsyOnBJ_WlPvpqXwj48WgVU/edit...
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
        if match:
            return match.group(1)
        raise ValueError(f"Could not extract spreadsheet ID from URL: {url}")


class GoogleFormsDataConverter:
    """Converts Google Forms response data to sleep analysis format."""
    
    # Mapping from potential Google Form question patterns to our standard questions
    FORM_QUESTION_MAPPING = {
        # Time-related questions
        r'.*wind.*down.*time.*': '1b. What time start winding down?',
        r'.*bed.*time.*commit.*sleep.*': '1.2b. What time did you get into bed & commit to sleep?',
        r'.*wake.*up.*time.*': '6. What time did you wake up?',
        r'.*get.*out.*bed.*time.*': '7. What time did you get out of bed?',
        
        # Duration questions
        r'.*fall.*asleep.*minutes.*': '2. How long do you estimate it took to fall asleep (minutes)?',
        r'.*awakening.*minutes.*': '4. In total, how long did these awakenings last (minutes)?',
        r'.*out.*bed.*minutes.*': '5. When awake during the night, how long did you spend out of bed (minutes)?',
        r'.*sleep.*hours.*total.*': '8. In TOTAL, how many hours of sleep did you get?',
        r'.*bed.*hours.*total.*': '9. In TOTAL, how many hours did you spend in bed?',
        
        # Count/rating questions
        r'.*wake.*up.*night.*times.*': '3. How many times did you wake up during the night?',
        r'.*sleep.*quality.*': '10. Quality of your sleep (1-10)?',
        r'.*naps.*day.*': '11. Did you take naps during the day?',
        r'.*mood.*day.*': '12. Mood during the day (1-10)?',
        r'.*fatigue.*day.*': '13. Fatigue level during the day (1-10)?',
        
        # Alcohol questions
        r'.*alcohol.*drinks.*': '14. If alcohol, how many standard drinks?',
        r'.*alcohol.*type.*': '15. - what type?',
        r'.*alcohol.*time.*': '16. - what time?',
        
        # Other
        r'.*second.*wind.*': '17. Second wind?',
    }
    
    def __init__(self, data: List[List[str]]):
        """Initialize converter with raw Google Sheets data.
        
        Args:
            data: Raw data from Google Sheets (list of rows)
        """
        self.raw_data = data
        self.header = data[0] if data else []
        self.rows = data[1:] if len(data) > 1 else []
        
    def map_form_questions(self) -> Dict[str, str]:
        """Map Google Form questions to standard sleep analysis questions.
        
        Returns:
            Dictionary mapping column indices to standard question text
        """
        question_mapping = {}
        
        for i, header_text in enumerate(self.header):
            header_lower = header_text.lower()
            
            # Try to match against our question patterns
            for pattern, standard_question in self.FORM_QUESTION_MAPPING.items():
                if re.search(pattern, header_lower):
                    question_mapping[i] = standard_question
                    break
        
        return question_mapping
    
    def parse_timestamp_column(self, timestamp_col_idx: int = 0) -> List[datetime.date]:
        """Parse timestamp column to extract dates.
        
        Args:
            timestamp_col_idx: Index of the timestamp column
            
        Returns:
            List of dates for each response
        """
        dates = []
        
        for row in self.rows:
            if len(row) > timestamp_col_idx:
                timestamp_str = row[timestamp_col_idx]
                try:
                    # Parse Google Forms timestamp format
                    # Common formats: "12/31/2024 14:30:45", "2024-12-31 14:30:45", etc.
                    timestamp = pd.to_datetime(timestamp_str)
                    dates.append(timestamp.date())
                except (ValueError, TypeError):
                    # Skip invalid timestamps
                    continue
                    
        return dates
    
    def convert_to_weekly_format(self, question_mapping: Dict[int, str]) -> pd.DataFrame:
        """Convert Google Forms data to weekly sleep analysis format.
        
        Args:
            question_mapping: Mapping from column indices to standard questions
            
        Returns:
            DataFrame in the expected format
        """
        records = []
        dates = self.parse_timestamp_column()
        
        # Process each response
        for i, row in enumerate(self.rows):
            if i >= len(dates):
                continue
                
            date = dates[i]
            record = {'date': date}
            
            # Map each question response
            for col_idx, standard_question in question_mapping.items():
                if col_idx < len(row):
                    raw_value = row[col_idx].strip() if row[col_idx] else ''
                    
                    # Get the column name for this question
                    column_name = QUESTION_TO_COLUMN.get(standard_question)
                    if not column_name:
                        continue
                    
                    # Parse value based on column type
                    parsed_value = self._parse_value(raw_value, column_name)
                    record[column_name] = parsed_value
                    
            records.append(record)
        
        return pd.DataFrame(records)
    
    def _parse_value(self, value: str, column_name: str) -> Any:
        """Parse a form response value based on the expected column type.
        
        Args:
            value: Raw form response value
            column_name: Target column name
            
        Returns:
            Parsed value in the appropriate type
        """
        if not value or value == '.':
            return None
            
        if column_name in TIME_COLS:
            return self._parse_time(value)
        elif column_name in NUMERIC_COLS:
            return self._parse_numeric(value)
        elif column_name in STRING_COLS:
            return value
        else:
            # Default to string
            return value
    
    def _parse_time(self, value: str) -> Optional[datetime.time]:
        """Parse time value from form response."""
        try:
            # Handle various time formats
            time_obj = pd.to_datetime(value).time()
            return time_obj
        except (ValueError, TypeError):
            return None
    
    def _parse_numeric(self, value: str) -> Optional[float]:
        """Parse numeric value from form response."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


def fetch_google_forms_data(
    sheets_url: str,
    credentials_path: str = 'credentials.json',
    range_name: str = 'A:Z'
) -> pd.DataFrame:
    """Fetch and convert Google Forms data to sleep analysis format.
    
    Args:
        sheets_url: Google Sheets URL
        credentials_path: Path to Google API credentials
        range_name: Range to fetch from the sheet
        
    Returns:
        DataFrame in sleep analysis format
    """
    # Initialize fetcher and converter
    fetcher = GoogleSheetsDataFetcher(credentials_path)
    spreadsheet_id = fetcher.extract_spreadsheet_id(sheets_url)
    
    # Fetch raw data
    raw_data = fetcher.fetch_data(spreadsheet_id, range_name)
    
    # Convert to our format
    converter = GoogleFormsDataConverter(raw_data)
    question_mapping = converter.map_form_questions()
    
    return converter.convert_to_weekly_format(question_mapping)


def save_google_forms_as_log(
    sheets_url: str,
    output_path: str,
    credentials_path: str = 'credentials.json'
) -> None:
    """Fetch Google Forms data and save as a text log file.
    
    Args:
        sheets_url: Google Sheets URL
        output_path: Path to save the log file
        credentials_path: Path to Google API credentials
    """
    df = fetch_google_forms_data(sheets_url, credentials_path)
    
    # Group by week and generate log format
    # This is a simplified implementation - you may want to customize based on your exact needs
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Sleep log generated from Google Forms data\n\n")
        
        # Group data by week (Sunday to Saturday)
        df['week_start'] = df['date'].dt.to_period('W-SAT').dt.start_time.dt.date
        
        for week_start, week_df in df.groupby('week_start'):
            week_end = week_start + datetime.timedelta(days=6)
            f.write(f"    {week_start.strftime('%m/%d')}-{week_end.strftime('%m/%d')}\n")
            
            # Write each question with daily values
            for question, column in QUESTION_TO_COLUMN.items():
                if column in week_df.columns:
                    values = []
                    for _, row in week_df.iterrows():
                        val = row[column]
                        if pd.isna(val) or val is None:
                            values.append('.')
                        elif isinstance(val, datetime.time):
                            values.append(val.strftime('%I:%M%p').lower())
                        else:
                            values.append(str(val))
                    
                    f.write(f"        {question} {' '.join(values)}\n")
            f.write("\n")