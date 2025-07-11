import os
import filecmp

from sleep_analysis.log_parser import export_single_weeks_csv


def test_export_single_weeks_csv(tmp_path):
    log_path = 'tests/input/log-pivot.txt'
    out_dir = tmp_path
    export_single_weeks_csv(log_path, out_dir)
    expected = 'tests/output_expected/data-2025--06-19--06-25.csv'
    out_file = os.path.join(out_dir, 'data-2025--06-19--06-25.csv')
    assert os.path.exists(out_file)
    assert filecmp.cmp(out_file, expected, shallow=False)
