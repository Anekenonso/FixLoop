import tempfile
from pathlib import Path
from src.fixloop.state import default_state, save_state, load_state, project_state

def test_state_atomic_save_and_load():
    st = default_state()
    st["run_id"] = "run-123"
    st["issue_id"] = "03"
    st["status"] = "running"
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = str(Path(tmp_dir) / "state.json")
        save_state(st, path)
        loaded = load_state(path)
        assert loaded["run_id"] == "run-123"
        assert loaded["issue_id"] == "03"
        assert loaded["status"] == "running"

def test_project_state_attempt_1():
    st = default_state()
    st["issue"] = {"title": "Test", "body": "Details"}
    st["test_node"] = "tests/test_cache.py::test_contract"
    st["attempt"] = 1
    st["max_attempts"] = 2
    st["runs_used"] = 0
    st["working"] = ["tool result 1"]
    st["baseline"] = {"exit_code": 1, "tail": "failed line"}
    st["edits"] = [{"path": "src/cache.py", "ok": True}]
    
    view = project_state(st)
    assert view["attempt"] == 1
    assert view["runs_remaining"] == 2
    assert view["files_edited"] == ["src/cache.py"]
    assert "previous_attempt" not in view

def test_project_state_attempt_2_with_lookup():
    st = default_state()
    st["attempt"] = 2
    st["max_attempts"] = 2
    st["runs_used"] = 1
    st["flags"]["lookup"] = True
    st["runs"] = [{
        "attempt": 1,
        "exit_code": 1,
        "tail": "attempt 1 failed",
        "span_id": "span-abc",
    }]
    
    view = project_state(st)
    assert view["attempt"] == 2
    assert view["runs_remaining"] == 1
    assert view["previous_attempt"] == {
        "exit_code": 1,
        "span_id": "span-abc",
    }
    # Notice: the failure tail from attempt 1 is NOT present in previous_attempt!
    assert "tail" not in view["previous_attempt"]

def test_project_state_attempt_2_no_lookup():
    st = default_state()
    st["attempt"] = 2
    st["flags"]["lookup"] = False
    st["runs"] = [{
        "attempt": 1,
        "exit_code": 1,
        "span_id": "span-abc",
    }]
    
    view = project_state(st)
    assert view["previous_attempt"] == {
        "exit_code": 1,
    }
    assert "span_id" not in view["previous_attempt"]
