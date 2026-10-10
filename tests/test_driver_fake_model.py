import json
import os
import subprocess
import sys
import time
from pathlib import Path
import pytest

from src.fixloop import driver

def test_driver_issue03_full_arm(sandbox_repo):
    """Issue 03 full arm: red -> comment patch -> red -> trace_lookup -> re-raise -> green -> gate ok -> passed."""
    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="03",
        model="fake",
        arm="full",
        max_attempts=2,
        gate=True,
        lookup=True,
        dry_pr=True,
        state=str(state_file),
    )

    exit_code = driver.run(cfg)
    assert exit_code == 0

    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "passed"
    assert s["attempt"] == 2
    assert s["oracle"]["resolved"] is True
    assert s["false_pr"] is False

    # Check evidence spans file
    spans_file = sandbox_repo / "evidence" / "spans.jsonl"
    assert spans_file.is_file()
    lines = spans_file.read_text(encoding="utf-8").strip().splitlines()
    span_names = [json.loads(line).get("name") for line in lines]
    assert "baseline_run" in span_names
    assert "trace_lookup" in span_names
    assert "open_pr" in span_names

    # Check that cache.py was fixed
    cache_content = (sandbox_repo / "src" / "cache.py").read_text(encoding="utf-8")
    assert "raise" in cache_content

def test_driver_issue03_removal_arm(sandbox_repo):
    """Issue 03 removal arm (--no-trace-lookup): attempt 2 cannot succeed -> stopped, stop file written."""
    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="03",
        model="fake",
        arm="removal",
        max_attempts=2,
        gate=True,
        lookup=False,
        dry_pr=True,
        state=str(state_file),
    )

    exit_code = driver.run(cfg)
    assert exit_code == 1

    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "stopped"
    assert s["oracle"]["resolved"] is False
    assert s["false_pr"] is False

    # Verify stop file written
    stop_files = list((sandbox_repo / "evidence").glob("stop-03-*.md"))
    assert len(stop_files) >= 1
    stop_content = stop_files[0].read_text(encoding="utf-8")
    assert any(r in stop_content for r in ["too_many_rejections", "attempts_exhausted", "mismatch"])

def test_driver_issue03_baseline_ungated_arm(sandbox_repo):
    """Issue 03 baseline ungated arm: ends proposed_ungated with oracle NOT resolved -> false_pr True."""
    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="03",
        model="fake",
        arm="baseline",
        max_attempts=1,
        gate=False,
        lookup=False,
        dry_pr=True,
        state=str(state_file),
    )

    exit_code = driver.run(cfg)
    assert exit_code == 3

    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "proposed_ungated"
    assert s["oracle"]["resolved"] is False
    assert s["false_pr"] is True

def test_driver_issue01_full_arm(sandbox_repo):
    """Issue 01 full arm: fixes off-by-one in one attempt -> passed."""
    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="01",
        model="fake",
        arm="full",
        state=str(state_file),
    )

    exit_code = driver.run(cfg)
    assert exit_code == 0

    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "passed"
    assert s["oracle"]["resolved"] is True
    assert s["false_pr"] is False

def test_driver_issue02_full_arm(sandbox_repo):
    """Issue 02 full arm: fixes dict merge precedence in one attempt -> passed."""
    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="02",
        model="fake",
        arm="full",
        state=str(state_file),
    )

    exit_code = driver.run(cfg)
    assert exit_code == 0

    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "passed"
    assert s["oracle"]["resolved"] is True
    assert s["false_pr"] is False

def test_driver_unknown_tool(sandbox_repo):
    """Unknown tool -> increments rejections -> stops after MAX_REJECTIONS."""
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

def test_driver_invalid_json(sandbox_repo):
    """Invalid JSON output -> increments rejections -> stops after MAX_REJECTIONS."""
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

def test_driver_junk_loop(sandbox_repo):
    """Model loops on premature open_pr -> gate rejects 2 times -> stops."""
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

def test_driver_lock_held_and_stale_lock(sandbox_repo):
    """Lock held by live process -> exit 2; stale lock replaced -> run proceeds."""
    state_file = sandbox_repo / ".fixloop" / "state.json"
    lock_file = state_file.with_suffix(".lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Spawn background dummy process that sleeps for 10 seconds
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        # Write live PID to lock file
        lock_file.write_text(json.dumps({"pid": proc.pid, "ts": time.time()}), encoding="utf-8")

        cfg = driver.Config(
            repo=str(sandbox_repo),
            issue="01",
            model="fake",
            state=str(state_file),
        )
        exit_code = driver.run(cfg)
        assert exit_code == 2  # Exit 2: lock held by another process
    finally:
        proc.terminate()
        proc.wait()

    # 2. Now proc.pid is dead -> stale lock
    assert lock_file.is_file()
    cfg_proceed = driver.Config(
        repo=str(sandbox_repo),
        issue="01",
        model="fake",
        state=str(state_file),
    )
    exit_code = driver.run(cfg_proceed)
    assert exit_code == 0  # Replaced stale lock and succeeded

def test_driver_dirty_repo(sandbox_repo):
    """Dirty repo at start -> exit 2."""
    dirty_file = sandbox_repo / "untracked_file.txt"
    dirty_file.write_text("uncommitted dirty content", encoding="utf-8")

    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="03",
        model="fake",
        state=str(state_file),
    )

    exit_code = driver.run(cfg)
    assert exit_code == 2

def test_driver_missing_test_node(sandbox_repo):
    """Issue file missing TEST_NODE -> exit 1, stop recorded."""
    bad_issue = sandbox_repo / "issues" / "bad.md"
    bad_issue.write_text("# Bad Title\n\nNo test node defined.\n", encoding="utf-8")
    subprocess.run(["git", "add", "issues/bad.md"], cwd=str(sandbox_repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add bad issue without test node"], cwd=str(sandbox_repo), check=True, capture_output=True)

    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue="bad",
        model="fake",
        state=str(state_file),
    )

    exit_code = driver.run(cfg)
    assert exit_code == 1

def test_cli_execution_python_m_fixloop(sandbox_repo):
    """python -m fixloop run --repo <tmp> --issue 03 --model fake exits 0 and prints output."""
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.fixloop",
            "run",
            "--repo",
            str(sandbox_repo),
            "--issue",
            "03",
            "--model",
            "fake"
        ],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0, f"CLI exited with {res.returncode}. Stderr: {res.stderr}"
    assert "State saved to" in res.stdout
    assert "Last span ID:" in res.stdout
