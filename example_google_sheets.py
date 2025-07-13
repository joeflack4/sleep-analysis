"""Example demonstrating Google Sheets integration."""

import os
import tempfile
from sleep_analysis.csv_parser import parse_google_sheets_csv
from sleep_analysis.__main__ import run_analysis

def create_sample_google_sheets_csv():
    """Create a sample CSV that mimics Google Sheets export format."""
    csv_content = """Timestamp,What time start winding down?,What time did you get into bed & commit to sleep?,How long do you estimate it took to fall asleep (minutes)?,How many times did you wake up during the night?,In total how long did these awakenings last (minutes)?,When awake during the night how long did you spend out of bed (minutes)?,What time did you wake up?,What time did you get out of bed?,In TOTAL how many hours of sleep did you get?,In TOTAL how many hours did you spend in bed?,Quality of your sleep (1-10)?,Did you take naps during the day?,Mood during the day (1-10)?,Fatigue level during the day (1-10)?,If alcohol how many standard drinks?,Second wind?
2025-01-01T22:30:00,10:30 PM,11:00 PM,15,0,0,0,7:00 AM,7:15 AM,8,8.5,8,No,8,3,0,No
2025-01-02T22:45:00,10:45 PM,11:15 PM,20,1,5,0,7:30 AM,7:45 AM,7.5,8,7,No,7,4,1,No
2025-01-03T22:20:00,10:20 PM,10:50 PM,10,0,0,0,6:45 AM,7:00 AM,8.5,8.75,9,No,9,2,0,No
2025-01-04T22:15:00,10:15 PM,10:45 PM,12,1,3,0,7:15 AM,7:30 AM,8,8.5,7,No,8,3,0,No
2025-01-05T23:00:00,11:00 PM,11:30 PM,25,2,10,5,8:00 AM,8:15 AM,7.5,8.75,6,No,6,5,2,Yes"""
    
    temp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(temp_dir, 'sample_google_sheets.csv')
    
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write(csv_content)
    
    return csv_path, temp_dir

def main():
    """Demonstrate Google Sheets integration."""
    print("Google Sheets Integration Example")
    print("=" * 40)
    
    # Create sample data
    csv_path, temp_dir = create_sample_google_sheets_csv()
    
    try:
        print(f"1. Created sample CSV at: {csv_path}")
        
        # Parse the CSV
        print("\n2. Parsing CSV data...")
        df = parse_google_sheets_csv(csv_path)
        print(f"   - Parsed {len(df)} records")
        print(f"   - Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"   - Columns: {', '.join(df.columns)}")
        
        # Run full analysis
        print("\n3. Running full analysis...")
        output_dir = os.path.join(temp_dir, 'output')
        run_analysis(csv_path, output_dir, input_format='csv')
        
        # Show results
        print(f"\n4. Analysis complete! Results saved to: {output_dir}")
        
        # List generated files
        if os.path.exists(output_dir):
            files = os.listdir(output_dir)
            print("   Generated files:")
            for file in sorted(files):
                if os.path.isfile(os.path.join(output_dir, file)):
                    print(f"   - {file}")
        
        # Show a sample of the stats
        stats_file = os.path.join(output_dir, 'stats.tsv')
        if os.path.exists(stats_file):
            print("\n5. Sample statistics:")
            with open(stats_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[:10]):  # Show first 10 lines
                    print(f"   {line.strip()}")
                if len(lines) > 10:
                    print(f"   ... and {len(lines) - 10} more rows")
        
        print(f"\n6. To use with your own Google Sheets:")
        print("   python -m sleep_analysis --sheets-url 'YOUR_GOOGLE_SHEETS_URL' --output-dir output")
        print("   or")
        print("   python -m sleep_analysis --csv-file 'your_exported.csv' --output-dir output")
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\n7. Cleaned up temporary files")

if __name__ == '__main__':
    main()