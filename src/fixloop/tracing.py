import os
from typing import Optional
import neatlogs
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def init_tracing(workflow_name: str = "fixloop-runner") -> None:
    """Initialize Neatlogs SDK with regional ingest endpoint.
    
    Args:
        workflow_name: Name describing the specific task or pipeline
                       (e.g., fixloop-full, fixloop-baseline, etc.)
    """
    api_key = os.environ.get("NEATLOGS_API_KEY")
    if not api_key:
        raise ValueError("NEATLOGS_API_KEY environment variable is missing in environment or .env")
    
    neatlogs.init(
        api_key=api_key,
        workflow_name=workflow_name,
        endpoint="https://ingest.neatlogs.com",
    )

def flush_tracing() -> None:
    """Flush pending spans to Neatlogs."""
    neatlogs.flush()

def shutdown_tracing() -> None:
    """Flush and shut down Neatlogs SDK before process exit."""
    neatlogs.flush()
    neatlogs.shutdown()

# Re-export span decorator for convenient tracing
span = neatlogs.span
trace = neatlogs.trace
