"""Sample instrumented entry point for FixLoop to verify Neatlogs telemetry.

Run this script to generate a live trace in the Neatlogs dashboard:
    python -m src.fixloop.run_sample_trace
"""
import time
from src.fixloop.tracing import init_tracing, shutdown_tracing, span

# 1. Initialize Neatlogs once at entry point startup
init_tracing(workflow_name="fixloop-verification")

@span(kind="TOOL", tool_name="check_environment")
def check_environment() -> dict:
    """Tool span representing environment inspection."""
    return {"status": "ok", "tools": ["git", "pytest", "gh", "neatlogs"]}

@span(kind="AGENT", name="fixloop_diagnostic_agent")
def diagnostic_agent() -> str:
    """Agent span representing diagnostic reasoning."""
    env_info = check_environment()
    return f"Diagnostic completed successfully: {env_info['status']}"

@span(kind="WORKFLOW")
def main() -> None:
    """Workflow root span representing the outer process entry point."""
    print("Executing FixLoop Neatlogs verification workflow...")
    result = diagnostic_agent()
    print(f"Result: {result}")

if __name__ == "__main__":
    try:
        main()
    finally:
        # One-shot CLI process flush & shutdown
        shutdown_tracing()
        print("Tracing flushed and shut down successfully.")
