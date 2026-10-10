import json
import subprocess
import pytest
from pathlib import Path
from src.fixloop import driver

def test_generic_cli_custom_issue_and_test(sandbox_repo):
    """Test --issue-file and --test overrides work seamlessly."""
    custom_issue = sandbox_repo / "custom_bug.md"
    custom_issue.write_text(
        "# Custom Bug\n\nCustom issue description.\n",
        encoding="utf-8"
    )
    subprocess.run(["git", "add", "custom_bug.md"], cwd=str(sandbox_repo), check=True)
    subprocess.run(["git", "commit", "-m", "add custom bug"], cwd=str(sandbox_repo), check=True)

    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        issue_file=str(custom_issue),
        test="tests/test_paginate.py::test_page_size_is_exact",
        model="fake",
        state=str(state_file),
    )
    exit_code = driver.run(cfg)
    assert exit_code == 0
    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["status"] == "passed"
    assert s["issue"]["title"] == "Custom Bug"
    assert s["test_node"] == "tests/test_paginate.py::test_page_size_is_exact"

    # Check trust receipt was generated
    receipt_file = sandbox_repo / "evidence" / f"receipt-{s['run_id']}.md"
    assert receipt_file.is_file()
    receipt_content = receipt_file.read_text(encoding="utf-8")
    assert "# FixLoop Trust Receipt" in receipt_content
    assert "**Verdict:** `FIXED, gate ok`" in receipt_content

def test_generic_cli_custom_edit_root_confinement(sandbox_repo):
    """Test --edit-root confines edits to the specified folder."""
    # Create custom package directory pkg/
    pkg_dir = sandbox_repo / "pkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")

    test_file = sandbox_repo / "tests" / "test_calc.py"
    test_file.write_text("from pkg.calc import add\ndef test_add(): assert add(1, 2) == 3\n", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=str(sandbox_repo), check=True)
    subprocess.run(["git", "commit", "-m", "add pkg"], cwd=str(sandbox_repo), check=True)

    state_file = sandbox_repo / ".fixloop" / "state.json"
    cfg = driver.Config(
        repo=str(sandbox_repo),
        edit_root="pkg/",
        test="tests/test_calc.py::test_add",
        model="fake",
        state=str(state_file),
    )
    # The default fake model does not target pkg/calc.py, so it will stop cleanly
    exit_code = driver.run(cfg)
    s = json.loads(state_file.read_text(encoding="utf-8"))
    assert s["edit_root"] == "pkg/"
