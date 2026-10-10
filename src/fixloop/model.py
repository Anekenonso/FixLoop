import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class Action:
    tool: str
    args: Dict[str, Any]
    usage: Dict[str, Any] = field(default_factory=lambda: {"tokens": 0, "cost_usd": 0.0})

class ModelError(Exception):
    """Raised on model transport or parsing failure."""
    pass

def parse_action_response(text: str, usage: Optional[Dict[str, Any]] = None) -> Action:
    """Parse JSON action response from a model, stripping code fences if present."""
    usage = usage or {"tokens": 0, "cost_usd": 0.0}
    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    try:
        parsed = json.loads(clean)
    except Exception as e:
        raise ModelError(f"invalid_json: {e}")

    if not isinstance(parsed, dict) or "tool" not in parsed or "args" not in parsed:
        raise ModelError("missing_tool_or_args")

    return Action(tool=str(parsed["tool"]), args=dict(parsed["args"]), usage=usage)

class FakeModelAdapter:
    """Deterministic simulated model adapter for CI and acceptance testing.
    
    Behaviour is strictly a function of the view, without hidden counters.
    """
    def __init__(self, mode: Optional[str] = None):
        self.mode = mode

    def next_action(self, view: Dict[str, Any]) -> Action:
        # Support injected test modes
        if self.mode == "invalid_json":
            raise ModelError("non_json_model_output")
        if self.mode == "unknown_tool":
            return Action(tool="magic_tool", args={"foo": "bar"}, usage={"tokens": 5})
        if self.mode == "junk_loop":
            return Action(tool="open_pr", args={"title": "Spam", "body": "Spam"}, usage={"tokens": 5})

        test_node = view.get("test_node", "")
        working = view.get("working", [])
        attempt = view.get("attempt", 1)
        prev_attempt = view.get("previous_attempt", {})

        def in_working(tool_name: str) -> bool:
            for item in working:
                item_str = str(item)
                if f"'tool': '{tool_name}'" in item_str or f'"tool": "{tool_name}"' in item_str:
                    return True
            return False

        # --- ISSUE 01: Paginate ---
        if "test_paginate" in test_node:
            if not in_working("read_file"):
                return Action("read_file", {"path": "src/paginate.py", "start": 1, "end": 10}, usage={"tokens": 10})
            if not in_working("edit_file"):
                return Action("edit_file", {
                    "path": "src/paginate.py",
                    "old": "    end = start + size + 1  # BUG: off by one",
                    "new": "    end = start + size"
                }, usage={"tokens": 15})
            if not in_working("run_tests"):
                return Action("run_tests", {"node_id": test_node}, usage={"tokens": 10})
            return Action("open_pr", {
                "title": "Fix pagination page size off by one",
                "body": "Corrected end index to start + size."
            }, usage={"tokens": 20})

        # --- ISSUE 02: Merge ---
        if "test_merge" in test_node:
            if not in_working("read_file"):
                return Action("read_file", {"path": "src/merge.py", "start": 1, "end": 10}, usage={"tokens": 10})
            if not in_working("edit_file"):
                return Action("edit_file", {
                    "path": "src/merge.py",
                    "old": "    return {**right, **left}  # BUG: left overwrites right; right must win",
                    "new": "    return {**left, **right}"
                }, usage={"tokens": 15})
            if not in_working("run_tests"):
                return Action("run_tests", {"node_id": test_node}, usage={"tokens": 10})
            return Action("open_pr", {
                "title": "Fix dict merge precedence",
                "body": "Right dictionary now correctly overrides left."
            }, usage={"tokens": 20})

        # --- ISSUE 03: Cache ---
        if "test_cache" in test_node:
            if attempt == 1:
                # Attempt 1: naive comment-only edit -> still red
                if not in_working("read_file"):
                    return Action("read_file", {"path": "src/cache.py", "start": 1, "end": 20}, usage={"tokens": 10})
                if not in_working("edit_file"):
                    return Action("edit_file", {
                        "path": "src/cache.py",
                        "old": "        return _last   # BUG: swallows the error silently",
                        "new": "        # swallowed error\n        return _last"
                    }, usage={"tokens": 15})
                if not in_working("run_tests"):
                    return Action("run_tests", {"node_id": test_node}, usage={"tokens": 10})
                # If run_tests somehow returned without attempt bump:
                return Action("open_pr", {
                    "title": "Attempted logging in cache",
                    "body": "Added comment around swallowed exception."
                }, usage={"tokens": 20})

            # Attempt 2:
            span_id = prev_attempt.get("span_id")
            if span_id:
                # Full arm with lookup enabled
                if not in_working("trace_lookup"):
                    return Action("trace_lookup", {"span_id": span_id}, usage={"tokens": 10})
                if not in_working("edit_file"):
                    return Action("edit_file", {
                        "path": "src/cache.py",
                        "old": "        # swallowed error\n        return _last",
                        "new": "        raise"
                    }, usage={"tokens": 15})
                if not in_working("run_tests"):
                    return Action("run_tests", {"node_id": test_node}, usage={"tokens": 10})
                return Action("open_pr", {
                    "title": "Fix swallowed exception in cache.py",
                    "body": "Re-raise exception when compute fails so callers can diagnose errors."
                }, usage={"tokens": 20})
            else:
                # Removal arm (--no-trace-lookup): pointer absent, blind to attempt 1
                # Repeats original comment edit, which fails with mismatch and stops
                return Action("edit_file", {
                    "path": "src/cache.py",
                    "old": "        return _last   # BUG: swallows the error silently",
                    "new": "        # swallowed error\n        return _last"
                }, usage={"tokens": 15})

        # Fallback for unrecognized issue
        if not in_working("run_tests"):
            return Action("run_tests", {"node_id": test_node}, usage={"tokens": 5})
        return Action("open_pr", {"title": "Generic fix", "body": "Generic fix body"}, usage={"tokens": 5})

def get_adapter(model_name: str, **kwargs) -> Any:
    """Factory to get the appropriate model adapter."""
    if model_name == "fake":
        mode = kwargs.get("mode")
        return FakeModelAdapter(mode=mode)
    elif model_name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        model_id = os.environ.get("FIXLOOP_MODEL")
        if not api_key or not model_id:
            raise ValueError("OPENAI_API_KEY and FIXLOOP_MODEL must be set for --model openai")
        # OpenAI adapter will be fully wired in Phase 6
        raise NotImplementedError("OpenAI adapter will be wired in Phase 6")
    elif model_name == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        model_id = os.environ.get("FIXLOOP_MODEL")
        if not api_key or not model_id:
            raise ValueError("ANTHROPIC_API_KEY and FIXLOOP_MODEL must be set for --model anthropic")
        raise NotImplementedError("Anthropic adapter will be wired in Phase 6")
    else:
        raise ValueError(f"Unknown model provider: {model_name}")
