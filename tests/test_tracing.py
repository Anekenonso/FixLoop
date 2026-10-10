import ast
import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from src.fixloop import driver, tracing

@pytest.fixture
def temp_sandbox():
    """Create an isolated sandbox repository for acceptance tests."""
    template_dir = Path("sandbox_template").resolve()
    temp_dir = Path(tempfile.mkdtemp(prefix="fixloop_tracing_test_"))
    try:
        shutil.copytree(str(template_dir), str(temp_dir), dirs_exist_ok=True)
        # Initialize git repo with fixture commit
        driver.subprocess.run(["git", "init"], cwd=str(temp_dir), check=True, capture_output=True)
        driver.subprocess.run(["git", "config", "user.name", "fixture"], cwd=str(temp_dir), check=True, capture_output=True)
        driver.subprocess.run(["git", "config", "user.email", "f@x"], cwd=str(temp_dir), check=True, capture_output=True)
        driver.subprocess.run(["git", "add", "-A"], cwd=str(temp_dir), check=True, capture_output=True)
        driver.subprocess.run(["git", "commit", "-m", "fixture"], cwd=str(temp_dir), check=True, capture_output=True)
        yield temp_dir
    finally:
        shutil.rmtree(str(temp_dir), ignore_errors=True)

def test_fake_model_spans_schema_and_fields(temp_sandbox):
    """Phase 5 Acceptance: Fake model run produces evidence/spans.jsonl with all 14 fields."""
    cfg = driver.Config(
        repo=str(temp_sandbox),
        issue="03",
        model="fake",
        arm="full",
        max_attempts=2,
    )
    exit_code = driver.run(cfg)
    assert exit_code == 0, "Full arm run should exit 0 on clean resolution"

    spans_path = temp_sandbox / "evidence" / "spans.jsonl"
    assert spans_path.is_file(), "evidence/spans.jsonl must exist after driver run"

    lines = [l.strip() for l in spans_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 3, "Should have logged at least baseline and tool call spans"

    required_fields = {
        "span_id": str,
        "parent_span_id": (str, type(None)),
        "run_id": str,
        "attempt": int,
        "name": str,
        "tool": str,
        "args_redacted": dict,
        "exit_code": (int, type(None)),
        "tail": str,
        "diff": str,
        "cost_usd": (float, int),
        "tokens": int,
        "recovery_of": (str, type(None)),
        "model_id": str,
    }

    seen_tools = set()
    has_recovery_of = False

    for idx, line in enumerate(lines):
        record = json.loads(line)
        for field, expected_type in required_fields.items():
            assert field in record, f"Span {idx} missing required field '{field}'"
            assert isinstance(record[field], expected_type), (
                f"Span {idx} field '{field}' has wrong type {type(record[field])}, expected {expected_type}"
            )

        # Check tail line count invariant (max 80 lines)
        tail_lines = record["tail"].splitlines()
        assert len(tail_lines) <= 80, f"Span {idx} tail has {len(tail_lines)} lines, exceeding 80 max lines"

        seen_tools.add(record["tool"])
        if record["recovery_of"]:
            has_recovery_of = True

    # Baseline run is tool="run_tests_raw", attempt 0
    first_record = json.loads(lines[0])
    assert first_record["attempt"] == 0
    assert first_record["tool"] == "run_tests_raw"
    assert first_record["name"] == "baseline_run"
    assert first_record["parent_span_id"] is None

    # Full arm attempt 2 called trace_lookup, so recovery_of must be recorded on that span
    assert "trace_lookup" in seen_tools
    assert has_recovery_of, "trace_lookup span must have recovery_of set"

def test_spans_written_without_neatlogs_api_key(temp_sandbox, monkeypatch):
    """Phase 5 Acceptance: Spans JSONL must be written even with no NEATLOGS_API_KEY."""
    monkeypatch.delenv("NEATLOGS_API_KEY", raising=False)
    
    # Verify init_tracing returns False gracefully
    init_res = tracing.init_tracing("test-no-key")
    assert init_res is False, "init_tracing must return False when NEATLOGS_API_KEY is unset"

    cfg = driver.Config(
        repo=str(temp_sandbox),
        issue="01",
        model="fake",
        arm="full",
        max_attempts=1,
    )
    exit_code = driver.run(cfg)
    assert exit_code == 0

    spans_path = temp_sandbox / "evidence" / "spans.jsonl"
    assert spans_path.is_file(), "spans.jsonl must be written even without API key"
    records = [json.loads(l) for l in spans_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(records) > 0

def test_doctor_local_evidence_valid():
    """Phase 5 Acceptance: evidence/doctor-local.json exists and reports pass."""
    doctor_path = Path("evidence/doctor-local.json").resolve()
    assert doctor_path.is_file(), "evidence/doctor-local.json must exist"

    data = json.loads(doctor_path.read_text(encoding="utf-8"))
    assert data.get("status") == "pass", f"Doctor status must be 'pass', got {data.get('status')}"
    assert data.get("mode") == "local"
    assert data.get("format_version") == "neatlogs.doctor/v2"

def test_model_sdk_not_imported_at_top_level():
    """Phase 5 Acceptance: Model SDKs (openai/anthropic) must not be imported at top-level before neatlogs.init."""
    model_py_path = Path("src/fixloop/model.py").resolve()
    assert model_py_path.is_file()

    tree = ast.parse(model_py_path.read_text(encoding="utf-8"), filename=str(model_py_path))
    
    # Check top-level statements for direct imports of openai or anthropic
    forbidden_modules = {"openai", "anthropic"}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden_modules, (
                    f"Top-level import of '{alias.name}' detected in model.py. "
                    "Model SDK must only be imported after neatlogs.init"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                base_pkg = node.module.split(".")[0]
                assert base_pkg not in forbidden_modules, (
                    f"Top-level import from '{node.module}' detected in model.py. "
                    "Model SDK must only be imported after neatlogs.init"
                )

def test_redact_sensitive_args():
    """Verify sensitive keys are redacted from args dict in spans."""
    raw_args = {
        "path": "src/cache.py",
        "api_key": "sk-secret123",
        "secret_token": "tok_xyz",
        "password": "pass",
        "auth_header": "Bearer abc",
        "credential_data": "cred",
        "count": 42
    }
    redacted = tracing.redact_args(raw_args)
    assert redacted["path"] == "src/cache.py"
    assert redacted["count"] == 42
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["secret_token"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["auth_header"] == "[REDACTED]"
    assert redacted["credential_data"] == "[REDACTED]"

def test_tail_truncation_max_80_lines(tmp_path):
    """Verify log_span truncates tail output to at most 80 lines."""
    long_tail = "\n".join(f"line_{i}" for i in range(120))
    spans_file = tmp_path / "spans.jsonl"
    
    rec = tracing.log_span(
        spans_file,
        span_id="span_test",
        run_id="run_test",
        attempt=1,
        name="test_tool",
        tool="test_tool",
        tail=long_tail
    )
    
    lines = rec["tail"].splitlines()
    assert len(lines) == 80
    assert lines[0] == "line_40"
    assert lines[-1] == "line_119"
