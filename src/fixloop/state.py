import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

def default_state() -> Dict[str, Any]:
    """Return the canonical FixLoop state dictionary structure."""
    return {
        "run_id": "",
        "arm": "full",
        "issue_id": "",
        "issue": {"title": "", "body": ""},
        "test_node": "",
        "repo": "",
        "base_commit": "",
        "branch": "",
        "attempt": 1,
        "max_attempts": 2,
        "runs_used": 0,
        "timeout_retry_used": False,
        "status": "running",
        "flags": {"gate": True, "lookup": True, "dry_pr": True},
        "baseline": {"exit_code": 1, "tail": "", "span_id": ""},
        "runs": [],
        "edits": [],
        "working": [],
        "hint": None,
        "steps": 0,
        "rejections": 0,
        "gate_rejects": 0,
        "gate": None,
        "pending": {
            "mismatch": False,
            "timeout_retry": False,
            "green": False,
            "lookup_done": False,
        },
        "hypotheses_rejected": [],
        "pr_url": None,
        "cost_usd": 0.0,
        "tokens": 0,
        "last_span_id": None,
        "edit_root": "src/",
    }

def save_state(state: Dict[str, Any], path: str) -> None:
    """Atomically write the state to disk using a temporary file and os.replace."""
    target_path = Path(path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temp file in the same directory to ensure atomic rename
    with tempfile.NamedTemporaryFile("w", dir=target_path.parent, delete=False, encoding="utf-8") as tf:
        json.dump(state, tf, indent=2)
        temp_name = tf.name
        
    os.replace(temp_name, target_path)

def load_state(path: str) -> Dict[str, Any]:
    """Load state from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def project_state(s: Dict[str, Any]) -> Dict[str, Any]:
    """Project the state to only what the stateless model is allowed to see.
    
    In attempt 2, failure outputs and diffs of attempt 1 are stripped,
    leaving only exit code and span_id pointer (if lookup is enabled).
    """
    # Truncate each working item to 4000 characters and total working to 12000 chars
    working_projected = []
    total_len = 0
    for w in s.get("working", []):
        w_str = str(w)
        truncated_item = w_str[:4000]
        if total_len + len(truncated_item) > 12000:
            remaining = max(0, 12000 - total_len)
            if remaining > 0:
                working_projected.append(truncated_item[:remaining])
            break
        working_projected.append(truncated_item)
        total_len += len(truncated_item)

    baseline_tail = s.get("baseline", {}).get("tail", "")
    view = {
        "issue": s.get("issue", {}),
        "test_node": s.get("test_node", ""),
        "attempt": s.get("attempt", 1),
        "max_attempts": s.get("max_attempts", 2),
        "runs_remaining": max(0, s.get("max_attempts", 2) - s.get("runs_used", 0)),
        "hint": s.get("hint"),
        "baseline": {
            "exit_code": s.get("baseline", {}).get("exit_code"),
            "tail": baseline_tail[-3000:],
        },
        "working": working_projected,
        "files_edited": sorted({e["path"] for e in s.get("edits", []) if e.get("ok")}),
    }

    if s.get("attempt", 1) >= 2 and s.get("runs"):
        last_run = s["runs"][-1]
        prev = {"exit_code": last_run.get("exit_code")}
        if s.get("flags", {}).get("lookup", True):
            prev["span_id"] = last_run.get("span_id")
        view["previous_attempt"] = prev

    return view
