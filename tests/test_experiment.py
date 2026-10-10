import json
from pathlib import Path
import pytest

from src.fixloop import experiment

def test_arm_definitions():
    """Verify that arm definitions strictly map to flags in Section 5."""
    assert experiment.ARM_DEFS["baseline"] == {"max_attempts": 1, "gate": False, "lookup": False}
    assert experiment.ARM_DEFS["nogate"] == {"max_attempts": 2, "gate": False, "lookup": True}
    assert experiment.ARM_DEFS["removal"] == {"max_attempts": 2, "gate": True, "lookup": False}
    assert experiment.ARM_DEFS["full"] == {"max_attempts": 2, "gate": True, "lookup": True}

def test_check_red_to_green_recovery():
    """Verify detection of attempt 1 red then attempt 2 green recovery."""
    # Attempt 1 red, attempt 2 green, oracle resolved -> True
    recovered_record = {
        "runs": [
            {"attempt": 1, "exit_code": 1},
            {"attempt": 2, "exit_code": 0},
        ],
        "oracle": {"resolved": True}
    }
    assert experiment.check_red_to_green_recovery(recovered_record) is True

    # Attempt 1 green -> False (not a recovery, solved first try)
    first_try_green = {
        "runs": [{"attempt": 1, "exit_code": 0}],
        "oracle": {"resolved": True}
    }
    assert experiment.check_red_to_green_recovery(first_try_green) is False

    # Attempt 2 red -> False
    failed_record = {
        "runs": [
            {"attempt": 1, "exit_code": 1},
            {"attempt": 2, "exit_code": 1},
        ],
        "oracle": {"resolved": False}
    }
    assert experiment.check_red_to_green_recovery(failed_record) is False

def test_generate_summary():
    """Verify statistical rate table generation for both JSON and Markdown."""
    mock_results = [
        # Full arm, issue 01: 2 trials, both resolved, 0 false PR
        {"arm": "full", "issue_id": "01", "attempt": 1, "tokens": 1000, "cost_usd": 0.001, "oracle": {"resolved": True}, "false_pr": False, "runs": [{"exit_code": 0}]},
        {"arm": "full", "issue_id": "01", "attempt": 1, "tokens": 1200, "cost_usd": 0.0012, "oracle": {"resolved": True}, "false_pr": False, "runs": [{"exit_code": 0}]},
        # Baseline arm, issue 01: 2 trials, 1 resolved, 1 false PR
        {"arm": "baseline", "issue_id": "01", "attempt": 1, "tokens": 800, "cost_usd": 0.0008, "oracle": {"resolved": False}, "false_pr": True, "runs": [{"exit_code": 0}]},
        {"arm": "baseline", "issue_id": "01", "attempt": 1, "tokens": 800, "cost_usd": 0.0008, "oracle": {"resolved": True}, "false_pr": False, "runs": [{"exit_code": 0}]},
    ]

    summary_data, summary_md = experiment.generate_summary(mock_results, issues=["01"], arms=["baseline", "full"])

    assert "arms" in summary_data
    assert summary_data["arms"]["full"]["01"]["resolved_rate"] == 1.0
    assert summary_data["arms"]["full"]["01"]["false_pr_rate"] == 0.0
    assert summary_data["arms"]["baseline"]["01"]["false_pr_rate"] == 0.5

    assert "# FixLoop Experiment Summary" in summary_md
    assert "| `full` | `01` | 2 | 100.0% (2/2) | 0.0% (0/2) |" in summary_md

def test_select_recovery_example(tmp_path):
    """Verify recovery example selection rule and fallback."""
    out_file = tmp_path / "recovery.json"

    # When no recovery exists
    no_rec_results = [{"arm": "full", "runs": [{"exit_code": 0}], "oracle": {"resolved": True}}]
    res = experiment.select_recovery_example(no_rec_results, out_file)
    assert res is None
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["status"] == "not_run"

    # When a recovery exists
    rec_results = [
        {"arm": "full", "issue_id": "03", "trial": 2, "runs": [{"exit_code": 1}, {"exit_code": 0}], "oracle": {"resolved": True}}
    ]
    res2 = experiment.select_recovery_example(rec_results, out_file)
    assert res2 is not None
    assert res2["selected_example_index"] == 0
    data2 = json.loads(out_file.read_text(encoding="utf-8"))
    assert "trial_file" in data2
