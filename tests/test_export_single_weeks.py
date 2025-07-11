import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tests.test_log_parser  # ensure pandas stub is available

from sleep_analysis.log_parser import export_single_weeks_csv


def test_export_single_weeks_csv(tmp_path):
    log_path = 'tests/input/log-pivot.txt'
    out_dir = tmp_path
    export_single_weeks_csv(log_path, out_dir)
    expected = 'tests/output_expected/data-with-questions-2025--06-19--06-25.csv'
    out_file = os.path.join(out_dir, 'data-with-questions-2025--06-19--06-25.csv')
    assert os.path.exists(out_file)
    with open(out_file, 'r', encoding='utf-8') as f_out, open(expected, 'r', encoding='utf-8') as f_exp:
        out_text = f_out.read().replace('\r\n', '\n')
        exp_text = f_exp.read().replace('\r\n', '\n')
    assert out_text == exp_text
