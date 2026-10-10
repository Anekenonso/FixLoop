import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Set

from src.fixloop import gate, model, state, tools, tracing

MAX_STEPS = 24
MAX_REJECTIONS = 6
TOOLS = {"read_issue", "read_file", "edit_file", "run_tests", "trace_lookup", "open_pr"}

@dataclass
class Config:
    repo: str = "."
    issue: str = "03"
    model: str = "fake"
    arm: str = "full"
    max_attempts: int = 2
    gate: bool = True
    lookup: bool = True
    dry_pr: bool = True
    temperature: float = 0.0
    budget_usd: float = 0.50
    max_tokens_per_run: int = 120000
    state: str = ".fixloop/state.json"
    out: Optional[str] = None
    model_mode: Optional[str] = None

def is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is alive."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        success = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(success and exit_code.value == STILL_ACTIVE)
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

def acquire_lock(state_path_str: str) -> Optional[Path]:
    """Acquire process lock for state file.
    
    Returns lock file Path on success.
    Returns None if a live process holds the lock (exit 2).
    Replaces stale locks left by dead processes.
    """
    state_path = Path(state_path_str).resolve()
    lock_path = state_path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.is_file():
        try:
            content = lock_path.read_text(encoding="utf-8").strip()
            data = json.loads(content)
            lock_pid = data.get("pid")
            if lock_pid and is_pid_alive(lock_pid) and lock_pid != os.getpid():
                # Another live process holds the lock
                return None
        except Exception:
            # Corrupted lock file -> replace
            pass

    # Write current pid to lock
    lock_data = {"pid": os.getpid(), "ts": time.time()}
    lock_path.write_text(json.dumps(lock_data), encoding="utf-8")
    return lock_path

def release_lock(lock_path: Optional[Path]) -> None:
    """Release acquired lock."""
    if lock_path and lock_path.is_file():
        try:
            lock_path.unlink()
        except OSError:
            pass

def check_dirty_repo(repo_path: Path) -> bool:
    """Check if git repository has untracked or unstaged changes."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True
        )
        lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
        dirty_lines = [
            l for l in lines
            if not any(ignored in l for ignored in [".fixloop", "evidence", ".pytest_cache", "__pycache__"])
        ]
        return bool(dirty_lines)
    except subprocess.CalledProcessError:
        return False

def append_span(spans_path: Path, span_record: Dict[str, Any]) -> None:
    """Append a span record to local spans.jsonl."""
    spans_path.parent.mkdir(parents=True, exist_ok=True)
    with open(spans_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(span_record) + "\n")

def allowed_tools(s: Dict[str, Any]) -> Set[str]:
    """Determine currently allowed tools based on state invariants."""
    p = s.get("pending", {})
    if p.get("mismatch"):
        return {"read_file"}
    if p.get("timeout_retry"):
        return {"run_tests"}
    if p.get("green"):
        return {"open_pr"}
    if s.get("flags", {}).get("lookup") and s.get("attempt", 1) >= 2 and not p.get("lookup_done"):
        return {"trace_lookup"}
    return TOOLS

def over_budget(s: Dict[str, Any], cfg: Config) -> bool:
    """Check if token or dollar budget is exceeded."""
    if s.get("tokens", 0) > cfg.max_tokens_per_run:
        return True
    if cfg.budget_usd > 0 and s.get("cost_usd", 0.0) > cfg.budget_usd:
        return True
    return False

def write_stop_file(s: Dict[str, Any], reason: str) -> None:
    """Write evidence stop file."""
    repo_path = Path(s["repo"]).resolve()
    evidence_dir = repo_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stop_file = evidence_dir / f"stop-{s['issue_id']}-{s['run_id']}.md"
    
    last_diff = ""
    try:
        base_commit = s.get("base_commit", "HEAD")
        dres = subprocess.run(
            ["git", "diff", base_commit],
            cwd=str(repo_path),
            capture_output=True,
            text=True
        )
        last_diff = dres.stdout
    except Exception:
        pass

    content = f"""# FixLoop Stop Record

- **Run ID:** {s.get('run_id')}
- **Issue:** {s.get('issue_id')}
- **Reason:** {reason}
- **Status:** stopped
- **Attempts:** {s.get('attempt')}/{s.get('max_attempts')}
- **Tokens:** {s.get('tokens')}
- **Cost USD:** {s.get('cost_usd')}
- **Last Span ID:** {s.get('last_span_id')}
- **Hypotheses Rejected:** {json.dumps(s.get('hypotheses_rejected', []))}

## Last Change Diff
```diff
{last_diff}
```
"""
    stop_file.write_text(content, encoding="utf-8")

def run_oracle(s: Dict[str, Any]) -> Dict[str, Any]:
    """Independent oracle verification of the final tree."""
    target_node = s.get("test_node", "")
    if not target_node:
        return {"resolved": False, "node_exit": 1, "file_exit": 1}

    node_res = tools.run_tests_raw(s, node_id=target_node)
    test_file = target_node.split("::")[0] if "::" in target_node else target_node
    file_res = tools.run_tests_raw(s, node_id=test_file)

    resolved = (node_res.get("exit_code") == 0 and file_res.get("exit_code") == 0)
    return {
        "resolved": resolved,
        "node_exit": node_res.get("exit_code", 1),
        "file_exit": file_res.get("exit_code", 1),
    }

def run(cfg: Config) -> int:
    """Authoritative driver loop execution."""
    repo_path = Path(cfg.repo).resolve()
    state_path = Path(cfg.state).resolve()

    # 1. Acquire lock
    lock = acquire_lock(str(state_path))
    if lock is None:
        print(f"Error: Lock held by another live process for state file {state_path}", file=sys.stderr)
        return 2

    # Initialize observability tracing (Neatlogs)
    tracing.init_tracing(workflow_name=f"fixloop-{cfg.arm}")

    try:
        # Check Break Matrix Row 20: --model fake with headline --out
        if cfg.model == "fake" and cfg.out:
            out_norm = cfg.out.replace("\\", "/")
            headline_targets = {
                "evidence/baseline.json",
                "evidence/intervention.json",
                "evidence/removal.json",
                "evidence/recovery.json",
                "evidence/nogate.json"
            }
            if any(out_norm.endswith(t) for t in headline_targets):
                print(f"Error: --model fake cannot produce headline evidence file {cfg.out}", file=sys.stderr)
                return 2

        # 2. Verify git repo & clean tree (Break Matrix Row 18)
        if check_dirty_repo(repo_path):
            print("Error: Repository has uncommitted changes at start (dirty repo)", file=sys.stderr)
            return 2

        # 3. Read issue (Break Matrix Row 1)
        issue_res = tools.read_issue(str(repo_path), cfg.issue)
        run_id = f"{cfg.issue}-{int(time.time())}-{uuid.uuid4().hex[:6]}"

        if not issue_res.get("ok"):
            # Break Matrix Row 1: issue missing or malformed -> stop, no edit, exit 1
            s = state.default_state()
            s.update({
                "run_id": run_id,
                "arm": cfg.arm,
                "issue_id": cfg.issue,
                "repo": str(repo_path),
                "status": "stopped",
            })
            write_stop_file(s, issue_res.get("error", "invalid_issue"))
            state.save_state(s, str(state_path))
            print(f"State saved to {state_path}")
            return 1

        # 4. Initialize git branch & base_commit
        base_commit = "HEAD"
        try:
            head_rev = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=True
            )
            base_commit = head_rev.stdout.strip()
        except Exception:
            pass

        branch_name = f"fixloop/{cfg.issue}-{int(time.time())}"
        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=True
            )
        except Exception:
            pass

        # 5. Initialize State
        s = state.default_state()
        s.update({
            "run_id": run_id,
            "arm": cfg.arm,
            "issue_id": cfg.issue,
            "issue": {"title": issue_res.get("title", ""), "body": issue_res.get("body", "")},
            "test_node": issue_res.get("test_node", ""),
            "repo": str(repo_path),
            "base_commit": base_commit,
            "branch": branch_name,
            "attempt": 1,
            "max_attempts": cfg.max_attempts,
            "status": "running",
            "flags": {
                "gate": cfg.gate,
                "lookup": cfg.lookup,
                "dry_pr": cfg.dry_pr,
            },
        })
        state.save_state(s, str(state_path))

        spans_path = repo_path / "evidence" / "spans.jsonl"

        # 6. Baseline run (Attempt 0)
        base_span_id = f"span_base_{uuid.uuid4().hex[:8]}"
        base = tools.run_tests_raw(s)
        base["span_id"] = base_span_id
        s["baseline"] = base
        s["last_span_id"] = base_span_id

        tracing.log_span(
            spans_path,
            span_id=base_span_id,
            parent_span_id=None,
            run_id=run_id,
            attempt=0,
            name="baseline_run",
            tool="run_tests_raw",
            args_redacted={"node_id": s.get("test_node", "")},
            exit_code=base.get("exit_code"),
            tail=base.get("tail", ""),
            diff="",
            cost_usd=0.0,
            tokens=0,
            recovery_of=None,
            model_id=cfg.model,
        )
        state.save_state(s, str(state_path))

        if base.get("exit_code") == 0:
            s["status"] = "stopped"
            write_stop_file(s, "baseline_not_red")
            state.save_state(s, str(state_path))
            return 1

        if base.get("exit_code") == 124:
            s["status"] = "stopped"
            write_stop_file(s, "baseline_timeout")
            state.save_state(s, str(state_path))
            return 1

        # 7. Model Adapter initialization
        try:
            adapter = model.get_adapter(cfg.model, mode=cfg.model_mode)
        except Exception as e:
            print(f"Error initializing model adapter: {e}", file=sys.stderr)
            return 2

        # 8. Main Driver Loop
        while s["status"] == "running":
            if over_budget(s, cfg):
                s["status"] = "stopped"
                write_stop_file(s, "budget_exceeded")
                break

            s["steps"] += 1
            if s["steps"] > MAX_STEPS:
                s["status"] = "stopped"
                write_stop_file(s, "step_budget")
                break

            if s["rejections"] >= MAX_REJECTIONS:
                s["status"] = "stopped"
                write_stop_file(s, "too_many_rejections")
                break

            view = state.project_state(s)
            try:
                action = adapter.next_action(view)
            except model.ModelError:
                s["rejections"] += 1
                state.save_state(s, str(state_path))
                continue
            except Exception as e:
                s["status"] = "stopped"
                write_stop_file(s, f"model_error: {e}")
                break

            if action is None or action.tool not in TOOLS:
                s["rejections"] += 1
                state.save_state(s, str(state_path))
                continue

            allowed = allowed_tools(s)
            if action.tool not in allowed:
                s["rejections"] += 1
                s["hint"] = f"tool_not_allowed: use one of {sorted(allowed)}"
                state.save_state(s, str(state_path))
                continue

            # Dispatch action
            span_id = f"span_{action.tool}_{uuid.uuid4().hex[:8]}"
            s["last_span_id"] = span_id
            s["tokens"] += action.usage.get("tokens", 0)
            s["cost_usd"] += action.usage.get("cost_usd", 0.0)

            result = {}
            if action.tool == "read_issue":
                result = tools.read_issue(s["repo"], action.args.get("issue_id", s["issue_id"]))
            elif action.tool == "read_file":
                result = tools.read_file(
                    s["repo"],
                    action.args.get("path", ""),
                    start=action.args.get("start", 1),
                    end=action.args.get("end", 200)
                )
                if result.get("ok"):
                    s["pending"]["mismatch"] = False
            elif action.tool == "edit_file":
                result = tools.edit_file(
                    s["repo"],
                    action.args.get("path", ""),
                    action.args.get("old", ""),
                    action.args.get("new", ""),
                    s
                )
                s["edits"].append({
                    "attempt": s["attempt"],
                    "path": action.args.get("path", ""),
                    "ok": result.get("ok", False),
                    "span_id": span_id
                })
                if not result.get("ok"):
                    s["pending"]["mismatch"] = True
                    s["hint"] = "mismatch: read_file before the next edit"
            elif action.tool == "trace_lookup":
                result = tools.trace_lookup(
                    action.args.get("span_id", ""),
                    str(spans_path),
                    s
                )
                if result.get("ok"):
                    s["pending"]["lookup_done"] = True
            elif action.tool == "run_tests":
                result = tools.run_tests(action.args.get("node_id", ""), s)
            elif action.tool == "open_pr":
                result = tools.open_pr(
                    action.args.get("title", ""),
                    action.args.get("body", ""),
                    s
                )

            # Record in working memory
            s["working"].append({"tool": action.tool, "args": action.args, "result": result})

            # Record span
            diff_text = ""
            try:
                diff_res = subprocess.run(
                    ["git", "diff", s.get("base_commit", "HEAD")],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True
                )
                diff_text = diff_res.stdout
            except Exception:
                pass

            recovery_of = None
            if action.tool == "trace_lookup":
                recovery_of = action.args.get("span_id")

            parent_span_id = base_span_id if s["attempt"] == 1 else (
                s["runs"][-1]["span_id"] if s["runs"] else base_span_id
            )

            tracing.log_span(
                spans_path,
                span_id=span_id,
                parent_span_id=parent_span_id,
                run_id=run_id,
                attempt=s["attempt"],
                name=action.tool,
                tool=action.tool,
                args_redacted=action.args,
                exit_code=result.get("exit_code"),
                tail=result.get("tail", "") if action.tool in {"run_tests", "run_tests_raw"} else "",
                diff=diff_text,
                cost_usd=action.usage.get("cost_usd", 0.0),
                tokens=action.usage.get("tokens", 0),
                recovery_of=recovery_of,
                model_id=cfg.model,
            )

            # After-run hooks
            if action.tool == "run_tests":
                exit_code = result.get("exit_code", 1)
                s["runs"].append({
                    "attempt": s["attempt"],
                    "command": f"pytest {s['test_node']}",
                    "exit_code": exit_code,
                    "tail": result.get("tail", ""),
                    "span_id": span_id,
                    "duration_s": result.get("duration_s", 0.0),
                })

                if exit_code == 124:
                    if not s["timeout_retry_used"]:
                        s["pending"]["timeout_retry"] = True
                        s["timeout_retry_used"] = True
                    else:
                        s["status"] = "stopped"
                        write_stop_file(s, "timeout_twice")
                        break
                else:
                    s["runs_used"] += 1
                    s["pending"]["timeout_retry"] = False
                    if exit_code == 0:
                        s["pending"]["green"] = True
                    else:
                        # Red run
                        s["attempt"] += 1
                        s["working"] = []
                        s["pending"]["lookup_done"] = False
                        tracing.flush_tracing()
                        if s["attempt"] > s["max_attempts"]:
                            if s["flags"]["gate"]:
                                s["status"] = "stopped"
                                write_stop_file(s, "attempts_exhausted")
                                break
                            else:
                                # Naive ungated arm auto-proposes
                                tools.open_pr("Ungated fix proposal", "Auto proposed without gate", s)
                                s["status"] = "proposed_ungated"
                                break

            if action.tool == "open_pr":
                if not result.get("allowed"):
                    s["gate_rejects"] += 1
                    s["hint"] = result.get("reason", "gate_rejected")
                    if s["gate_rejects"] >= 2:
                        s["status"] = "stopped"
                        write_stop_file(s, "gate_reject_limit")
                        break
                else:
                    if result.get("pr") == "dry_run":
                        s["status"] = "passed"
                    else:
                        s["status"] = "pr_opened"
                        s["pr_url"] = result.get("url")
                    break

            state.save_state(s, str(state_path))

        # 9. Oracle Evaluation
        oracle = run_oracle(s)
        s["oracle"] = oracle
        s["false_pr"] = (s["status"] in {"passed", "pr_opened", "proposed_ungated"} and not oracle["resolved"])
        state.save_state(s, str(state_path))

        # 10. Write output file if requested
        if cfg.out:
            out_path = Path(cfg.out).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(s, indent=2), encoding="utf-8")

        # 11. Final output and exit code
        print(f"State saved to {state_path}")
        print(f"Last span ID: {s.get('last_span_id')}")

        if s["status"] in {"passed", "pr_opened"}:
            return 0
        elif s["status"] == "proposed_ungated":
            return 3
        else:
            return 1

    finally:
        tracing.shutdown_tracing()
        release_lock(lock)
