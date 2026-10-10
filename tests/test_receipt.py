import json
import pytest
from src.fixloop import receipt, state

def test_trust_receipt_fixed_run():
    s = state.default_state()
    s.update({
        "run_id": "test-run-123",
        "issue_id": "03",
        "issue": {"title": "Swallowed exception in cache", "body": "Fix it"},
        "test_node": "tests/test_cache.py::test_compute_failure_contract",
        "status": "passed",
        "attempt": 2,
        "max_attempts": 2,
        "tokens": 4200,
        "cost_usd": 0.0012,
        "oracle": {"resolved": True, "node_exit": 0, "file_exit": 0},
        "last_span_id": "span_open_pr_abc123"
    })
    diff = """diff --git a/src/cache.py b/src/cache.py
--- a/src/cache.py
+++ b/src/cache.py
@@ -1,2 +1,2 @@
-        return _last
+        raise
"""
    doc = receipt.generate_receipt(s, diff_text=diff)
    assert "# FixLoop Trust Receipt" in doc
    assert "**Verdict:** `FIXED, gate ok`" in doc
    assert "Swallowed exception in cache" in doc
    assert "`tests/test_cache.py::test_compute_failure_contract`" in doc
    assert "`src/cache.py`" in doc
    assert "+1 / -1" in doc
    assert "Tests and Config Unchanged:** **yes**" in doc
    assert "2 / 2" in doc
    assert "4,200" in doc
    assert "$0.00120 USD" in doc
    assert "Local span ID: `span_open_pr_abc123`" in doc

def test_trust_receipt_stopped_run():
    s = state.default_state()
    s.update({
        "run_id": "test-run-stopped",
        "issue_id": "01",
        "issue": {"title": "Off by one error", "body": "Pagination bug"},
        "test_node": "tests/test_paginate.py::test_page_size_is_exact",
        "status": "stopped",
        "hint": "attempts_exhausted",
        "attempt": 2,
        "max_attempts": 2,
        "tokens": 8000,
        "cost_usd": 0.002,
        "oracle": {"resolved": False, "node_exit": 1, "file_exit": 1},
        "last_span_id": "span_run_tests_xyz"
    })
    doc = receipt.generate_receipt(s)
    assert "**Verdict:** `NOT FIXED: attempts_exhausted`" in doc
    assert "FAILED / UNVERIFIED" in doc

def test_trust_receipt_test_tampering_detected():
    s = state.default_state()
    s["edit_root"] = "src/"
    diff = """diff --git a/tests/test_paginate.py b/tests/test_paginate.py
--- a/tests/test_paginate.py
+++ b/tests/test_paginate.py
@@ -1,2 +1,2 @@
-def test_foo(): assert False
+def test_foo(): pass
"""
    stats = receipt.compute_diff_stats(diff, edit_root="src/")
    assert stats["tests_and_config_untouched"] is False
