import re
from typing import Callable, Dict, Any, List, Tuple

DIFF_FILE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
ASSERT_PATTERN = re.compile(r"\bassert\b")
SKIP_PATTERN = re.compile(r"\b(pytest\.skip|importorskip|xfail|skipif|mark\.skip)\b")

def parse_diff(text: str) -> Tuple[List[str], List[str], List[str]]:
    """Parse unified git diff output into touched files, added lines, and removed lines.
    
    Prevents mistaking a removed line like '-- x' for a header.
    """
    files: List[str] = []
    added: List[str] = []
    removed: List[str] = []
    in_hunk = False

    for line in text.splitlines():
        m = DIFF_FILE.match(line)
        if m:
            files.extend([m.group(1), m.group(2)])
            in_hunk = False
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])

    return files, added, removed

def is_path_confined(path: str, edit_root: str = "src/") -> bool:
    """Verify that a path from git diff is under the allowed edit root.
    
    dev/null is permitted for newly created or deleted files.
    """
    if path in ("/dev/null", "dev/null"):
        return True
    
    # Normalize slashes and strip leading slashes
    norm_path = path.replace("\\", "/").lstrip("/")
    root = edit_root.replace("\\", "/").strip("/")
    
    if not root:
        return True
    
    return norm_path.startswith(f"{root}/") or norm_path == root

def evaluate(
    state: Dict[str, Any],
    diff_text: str,
    verify: Callable[[], Dict[str, int]]
) -> Dict[str, Any]:
    """Evaluate whether a proposed change is allowed to be opened as a PR.
    
    First failure wins, in strict priority order:
      1. no_prior_red_run
      2. empty_diff
      3. protected_path_touched
      4. assert_deleted
      5. test_skipped
      6. diff_too_large
      7. node_not_green
      8. file_not_green
      9. allowed: True, reason: "ok"
    """
    # 1. no_prior_red_run: baseline must be a real failure (not 0, not 124 timeout)
    baseline = state.get("baseline", {})
    base_exit = baseline.get("exit_code")
    if base_exit == 0 or base_exit == 124 or base_exit is None:
        return {"allowed": False, "reason": "no_prior_red_run"}

    # Parse diff
    files, added, removed = parse_diff(diff_text)

    # 2. empty_diff (empty text, no files, or no content/metadata changes)
    if not diff_text.strip() or not files:
        return {"allowed": False, "reason": "empty_diff"}

    # 3. protected_path_touched: all touched files must reside inside edit_root (default: src/)
    edit_root = state.get("edit_root", "src/")
    for f in files:
        if not is_path_confined(f, edit_root=edit_root):
            return {"allowed": False, "reason": "protected_path_touched"}

    has_meta_change = any(
        line.startswith(("rename ", "copy ", "deleted file ", "new file "))
        for line in diff_text.splitlines()
    )
    if not added and not removed and not has_meta_change:
        return {"allowed": False, "reason": "empty_diff"}

    # 4. assert_deleted: any removed line matches \bassert\b
    for line in removed:
        if ASSERT_PATTERN.search(line):
            return {"allowed": False, "reason": "assert_deleted"}

    # 5. test_skipped: any added line matches skip / xfail patterns
    for line in added:
        if SKIP_PATTERN.search(line):
            return {"allowed": False, "reason": "test_skipped"}

    # 6. diff_too_large: total added + removed lines > 80
    if len(added) + len(removed) > 80:
        return {"allowed": False, "reason": "diff_too_large"}

    # 7 & 8: Dynamic verification (lazy; only run once all static checks pass)
    verify_result = verify()
    if verify_result.get("node_exit") != 0:
        return {"allowed": False, "reason": "node_not_green"}

    if verify_result.get("file_exit") != 0:
        return {"allowed": False, "reason": "file_not_green"}

    # 9. All checks passed
    return {"allowed": True, "reason": "ok"}
