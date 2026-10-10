import json
import os
import subprocess
import sys
import time
from pathlib import Path
import pytest

from src.fixloop import driver, gate, model, state, tools

# Row 1: Issue file without TEST_NODE
def test_break_row_01_malformed_issue_missing_test_node(sandbox_repo):
    bad_issue = sandbox_repo / "issues" / "bad.md"
    bad_issue.write_text("# Bad Title\n\nNo test node defined.\n", encoding="utf-8")
    subprocess.run(["git", "add", "issues/bad.md"], cwd=str(sandbox_repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add bad issue"], cwd=str(sandbox_repo), check=True, capture_output=True)

    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="bad",
        model="fake",
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 1
    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "stopped"

# Row 2: read_file with ../, absolute path, symlink out of repo
def test_break_row_02_read_file_path_outside_repo(sandbox_repo):
    # Relative path outside repo
    res_rel = tools.read_file(str(sandbox_repo), "../outside.py")
    assert res_rel["ok"] is False
    assert res_rel["error"] == "path_outside_repo"

    # Absolute path outside repo
    res_abs = tools.read_file(str(sandbox_repo), str(Path(sandbox_repo).parent.resolve() / "outside.py"))
    assert res_abs["ok"] is False
    assert res_abs["error"] == "path_outside_repo"

# Row 3: edit_file old absent / appears twice
def test_break_row_03_edit_file_mismatch(sandbox_repo):
    paginate_path = sandbox_repo / "src" / "paginate.py"
    orig_hash = hash(paginate_path.read_text(encoding="utf-8"))

    s = state.default_state()
    # Absent
    res_absent = tools.edit_file(str(sandbox_repo), "src/paginate.py", "def nonexistent():", "pass", s)
    assert res_absent["ok"] is False
    assert res_absent["error"] == "mismatch"
    assert hash(paginate_path.read_text(encoding="utf-8")) == orig_hash

    # Duplicate
    paginate_path.write_text("dup\ndup\n", encoding="utf-8")
    orig_hash_dup = hash(paginate_path.read_text(encoding="utf-8"))
    res_dup = tools.edit_file(str(sandbox_repo), "src/paginate.py", "dup", "replaced", s)
    assert res_dup["ok"] is False
    assert res_dup["error"] == "mismatch"
    assert hash(paginate_path.read_text(encoding="utf-8")) == orig_hash_dup

# Row 4: edit_file path tests/... or pytest.ini
def test_break_row_04_edit_file_protected_path(sandbox_repo):
    s = state.default_state()
    test_file = sandbox_repo / "tests" / "test_paginate.py"
    orig_content = test_file.read_text(encoding="utf-8")

    res = tools.edit_file(str(sandbox_repo), "tests/test_paginate.py", "assert", "assert True or", s)
    assert res["ok"] is False
    assert res["error"] == "protected_path"
    assert test_file.read_text(encoding="utf-8") == orig_content

# Row 5: edit_file new text containing pytest.skip / xfail
def test_break_row_05_edit_file_test_skipped(sandbox_repo):
    s = state.default_state()
    paginate_path = sandbox_repo / "src" / "paginate.py"
    orig_content = paginate_path.read_text(encoding="utf-8")

    res = tools.edit_file(
        str(sandbox_repo),
        "src/paginate.py",
        "def page(items, number, size):",
        "import pytest\npytest.skip('bypassed')\ndef page(items, number, size):",
        s
    )
    assert res["ok"] is False
    assert res["error"] == "test_skipped"
    assert paginate_path.read_text(encoding="utf-8") == orig_content

# Row 6: Diff deleting an assert
def test_break_row_06_diff_assert_deleted(sandbox_repo):
    st = state.default_state()
    st["baseline"] = {"exit_code": 1, "tail": "failed"}
    diff = """diff --git a/src/cache.py b/src/cache.py
--- a/src/cache.py
+++ b/src/cache.py
@@ -1,3 +1,2 @@
-assert x == 1
+pass
"""
    res = gate.evaluate(st, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert res["allowed"] is False
    assert res["reason"] == "assert_deleted"

# Row 7: Diff editing a test file only
def test_break_row_07_diff_protected_path_touched(sandbox_repo):
    st = state.default_state()
    st["baseline"] = {"exit_code": 1, "tail": "failed"}
    diff = """diff --git a/tests/test_cache.py b/tests/test_cache.py
--- a/tests/test_cache.py
+++ b/tests/test_cache.py
@@ -1,3 +1,3 @@
-def test_foo():
+def test_foo(): pass
"""
    res = gate.evaluate(st, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert res["allowed"] is False
    assert res["reason"] == "protected_path_touched"

# Row 8: open_pr before any green run
def test_break_row_08_open_pr_node_not_green(sandbox_repo):
    st = state.default_state()
    st["baseline"] = {"exit_code": 1, "tail": "failed"}
    diff = """diff --git a/src/cache.py b/src/cache.py
--- a/src/cache.py
+++ b/src/cache.py
@@ -1,1 +1,2 @@
+# edit
"""
    res = gate.evaluate(st, diff, lambda: {"node_exit": 1, "file_exit": 1})
    assert res["allowed"] is False
    assert res["reason"] == "node_not_green"

# Row 9: Unknown tool name
def test_break_row_09_unknown_tool_rejection(sandbox_repo):
    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="03",
        model="fake",
        model_mode="unknown_tool",
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 1
    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "stopped"
    assert s["rejections"] >= driver.MAX_REJECTIONS

# Row 10: Non-JSON model output
def test_break_row_10_non_json_model_output(sandbox_repo):
    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="03",
        model="fake",
        model_mode="invalid_json",
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 1
    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "stopped"
    assert s["rejections"] >= driver.MAX_REJECTIONS

# Row 11: Model loops on open_pr / junk
def test_break_row_11_junk_loop_rejections_exhausted(sandbox_repo):
    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="03",
        model="fake",
        model_mode="junk_loop",
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 1
    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "stopped"
    assert s["gate_rejects"] >= 2

# Row 12: run_tests with another node id or -x --pdb
def test_break_row_12_run_tests_invalid_node_id(sandbox_repo):
    s = state.default_state()
    s["test_node"] = "tests/test_paginate.py::test_page_size_is_exact"
    res = tools.run_tests("tests/test_other.py::test_unauthorized -x --pdb", s)
    assert res["ok"] is False
    assert res["error"] == "invalid_node_id"

# Row 13: Second process while lock held
def test_break_row_13_lock_held_exits_2(sandbox_repo):
    state_file = sandbox_repo / ".fixloop" / "state.json"
    lock_file = state_file.with_suffix(".lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        lock_file.write_text(json.dumps({"pid": proc.pid, "ts": time.time()}), encoding="utf-8")
        cfg = driver.Config(
            repo=str(sandbox_repo),
            issue="01",
            model="fake",
            state=str(state_file),
        )
        exit_code = driver.run(cfg)
        assert exit_code == 2
    finally:
        proc.terminate()
        proc.wait()

# Row 14: Stale lock (dead pid)
def test_break_row_14_stale_lock_recovered(sandbox_repo):
    state_file = sandbox_repo / ".fixloop" / "state.json"
    lock_file = state_file.with_suffix(".lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    # Stale lock with dead PID
    lock_file.write_text(json.dumps({"pid": 999999, "ts": time.time()}), encoding="utf-8")

    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="01",
        model="fake",
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 0
    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "passed"

# Row 15: Missing API key or model id with --model openai / anthropic
def test_break_row_15_missing_api_key_exits_2(sandbox_repo, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.delenv("FIXLOOP_MODEL", raising=False)

    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="01",
        model="openai",
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 2

# Row 16: Planted secret in env
def test_break_row_16_planted_secret_invisible_in_subprocess(sandbox_repo, monkeypatch):
    monkeypatch.setenv("FIXLOOP_PLANTED_SECRET", "super_classified_secret_xyz")
    inspect_node = "tests/test_inspect.py::test_inspect_env"
    inspect_file = sandbox_repo / "tests" / "test_inspect.py"
    inspect_file.write_text(
        "import os\n"
        "def test_inspect_env():\n"
        "    assert 'FIXLOOP_PLANTED_SECRET' not in os.environ\n",
        encoding="utf-8"
    )
    st = state.default_state()
    st["repo"] = str(sandbox_repo)
    res = tools.run_tests_raw(st, node_id=inspect_node)
    assert res["exit_code"] == 0

# Row 17: Test hangs (timeout)
def test_break_row_17_test_hangs_timeout_exit_124(sandbox_repo):
    hang_node = "tests/test_hang.py::test_hang_forever"
    hang_file = sandbox_repo / "tests" / "test_hang.py"
    hang_file.write_text(
        "import time\n"
        "def test_hang_forever():\n"
        "    time.sleep(10)\n",
        encoding="utf-8"
    )
    st = state.default_state()
    st["repo"] = str(sandbox_repo)
    res = tools.run_tests_raw(st, node_id=hang_node, timeout=1)
    assert res["exit_code"] == 124

# Row 18: Dirty repo at start
def test_break_row_18_dirty_repo_exits_2(sandbox_repo):
    dirty = sandbox_repo / "uncommitted.txt"
    dirty.write_text("dirty content", encoding="utf-8")

    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="03",
        model="fake",
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 2

# Row 19: Token cap exceeded
def test_break_row_19_token_cap_exceeded_stops(sandbox_repo):
    state_file = sandbox_repo / ".fixloop" / "state.json"
    # Setting max_tokens_per_run=5 ensures that after first action (10 tokens), budget is exceeded
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="01",
        model="fake",
        max_tokens_per_run=5,
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 1
    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "stopped"

# Row 20: --model fake with headline --out
def test_break_row_20_fake_model_headline_out_refused(sandbox_repo):
    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="03",
        model="fake",
        out="evidence/baseline.json",
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 2
