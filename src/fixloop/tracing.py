import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union

import neatlogs
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

_NEATLOGS_INITIALIZED = False
_CURRENT_TRACER = None
_CURRENT_ROOT_SPAN = None
_CURRENT_TRACE_ID = None

def init_tracing(workflow_name: str = "fixloop-full") -> bool:
    """Initialize Neatlogs SDK if API key is present.
    
    Gracefully falls back if NEATLOGS_API_KEY is missing so that local
    spans JSONL logging continues without interruption.
    
    Returns:
        True if Neatlogs SDK was initialized, False otherwise.
    """
    global _NEATLOGS_INITIALIZED, _CURRENT_TRACER, _CURRENT_ROOT_SPAN, _CURRENT_TRACE_ID
    api_key = os.environ.get("NEATLOGS_API_KEY")
    if not api_key or api_key.strip() in {"", "your_neatlogs_api_key_here"}:
        _NEATLOGS_INITIALIZED = False
        _CURRENT_TRACER = None
        _CURRENT_ROOT_SPAN = None
        _CURRENT_TRACE_ID = None
        return False

    try:
        neatlogs.init(
            api_key=api_key,
            workflow_name=workflow_name,
            endpoint="https://ingest.neatlogs.com",
        )
        try:
            from neatlogs._wrap_utils import get_internal_tracer
            _CURRENT_TRACER = get_internal_tracer("fixloop")
            _CURRENT_ROOT_SPAN = _CURRENT_TRACER.start_span(workflow_name)
            ctx = _CURRENT_ROOT_SPAN.get_span_context()
            if ctx.is_valid:
                _CURRENT_TRACE_ID = format(ctx.trace_id, "032x")
        except Exception:
            pass
        _NEATLOGS_INITIALIZED = True
        return True
    except Exception as e:
        _NEATLOGS_INITIALIZED = False
        _CURRENT_TRACER = None
        _CURRENT_ROOT_SPAN = None
        _CURRENT_TRACE_ID = None
        return False

def get_current_trace_id() -> Optional[str]:
    """Return the active 32-character hex Neatlogs trace ID if initialized."""
    global _CURRENT_TRACE_ID
    return _CURRENT_TRACE_ID

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
    global _NEATLOGS_INITIALIZED, _CURRENT_ROOT_SPAN, _CURRENT_TRACER, _CURRENT_TRACE_ID
    if _NEATLOGS_INITIALIZED:
        try:
            if _CURRENT_ROOT_SPAN:
                _CURRENT_ROOT_SPAN.end()
                _CURRENT_ROOT_SPAN = None
            neatlogs.flush()
            neatlogs.shutdown()
        except Exception:
            pass
        _NEATLOGS_INITIALIZED = False
        _CURRENT_TRACER = None
        _CURRENT_TRACE_ID = None

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

    # If Neatlogs SDK is initialized, also emit a live OpenTelemetry span
    global _NEATLOGS_INITIALIZED, _CURRENT_TRACER, _CURRENT_ROOT_SPAN
    if _NEATLOGS_INITIALIZED and _CURRENT_TRACER:
        try:
            from opentelemetry import trace as otel_trace
            parent_ctx = otel_trace.set_span_in_context(_CURRENT_ROOT_SPAN) if _CURRENT_ROOT_SPAN else None
            child_span = _CURRENT_TRACER.start_span(f"{tool}:{name}", context=parent_ctx)
            child_span.set_attribute("tool.name", tool)
            child_span.set_attribute("fixloop.span_id", span_id)
            child_span.set_attribute("fixloop.run_id", run_id)
            child_span.set_attribute("fixloop.attempt", attempt)
            if exit_code is not None:
                child_span.set_attribute("fixloop.exit_code", exit_code)
            child_span.set_attribute("fixloop.tokens", tokens)
            child_span.set_attribute("fixloop.cost_usd", cost_usd)
            if recovery_of:
                child_span.set_attribute("fixloop.recovery_of", recovery_of)
            if model_id:
                child_span.set_attribute("fixloop.model_id", model_id)
            if diff:
                child_span.set_attribute("fixloop.diff_lines", len(diff.splitlines()))
            child_span.end()
        except Exception:
            pass

    return record

# Re-export span decorator for convenient wrapping
span = neatlogs.span
trace = neatlogs.trace
