import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import pytest

from src.fixloop import tools

def get_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def test_read_issue_valid_missing_and_malformed(sandbox_repo):
    # Valid issue
    res = tools.read_issue(str(sandbox_repo), "01-paginate")
    assert res["ok"] is True
    assert "Last page item repeats on the next page" in res["title"]
    assert "Page 2 of 10 items" in res["body"]
    assert res["test_node"] == "tests/test_paginate.py::test_page_size_is_exact"

    # Missing issue
    res_missing = tools.read_issue(str(sandbox_repo), "99-nonexistent")
    assert res_missing["ok"] is False
    assert res_missing["error"] == "missing_issue"

    # Break matrix row 1: Issue file without TEST_NODE
    bad_issue = sandbox_repo / "issues" / "bad.md"
    bad_issue.write_text("# Bad Issue\n\nNo test node here\n", encoding="utf-8")
    res_bad = tools.read_issue(str(sandbox_repo), "bad")
    assert res_bad["ok"] is False
    assert res_bad["error"] == "malformed_issue"

def test_read_file_security_and_bounds(sandbox_repo):
    # Break matrix row 2: Path traversal with ../
    res_traversal = tools.read_file(str(sandbox_repo), "../outside.py")
    assert res_traversal["ok"] is False
    assert res_traversal["error"] == "path_outside_repo"

    # Break matrix row 2: Absolute path
    abs_path = str(Path(tempfile.gettempdir()) / "outside.txt")
    res_abs = tools.read_file(str(sandbox_repo), abs_path)
    assert res_abs["ok"] is False
    assert res_abs["error"] == "path_outside_repo"

    # Break matrix row 2: Symlink pointing outside repo
    outside_file = Path(tempfile.gettempdir()) / f"outside_{time.time()}.txt"
    outside_file.write_text("secret outside", encoding="utf-8")
    symlink_path = sandbox_repo / "src" / "symlink_out.py"
    try:
        os.symlink(str(outside_file), str(symlink_path))
        has_symlink = True
    except (OSError, NotImplementedError):
        has_symlink = False

    if has_symlink:
        res_symlink = tools.read_file(str(sandbox_repo), "src/symlink_out.py")
        assert res_symlink["ok"] is False
        assert res_symlink["error"] == "path_outside_repo"

    # Valid read: 1-indexed inclusive numbered lines
    res_valid = tools.read_file(str(sandbox_repo), "src/paginate.py", start=1, end=4)
    assert res_valid["ok"] is True
    lines = res_valid["lines"]
    assert 1 in lines
    assert 4 in lines
    assert "def page(" in lines[1]
    assert "return items[start:end]" in lines[4]

    # File not found inside repo
    res_not_found = tools.read_file(str(sandbox_repo), "src/does_not_exist.py")
    assert res_not_found["ok"] is False
    assert res_not_found["error"] == "file_not_found"

def test_edit_file_mismatch(sandbox_repo):
    target = sandbox_repo / "src" / "paginate.py"
    initial_hash = get_file_hash(target)
    state = {
        "repo": str(sandbox_repo),
        "test_node": "tests/test_paginate.py::test_page_size_is_exact",
        "attempt": 1,
        "edit_root": "src/"
    }

    # Break matrix row 3: old absent -> mismatch, file hash unchanged
    res_absent = tools.edit_file(
        repo=str(sandbox_repo),
        path="src/paginate.py",
        old="def non_existent_function():",
        new="def replacement():",
        state=state
    )
    assert res_absent["ok"] is False
    assert res_absent["error"] == "mismatch"
    assert get_file_hash(target) == initial_hash

    # Break matrix row 3: old appears twice -> mismatch, file hash unchanged
    # Create duplicate pattern in file
    dup_file = sandbox_repo / "src" / "dup.py"
    dup_file.write_text("foo = 1\nfoo = 1\n", encoding="utf-8")
    dup_hash = get_file_hash(dup_file)
    res_dup = tools.edit_file(
        repo=str(sandbox_repo),
        path="src/dup.py",
        old="foo = 1",
        new="foo = 2",
        state=state
    )
    assert res_dup["ok"] is False
    assert res_dup["error"] == "mismatch"
    assert get_file_hash(dup_file) == dup_hash

def test_edit_file_protected_path(sandbox_repo):
    test_file = sandbox_repo / "tests" / "test_paginate.py"
    test_hash = get_file_hash(test_file)
    pytest_ini = sandbox_repo / "pytest.ini"
    ini_hash = get_file_hash(pytest_ini)
    state = {
        "repo": str(sandbox_repo),
        "test_node": "tests/test_paginate.py::test_page_size_is_exact",
        "attempt": 1,
        "edit_root": "src/"
    }

    # Break matrix row 4: path in tests/... rejected, hash unchanged
    res_test = tools.edit_file(
        repo=str(sandbox_repo),
        path="tests/test_paginate.py",
        old="assert page(list(range(10)), 1, 3) == [3, 4, 5]",
        new="assert True",
        state=state
    )
    assert res_test["ok"] is False
    assert res_test["error"] == "protected_path"
    assert get_file_hash(test_file) == test_hash

    # Break matrix row 4: pytest.ini rejected, hash unchanged
    res_ini = tools.edit_file(
        repo=str(sandbox_repo),
        path="pytest.ini",
        old="pythonpath = .",
        new="pythonpath = ./src",
        state=state
    )
    assert res_ini["ok"] is False
    assert res_ini["error"] == "protected_path"
    assert get_file_hash(pytest_ini) == ini_hash

    # Break matrix row 4: outside path rejected
    res_outside = tools.edit_file(
        repo=str(sandbox_repo),
        path="../outside.py",
        old="x = 1",
        new="x = 2",
        state=state
    )
    assert res_outside["ok"] is False
    assert res_outside["error"] == "protected_path"

def test_edit_file_skip_and_xfail_rejected(sandbox_repo):
    target = sandbox_repo / "src" / "paginate.py"
    initial_hash = get_file_hash(target)
    state = {
        "repo": str(sandbox_repo),
        "test_node": "tests/test_paginate.py::test_page_size_is_exact",
        "attempt": 1,
        "edit_root": "src/"
    }

    # Break matrix row 5: new text containing pytest.skip / xfail rejected before write
    skip_samples = [
        "    pytest.skip('skip this')",
        "    import pytest; pytest.mark.skip()",
        "    @pytest.mark.xfail\n    def helper(): pass",
        "    pytest.skipif(True)",
        "    pytest.importorskip('somelib')",
    ]

    for sample in skip_samples:
        res = tools.edit_file(
            repo=str(sandbox_repo),
            path="src/paginate.py",
            old="    end = start + size + 1  # BUG: off by one",
            new=sample,
            state=state
        )
        assert res["ok"] is False
        assert res["error"] == "test_skipped"
        assert get_file_hash(target) == initial_hash

def test_edit_file_success_and_git_commit(sandbox_repo):
    target = sandbox_repo / "src" / "paginate.py"
    state = {
        "repo": str(sandbox_repo),
        "test_node": "tests/test_paginate.py::test_page_size_is_exact",
        "attempt": 1,
        "edit_root": "src/"
    }

    res = tools.edit_file(
        repo=str(sandbox_repo),
        path="src/paginate.py",
        old="    end = start + size + 1  # BUG: off by one",
        new="    end = start + size",
        state=state
    )
    assert res["ok"] is True
    assert "end = start + size" in target.read_text(encoding="utf-8")

    # Verify git commit was created
    log_res = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"],
        cwd=str(sandbox_repo),
        capture_output=True,
        text=True,
        check=True
    )
    assert "fixloop attempt 1: tests/test_paginate.py::test_page_size_is_exact" in log_res.stdout

def test_run_tests_invalid_node_id(sandbox_repo):
    state = {
        "repo": str(sandbox_repo),
        "test_node": "tests/test_paginate.py::test_page_size_is_exact",
    }

    # Break matrix row 12: different node_id
    res_diff = tools.run_tests("tests/test_merge.py::test_right_wins", state)
    assert res_diff["ok"] is False
    assert res_diff["error"] == "invalid_node_id"

    # Break matrix row 12: flag injection with -x --pdb
    res_flags = tools.run_tests("tests/test_paginate.py::test_page_size_is_exact -x --pdb", state)
    assert res_flags["ok"] is False
    assert res_flags["error"] == "invalid_node_id"

    # Arbitrary non-node argument
    res_arb = tools.run_tests("pytest -s", state)
    assert res_arb["ok"] is False
    assert res_arb["error"] == "invalid_node_id"

def test_run_tests_exact_argv_assertion(sandbox_repo, monkeypatch):
    state = {
        "repo": str(sandbox_repo),
        "test_node": "tests/test_paginate.py::test_page_size_is_exact",
    }
    captured_calls = []

    def mock_subprocess_run(cmd, **kwargs):
        captured_calls.append({"cmd": cmd, "kwargs": kwargs})
        class DummyProc:
            returncode = 0
            stdout = "1 passed in 0.05s"
            stderr = ""
        return DummyProc()

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    res = tools.run_tests("tests/test_paginate.py::test_page_size_is_exact", state)
    assert res["ok"] is True
    assert len(captured_calls) == 1

    call = captured_calls[0]
    expected_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_paginate.py::test_page_size_is_exact",
        "-q",
        "--tb=line"
    ]
    assert call["cmd"] == expected_cmd
    assert call["kwargs"]["cwd"] == str(sandbox_repo)
    assert call["kwargs"]["timeout"] == 60
    assert call["kwargs"]["capture_output"] is True
    assert call["kwargs"]["text"] is True

def test_run_tests_planted_secret_invisible(sandbox_repo):
    # Break matrix row 16: Planted secret in env is invisible in pytest subprocess
    secret_key = "FIXLOOP_PLANTED_SECRET"
    secret_val = "planted_super_secret_token_12345"
    os.environ[secret_key] = secret_val

    # Plant a test that verifies secret is absent
    secret_test = sandbox_repo / "tests" / "test_planted_secret.py"
    secret_test.write_text(
        "import os\n"
        "def test_secret_is_strictly_absent():\n"
        f"    assert '{secret_key}' not in os.environ, 'Secret was leaked into subprocess!'\n",
        encoding="utf-8"
    )

    state = {
        "repo": str(sandbox_repo),
        "test_node": "tests/test_planted_secret.py::test_secret_is_strictly_absent",
    }

    res = tools.run_tests_raw(state, node_id="tests/test_planted_secret.py::test_secret_is_strictly_absent")
    assert res["ok"] is True
    assert res["exit_code"] == 0, f"Test failed with output: {res['tail']}"

    # Clean up environment variable
    del os.environ[secret_key]

def test_run_tests_timeout_handling(sandbox_repo):
    # Break matrix row 17: Test hangs -> exit 124
    hang_test = sandbox_repo / "tests" / "test_hang.py"
    hang_test.write_text(
        "import time\n"
        "def test_hang():\n"
        "    time.sleep(10)\n",
        encoding="utf-8"
    )

    state = {
        "repo": str(sandbox_repo),
        "test_node": "tests/test_hang.py::test_hang",
    }

    # Run with 1 second timeout
    res = tools.run_tests_raw(state, node_id="tests/test_hang.py::test_hang", timeout=1)
    assert res["ok"] is True
    assert res["exit_code"] == 124
    assert res["duration_s"] >= 1.0

def test_trace_lookup(sandbox_repo):
    spans_file = sandbox_repo / "evidence" / "spans.jsonl"
    spans_file.parent.mkdir(parents=True, exist_ok=True)
    sample_spans = [
        {"span_id": "span_001", "name": "run_tests", "exit_code": 1, "tail": "assert 4 == 3"},
        {"span_id": "span_002", "name": "edit_file", "ok": True},
    ]
    with open(spans_file, "w", encoding="utf-8") as f:
        for s in sample_spans:
            f.write(json.dumps(s) + "\n")

    state_enabled = {"flags": {"lookup": True}}
    state_disabled = {"flags": {"lookup": False}}

    # Lookup found
    res = tools.trace_lookup("span_001", str(spans_file), state_enabled)
    assert res["ok"] is True
    assert res["span"]["span_id"] == "span_001"
    assert res["span"]["exit_code"] == 1

    # Lookup not found
    res_missing = tools.trace_lookup("span_999", str(spans_file), state_enabled)
    assert res_missing["ok"] is False
    assert res_missing["error"] == "not_found"

    # Lookup disabled with --no-trace-lookup
    res_disabled = tools.trace_lookup("span_001", str(spans_file), state_disabled)
    assert res_disabled.get("disabled") is True

def test_open_pr_length_limits_and_dry_run(sandbox_repo):
    state = {
        "repo": str(sandbox_repo),
        "test_node": "tests/test_paginate.py::test_page_size_is_exact",
        "base_commit": "HEAD",
        "branch": "fixloop/01-test",
        "run_id": "test_run_1",
        "flags": {"dry_pr": True, "gate": True},
        "baseline": {"exit_code": 1, "tail": "assert failed"}
    }

    # Title too long (> 120)
    long_title = "x" * 121
    res_title = tools.open_pr(long_title, "body", state)
    assert res_title["ok"] is False
    assert res_title["reason"] == "title_too_long"

    # Body too long (> 4000)
    long_body = "x" * 4001
    res_body = tools.open_pr("title", long_body, state)
    assert res_body["ok"] is False
    assert res_body["reason"] == "body_too_long"

    # Gate reject: node not green (verify mock returning 1)
    def verify_failing():
        return {"node_exit": 1, "file_exit": 0}

    res_gate_reject = tools.open_pr("Fix paginate", "Fixed off by one", state, verify=verify_failing)
    assert res_gate_reject["ok"] is False
    assert res_gate_reject["allowed"] is False

    # Dry run allowed: verify mock returning 0 and valid edit applied
    # Apply clean edit to paginate.py first so diff exists
    tools.edit_file(
        str(sandbox_repo),
        "src/paginate.py",
        "    end = start + size + 1  # BUG: off by one",
        "    end = start + size",
        state
    )
    def verify_passing():
        return {"node_exit": 0, "file_exit": 0}

    # We need base_commit to be HEAD~1 since an edit was committed
    state["base_commit"] = "HEAD~1"
    res_allowed = tools.open_pr("Fix paginate", "Fixed off by one", state, verify=verify_passing)
    assert res_allowed["ok"] is True
    assert res_allowed["allowed"] is True
    assert res_allowed["pr"] == "dry_run"

    # Check evidence pr body file was written
    pr_body_file = sandbox_repo / "evidence" / "pr-body-test_run_1.md"
    assert pr_body_file.is_file()
    pr_text = pr_body_file.read_text(encoding="utf-8")
    assert "# Fix paginate" in pr_text
    assert "FixLoop Trust Receipt" in pr_text
    assert "Fixed off by one" in pr_text
