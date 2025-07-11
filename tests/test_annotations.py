import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tests.test_log_parser  # ensure pandas stub is available

from sleep_analysis.log_parser import export_single_weeks_csv


def test_save_week_log_annotations(tmp_path):
    log_path = 'tests/input/log-annotations-week.txt'
    out_dir = tmp_path
    export_single_weeks_csv(log_path, out_dir)
    expected = 'tests/output_expected/annotations-2025--06-19--06-25.md'
    out_file = os.path.join(out_dir, 'annotations-2025--06-19--06-25.md')
    assert os.path.exists(out_file)
    with open(out_file) as f, open(expected) as g:
        assert f.read() == g.read()
