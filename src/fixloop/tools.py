import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable

from src.fixloop import gate

TEST_NODE_REGEX = re.compile(r"^[A-Za-z0-9_./-]+\.py::[A-Za-z0-9_]+$")
ISSUE_NODE_LINE = re.compile(r"^TEST_NODE:\s*([A-Za-z0-9_./-]+\.py::[A-Za-z0-9_]+)\s*$", re.MULTILINE)
SKIP_PATTERN = re.compile(r"\b(pytest\.skip|importorskip|xfail|skipif|mark\.skip)\b")

def read_issue(
    repo: str,
    issue_id: str,
    issue_file: Optional[str] = None,
    test_override: Optional[str] = None
) -> Dict[str, Any]:
    """Read and parse an issue file.
    
    Expects `# title`, body, and `TEST_NODE: tests/...::...`.
    If issue_file is provided, reads that path directly.
    If test_override is provided, uses it as the target test node.
    """
    repo_path = Path(repo).resolve()
    
    if issue_file:
        p = Path(issue_file)
        target_file = p if p.is_file() else (repo_path / issue_file)
        if not target_file.is_file():
            return {"ok": False, "error": "missing_issue"}
    else:
        # Support issue_id as '01', '01-paginate', or full file path
        candidates = [
            repo_path / f"issues/{issue_id}.md",
            repo_path / f"issues/{issue_id}",
            repo_path / issue_id,
            repo_path / f"sandbox_template/issues/{issue_id}.md",
        ]
        
        # Also search by prefix in issues/
        issues_dir = repo_path / "issues"
        if not any(c.is_file() for c in candidates) and issues_dir.is_dir():
            for f in issues_dir.glob(f"{issue_id}*.md"):
                candidates.insert(0, f)
                break

        target_file = next((c for c in candidates if c.is_file()), None)
        if not target_file:
            return {"ok": False, "error": "missing_issue"}

    try:
        content = target_file.read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"read_error: {e}"}

    lines = content.splitlines()
    title = ""
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    if test_override:
        if not TEST_NODE_REGEX.match(test_override.strip()):
            return {"ok": False, "error": "invalid_node_id"}
        test_node = test_override.strip()
    else:
        node_match = ISSUE_NODE_LINE.search(content)
        if not node_match or not title:
            return {"ok": False, "error": "malformed_issue"}
        test_node = node_match.group(1).strip()

    
    # Body is everything between title and TEST_NODE
    body_lines = []
    found_title = False
    for line in lines:
        if line.startswith("# ") and not found_title:
            found_title = True
            continue
        if line.startswith("TEST_NODE:"):
            break
        if found_title:
            body_lines.append(line)
            
    body = "\n".join(body_lines).strip()

    return {
        "ok": True,
        "title": title,
        "body": body,
        "test_node": test_node,
    }

def read_file(repo: str, path: str, start: int = 1, end: int = 200) -> Dict[str, Any]:
    """Read numbered lines from a file with strict path sandboxing.
    
    Blocks path traversal (../), absolute paths, and external symlinks.
    1-indexed, inclusive, maximum 200 lines.
    """
    repo_path = Path(repo).resolve()
    
    # Disallow absolute paths
    raw_path = Path(path)
    if raw_path.is_absolute():
        return {"ok": False, "error": "path_outside_repo"}
        
    try:
        target = (repo_path / raw_path).resolve()
        target.relative_to(repo_path)
    except (ValueError, RuntimeError):
        return {"ok": False, "error": "path_outside_repo"}

    if not target.is_file():
        return {"ok": False, "error": "file_not_found"}

    try:
        content = target.read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"read_error: {e}"}

    all_lines = content.splitlines()
    total_lines = len(all_lines)
    
    # Clamp bounds (1-indexed inclusive)
    start_idx = max(1, start)
    end_idx = min(total_lines, max(start_idx, end))
    
    if end_idx - start_idx + 1 > 200:
        end_idx = start_idx + 199

    lines_dict = {
        lineno: all_lines[lineno - 1]
        for lineno in range(start_idx, end_idx + 1)
    }

    return {"ok": True, "lines": lines_dict}

def edit_file(
    repo: str,
    path: str,
    old: str,
    new: str,
    state: Dict[str, Any]
) -> Dict[str, Any]:
    """Edit a file under edit_root using exact substring replacement.
    
    After a successful edit, creates a git commit on the branch.
    """
    repo_path = Path(repo).resolve()
    raw_path = Path(path)
    
    if raw_path.is_absolute():
        return {"ok": False, "error": "protected_path"}

    edit_root = state.get("edit_root", "src/").replace("\\", "/").strip("/")
    allowed_root = (repo_path / edit_root).resolve() if edit_root else repo_path

    try:
        target = (repo_path / raw_path).resolve()
        target.relative_to(allowed_root)
    except (ValueError, RuntimeError):
        return {"ok": False, "error": "protected_path"}

    if not target.is_file():
        return {"ok": False, "error": "file_not_found"}

    # Disallow test skipping / xfail
    if SKIP_PATTERN.search(new):
        return {"ok": False, "error": "test_skipped"}

    content = target.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        return {"ok": False, "error": "mismatch"}

    new_content = content.replace(old, new, 1)
    target.write_text(new_content, encoding="utf-8")

    # Commit after edit
    attempt = state.get("attempt", 1)
    test_node = state.get("test_node", "")
    commit_msg = f"fixloop attempt {attempt}: {test_node}"
    
    try:
        subprocess.run(["git", "add", norm_target], cwd=str(repo_path), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=str(repo_path), check=True, capture_output=True)
    except Exception:
        # Commit failure (e.g. no changes, non-git dir, or git error)
        pass

    return {"ok": True}

def run_tests_raw(
    state: Dict[str, Any],
    node_id: Optional[str] = None,
    timeout: int = 60
) -> Dict[str, Any]:
    """Execute pytest in a sanitized subprocess without injecting extra flags.
    
    Guarantees that environment secrets are never passed into pytest.
    """
    target_node = node_id or state.get("test_node", "")
    repo = state.get("repo", ".")
    repo_path = Path(repo).resolve()

    temp_home = tempfile.gettempdir()
    sanitized_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": temp_home,
        "USERPROFILE": temp_home,
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
    }
    if "SYSTEMROOT" in os.environ:
        sanitized_env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    if "SystemDrive" in os.environ:
        sanitized_env["SystemDrive"] = os.environ["SystemDrive"]

    cmd = [sys.executable, "-m", "pytest", target_node, "-q", "--tb=line"]

    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_path),
            env=sanitized_env,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        duration = round(time.time() - start_time, 3)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        combined = (stdout + "\n" + stderr).strip()
        lines = combined.splitlines()
        tail = "\n".join(lines[-80:])
        return {
            "ok": True,
            "exit_code": proc.returncode,
            "tail": tail,
            "duration_s": duration,
        }
    except subprocess.TimeoutExpired as e:
        duration = round(time.time() - start_time, 3)
        stdout = e.stdout or "" if isinstance(e.stdout, str) else ""
        stderr = e.stderr or "" if isinstance(e.stderr, str) else ""
        combined = (stdout + "\n" + stderr).strip()
        lines = combined.splitlines()
        tail = "\n".join(lines[-80:]) if lines else "TIMEOUT: test timed out after 60s"
        return {
            "ok": True,
            "exit_code": 124,
            "tail": tail,
            "duration_s": duration,
        }
    except Exception as e:
        return {
            "ok": False,
            "exit_code": -1,
            "tail": f"subprocess_error: {e}",
            "duration_s": 0.0,
        }

def run_tests(node_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Tool invocation for run_tests.
    
    Validates node_id against state['test_node'] to prevent arbitrary execution
    or flag injection (such as `-x --pdb`).
    """
    expected_node = state.get("test_node", "")
    if node_id != expected_node or not TEST_NODE_REGEX.match(node_id):
        return {"ok": False, "error": "invalid_node_id"}

    return run_tests_raw(state, node_id=node_id, timeout=60)

def trace_lookup(
    span_id: str,
    spans_path: str,
    state: Dict[str, Any]
) -> Dict[str, Any]:
    """Look up a span record by span_id in the local spans file.
    
    Never calls external network or Neatlogs API.
    """
    if not state.get("flags", {}).get("lookup", True):
        return {"disabled": True}

    path = Path(spans_path).resolve()
    if not path.is_file():
        return {"ok": False, "error": "not_found"}

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("span_id") == span_id:
                    return {"ok": True, "span": record}
    except Exception as e:
        return {"ok": False, "error": f"lookup_error: {e}"}

    return {"ok": False, "error": "not_found"}

def open_pr(
    title: str,
    body: str,
    state: Dict[str, Any],
    verify: Optional[Callable[[], Dict[str, int]]] = None
) -> Dict[str, Any]:
    """Evaluate gate before opening a PR or completing a dry run.
    
    Enforces title <= 120 chars and body <= 4000 chars.
    """
    if len(title) > 120:
        return {"ok": False, "reason": "title_too_long"}
    if len(body) > 4000:
        return {"ok": False, "reason": "body_too_long"}

    repo = state.get("repo", ".")
    repo_path = Path(repo).resolve()

    # Get git diff against base_commit
    base_commit = state.get("base_commit", "HEAD~1")
    try:
        diff_res = subprocess.run(
            ["git", "diff", base_commit],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True
        )
        diff_text = diff_res.stdout
    except Exception:
        diff_text = ""

    # Build verify callable if not provided
    if verify is None:
        def default_verify():
            target_node = state.get("test_node", "")
            node_res = run_tests_raw(state, node_id=target_node)
            test_file = target_node.split("::")[0] if "::" in target_node else target_node
            file_res = run_tests_raw(state, node_id=test_file)
            return {
                "node_exit": node_res.get("exit_code", 1),
                "file_exit": file_res.get("exit_code", 1),
            }
        verify = default_verify

    # Evaluate gate
    gate_result = gate.evaluate(state, diff_text, verify)
    if not gate_result.get("allowed"):
        return {"ok": False, "allowed": False, "reason": gate_result.get("reason")}

    # Gate allowed -> check if live PR or dry run
    from src.fixloop import receipt
    receipt_body = receipt.generate_receipt(state, diff_text=diff_text)
    full_body = f"{receipt_body}\n\n## Model Notes\n{body}" if body else receipt_body

    flags = state.get("flags", {})
    if flags.get("dry_pr", True):
        # Dry run: record body to evidence
        run_id = state.get("run_id", "dry")
        evidence_dir = repo_path / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        pr_body_file = evidence_dir / f"pr-body-{run_id}.md"
        pr_body_file.write_text(f"# {title}\n\n{full_body}", encoding="utf-8")
        return {
            "ok": True,
            "allowed": True,
            "pr": "dry_run",
            "branch": state.get("branch", ""),
        }

    # Live PR creation with gh (argv list, never shell)
    try:
        push_res = subprocess.run(
            ["git", "push", "origin", state.get("branch", "")],
            cwd=str(repo_path),
            capture_output=True,
            text=True
        )
        gh_cmd = ["gh", "pr", "create", "--title", title, "--body", full_body]
        gh_res = subprocess.run(
            gh_cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True
        )
        pr_url = gh_res.stdout.strip()
        return {"ok": True, "allowed": True, "pr": "opened", "url": pr_url}
    except Exception as e:
        return {"ok": False, "error": f"gh_error: {e}"}

