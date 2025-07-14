"""Helper functions for working with Google Sheets."""

import os
import subprocess
import urllib.parse
from typing import Optional


def extract_spreadsheet_id(url: str) -> Optional[str]:
    """Extract the spreadsheet ID from a Google Sheets URL.
    
    Args:
        url: Google Sheets URL
        
    Returns:
        Spreadsheet ID or None if not found
    """
    # Handle various Google Sheets URL formats
    if '/spreadsheets/d/' in url:
        # Extract ID from URL like: https://docs.google.com/spreadsheets/d/ID/edit...
        parts = url.split('/spreadsheets/d/')
        if len(parts) > 1:
            id_part = parts[1].split('/')[0]
            return id_part
    return None


def get_csv_export_url(spreadsheet_id: str, sheet_gid: Optional[str] = None) -> str:
    """Generate CSV export URL for a Google Sheets spreadsheet.
    
    Args:
        spreadsheet_id: The spreadsheet ID
        sheet_gid: Optional sheet GID (specific tab)
        
    Returns:
        CSV export URL
    """
    base_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export"
    params = {"format": "csv"}
    
    if sheet_gid:
        params["gid"] = sheet_gid
    
    query_string = urllib.parse.urlencode(params)
    return f"{base_url}?{query_string}"


def download_csv_from_sheets(url: str, output_path: str) -> bool:
    """Download CSV data from Google Sheets URL.
    
    Args:
        url: Google Sheets URL or direct CSV export URL
        output_path: Path to save the CSV file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # If it's a regular Google Sheets URL, convert to CSV export URL
        if '/spreadsheets/d/' in url and 'export' not in url:
            spreadsheet_id = extract_spreadsheet_id(url)
            if not spreadsheet_id:
                print(f"Error: Could not extract spreadsheet ID from URL: {url}")
                return False
            
            # Extract GID if present in the URL fragment
            sheet_gid = None
            if '#gid=' in url:
                sheet_gid = url.split('#gid=')[1]
            
            url = get_csv_export_url(spreadsheet_id, sheet_gid)
        
        # Download the CSV using curl (more reliable than urllib for Google Sheets)
        result = subprocess.run([
            'curl', '-L', '-o', output_path, url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            # Check if the file was created and has content
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"Successfully downloaded CSV to: {output_path}")
                return True
        
        print(f"Error downloading CSV: {result.stderr}")
        return False
        
    except Exception as e:
        print(f"Error downloading CSV from Google Sheets: {e}")
        return False


def sheets_url_to_csv(sheets_url: str, output_dir: str = ".", filename: Optional[str] = None) -> Optional[str]:
    """Convert a Google Sheets URL to a downloaded CSV file.
    
    Args:
        sheets_url: Google Sheets URL
        output_dir: Directory to save the CSV file
        filename: Optional custom filename (will generate one if not provided)
        
    Returns:
        Path to the downloaded CSV file or None if failed
    """
    spreadsheet_id = extract_spreadsheet_id(sheets_url)
    if not spreadsheet_id:
        print(f"Error: Could not extract spreadsheet ID from URL: {sheets_url}")
        return None
    
    if filename is None:
        filename = f"sleep_data_{spreadsheet_id}.csv"
    
    output_path = os.path.join(output_dir, filename)
    
    if download_csv_from_sheets(sheets_url, output_path):
        return output_path
    
    return None


# Example usage instructions
USAGE_INSTRUCTIONS = """
Google Sheets Integration Usage:

1. Basic CSV download from Google Sheets:
   python -c "
   from sleep_analysis.google_sheets_helper import sheets_url_to_csv
   csv_path = sheets_url_to_csv('YOUR_GOOGLE_SHEETS_URL')
   print(f'Downloaded to: {csv_path}')
   "

2. Run analysis with Google Sheets data:
   # First download the CSV
   python -c "
   from sleep_analysis.google_sheets_helper import sheets_url_to_csv
   sheets_url_to_csv('YOUR_SHEETS_URL', 'input', 'sleep_data.csv')
   "
   
   # Then run analysis
   python -m sleep_analysis --csv-file input/sleep_data.csv --output-dir output

3. Direct CSV export URL (if you have the direct export link):
   python -m sleep_analysis --csv-file <(curl -L 'YOUR_CSV_EXPORT_URL') --output-dir output

To get your Google Sheets in the right format:
- Make sure your form responses are in columns with clear question headers
- Include a timestamp column if possible
- Make the sheet publicly readable or use the direct CSV export URL
"""