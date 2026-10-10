import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union

import neatlogs
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

_NEATLOGS_INITIALIZED = False

def init_tracing(workflow_name: str = "fixloop-full") -> bool:
    """Initialize Neatlogs SDK if API key is present.
    
    Gracefully falls back if NEATLOGS_API_KEY is missing so that local
    spans JSONL logging continues without interruption.
    
    Returns:
        True if Neatlogs SDK was initialized, False otherwise.
    """
    global _NEATLOGS_INITIALIZED
    api_key = os.environ.get("NEATLOGS_API_KEY")
    if not api_key:
        _NEATLOGS_INITIALIZED = False
        return False

    try:
        neatlogs.init(
            api_key=api_key,
            workflow_name=workflow_name,
            endpoint="https://ingest.neatlogs.com",
        )
        _NEATLOGS_INITIALIZED = True
        return True
    except Exception as e:
        _NEATLOGS_INITIALIZED = False
        return False

def flush_tracing() -> None:
    """Flush pending spans to Neatlogs if initialized."""
    global _NEATLOGS_INITIALIZED
    if _NEATLOGS_INITIALIZED:
        try:
            neatlogs.flush()
        except Exception:
            pass

def shutdown_tracing() -> None:
    """Flush and shut down Neatlogs SDK before process exit."""
    global _NEATLOGS_INITIALIZED
    if _NEATLOGS_INITIALIZED:
        try:
            neatlogs.flush()
            neatlogs.shutdown()
        except Exception:
            pass
        _NEATLOGS_INITIALIZED = False

def redact_args(args: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Redact sensitive keys from tool argument dictionary."""
    if not args or not isinstance(args, dict):
        return {}
    sensitive_keys = {"token", "key", "secret", "password", "auth", "credential"}
    redacted = {}
    for k, v in args.items():
        if any(s in k.lower() for s in sensitive_keys):
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v
    return redacted

def log_span(
    spans_path: Union[str, Path],
    *,
    span_id: str,
    run_id: str,
    attempt: int,
    name: str,
    tool: str,
    parent_span_id: Optional[str] = None,
    args_redacted: Optional[Dict[str, Any]] = None,
    exit_code: Optional[int] = None,
    tail: str = "",
    diff: str = "",
    cost_usd: float = 0.0,
    tokens: int = 0,
    recovery_of: Optional[str] = None,
    model_id: str = "fake",
) -> Dict[str, Any]:
    """Record a span record to local append-only spans.jsonl (Section 3.7).
    
    Guaranteed to execute even when NEATLOGS_API_KEY is unset.
    Tail is constrained to at most 80 lines.
    """
    path = Path(spans_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Constrain tail to max 80 lines
    tail_lines = (tail or "").splitlines()
    truncated_tail = "\n".join(tail_lines[-80:]) if tail_lines else ""

    record = {
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "run_id": run_id,
        "attempt": attempt,
        "name": name,
        "tool": tool,
        "args_redacted": redact_args(args_redacted),
        "exit_code": exit_code,
        "tail": truncated_tail,
        "diff": diff or "",
        "cost_usd": round(cost_usd, 6),
        "tokens": int(tokens),
        "recovery_of": recovery_of,
        "model_id": model_id,
    }

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return record

# Re-export span decorator for convenient wrapping
span = neatlogs.span
trace = neatlogs.trace
