import argparse
import sys
from pathlib import Path
from typing import List, Optional

from src.fixloop import driver

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fixloop",
        description="FixLoop: Strictly gated autonomous software bug repair."
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run FixLoop agent on an issue")
    run_parser.add_argument("--repo", default=".", help="Target repository directory path")
    run_parser.add_argument("--issue", default="03", help="Issue ID (e.g. 01, 02, 03)")
    run_parser.add_argument("--model", choices=["fake", "openai", "anthropic"], default="fake", help="Model adapter")
    run_parser.add_argument("--arm", default="full", help="Experiment arm (baseline, nogate, removal, full)")
    run_parser.add_argument("--max-attempts", type=int, default=2, help="Maximum verifying run attempts")
    run_parser.add_argument("--no-gate", action="store_true", help="Disable the gatekeeper (experiment arms only)")
    run_parser.add_argument("--no-trace-lookup", action="store_true", help="Disable trace lookup memory")
    run_parser.add_argument("--pr", action="store_true", help="Open real GitHub pull request via gh")
    run_parser.add_argument("--temperature", type=float, default=0.0, help="Model temperature")
    run_parser.add_argument("--budget-usd", type=float, default=0.50, help="Run budget cap in USD")
    run_parser.add_argument("--max-tokens-per-run", type=int, default=120000, help="Run token budget cap")
    run_parser.add_argument("--state", default=".fixloop/state.json", help="Path to state file")
    run_parser.add_argument("--out", default=None, help="Path to write run summary JSON")
    run_parser.add_argument("--model-mode", default=None, help="Internal test mode for fake model")

    # Command: experiment (stub for Phase 7)
    exp_parser = subparsers.add_parser("experiment", help="Run benchmark experiments")
    exp_parser.add_argument("--model", choices=["fake", "openai", "anthropic"], default="openai")
    exp_parser.add_argument("--issues", nargs="+", default=["01", "02", "03"])
    exp_parser.add_argument("--arms", nargs="+", default=["baseline", "nogate", "removal", "full"])
    exp_parser.add_argument("--trials", type=int, default=5)
    exp_parser.add_argument("--temperature", type=float, default=0.7)
    exp_parser.add_argument("--total-budget-usd", type=float, default=8.0)

    return parser

def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand or args.subcommand == "run":
        repo_val = getattr(args, "repo", ".")
        state_val = getattr(args, "state", ".fixloop/state.json")
        if state_val == ".fixloop/state.json":
            state_val = str(Path(repo_val) / ".fixloop" / "state.json")

        cfg = driver.Config(
            repo=repo_val,
            issue=getattr(args, "issue", "03"),
            model=getattr(args, "model", "fake"),
            arm=getattr(args, "arm", "full"),
            max_attempts=getattr(args, "max_attempts", 2),
            gate=not getattr(args, "no_gate", False),
            lookup=not getattr(args, "no_trace_lookup", False),
            dry_pr=not getattr(args, "pr", False),
            temperature=getattr(args, "temperature", 0.0),
            budget_usd=getattr(args, "budget_usd", 0.50),
            max_tokens_per_run=getattr(args, "max_tokens_per_run", 120000),
            state=state_val,
            out=getattr(args, "out", None),
            model_mode=getattr(args, "model_mode", None),
        )
        return driver.run(cfg)

    elif args.subcommand == "experiment":
        print("Experiment runner will be executed in Phase 7.")
        return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
