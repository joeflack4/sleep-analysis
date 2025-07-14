#!/usr/bin/env python3
"""
Example script showing how to use Google Sheets integration.

This script demonstrates:
1. Setting up Google Sheets API credentials
2. Fetching data from Google Forms responses
3. Running sleep analysis on the data

Prerequisites:
1. Install Google Sheets API dependencies:
   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

2. Set up Google API credentials:
   - Go to Google Cloud Console
   - Enable Google Sheets API
   - Create OAuth 2.0 credentials
   - Download credentials.json

Usage:
    python examples/google_sheets_example.py
"""

import os
import sys

# Add the parent directory to Python path so we can import sleep_analysis
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from sleep_analysis.google_sheets_integration import (
        fetch_google_forms_data,
        save_google_forms_as_log,
        GoogleSheetsDataFetcher,
        GOOGLE_SHEETS_AVAILABLE
    )
    from sleep_analysis import run_analysis
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you've installed the required dependencies:")
    print("pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)


def main():
    """Main example function."""
    
    if not GOOGLE_SHEETS_AVAILABLE:
        print("Google Sheets API libraries not available!")
        print("Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return
    
    # Example Google Sheets URL (replace with your actual URL)
    sheets_url = "https://docs.google.com/spreadsheets/d/1dOFbfTFReRhJUxjj8TdLvsyOnBJ_WlPvpqXwj48WgVU/edit"
    
    print("Google Sheets Sleep Analysis Example")
    print("=" * 40)
    
    # Example 1: Extract spreadsheet ID from URL
    print(f"1. Extracting spreadsheet ID from URL:")
    print(f"   URL: {sheets_url}")
    
    try:
        fetcher = GoogleSheetsDataFetcher()
        spreadsheet_id = fetcher.extract_spreadsheet_id(sheets_url)
        print(f"   Spreadsheet ID: {spreadsheet_id}")
    except Exception as e:
        print(f"   Error: {e}")
        return
    
    # Example 2: Check for credentials
    print(f"\n2. Checking for credentials:")
    credentials_path = 'credentials.json'
    if os.path.exists(credentials_path):
        print(f"   ✓ Found credentials file: {credentials_path}")
    else:
        print(f"   ✗ Credentials file not found: {credentials_path}")
        print("   Please download your Google API credentials and save as 'credentials.json'")
        print("   See README.md for setup instructions")
        return
    
    # Example 3: Demonstrate the workflow (without actually fetching data)
    print(f"\n3. Example workflow:")
    print("   The following steps would be performed:")
    print("   a) Authenticate with Google Sheets API")
    print("   b) Fetch data from the spreadsheet")
    print("   c) Map Google Form questions to sleep analysis questions")
    print("   d) Convert data to the standard format")
    print("   e) Run sleep analysis and generate reports")
    
    # Example 4: Show how to use from command line
    print(f"\n4. Command line usage:")
    print("   python -m sleep_analysis \\")
    print(f"     --google-sheets-url \"{sheets_url}\" \\")
    print("     --output-dir output")
    
    print(f"\n5. For actual data processing:")
    print("   Uncomment the lines below and run with valid credentials")
    
    # Commented out actual data fetching to avoid authentication in example
    """
    try:
        # Fetch and analyze data
        output_dir = 'output_google_sheets'
        save_google_forms_as_log(sheets_url, 'temp_log.txt', credentials_path)
        run_analysis('temp_log.txt', output_dir)
        print(f"Analysis complete! Check {output_dir} for results.")
        
        # Clean up
        if os.path.exists('temp_log.txt'):
            os.unlink('temp_log.txt')
            
    except Exception as e:
        print(f"Error processing data: {e}")
    """


if __name__ == '__main__':
    main()