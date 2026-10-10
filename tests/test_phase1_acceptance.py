import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def run_cmd(cmd, cwd):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def test_phase1():
    root = Path(__file__).resolve().parent.parent
    template = root / "sandbox_template"
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Copy template into tmp_path
        for item in template.iterdir():
            if item.is_dir():
                shutil.copytree(item, tmp_path / item.name)
            else:
                shutil.copy2(item, tmp_path / item.name)
        
        py = sys.executable
        
        # 1. Target nodes exit 1 on buggy code
        code, out, _ = run_cmd([py, "-m", "pytest", "tests/test_paginate.py::test_page_size_is_exact", "-q", "--tb=line"], tmp_path)
        assert code == 1, f"Expected paginate target to exit 1, got {code}"
        
        code, out, _ = run_cmd([py, "-m", "pytest", "tests/test_merge.py::test_right_wins", "-q", "--tb=line"], tmp_path)
        assert code == 1, f"Expected merge target to exit 1, got {code}"
        
        code, out, _ = run_cmd([py, "-m", "pytest", "tests/test_cache.py::test_compute_failure_contract", "-q", "--tb=line"], tmp_path)
        assert code == 1, f"Expected cache target to exit 1, got {code}"
        print("[PASS] All 3 target tests exit 1 on buggy code")
        
        # 2. Guard tests exit 0 on buggy code
        code, out, _ = run_cmd([py, "-m", "pytest", "tests/test_paginate.py::test_first_page_starts_at_zero", "-q", "--tb=line"], tmp_path)
        assert code == 0, f"Expected paginate guard to exit 0, got {code}"
        
        code, out, _ = run_cmd([py, "-m", "pytest", "tests/test_merge.py::test_disjoint_keys_merge", "-q", "--tb=line"], tmp_path)
        assert code == 0, f"Expected merge guard to exit 0, got {code}"
        
        code, out, _ = run_cmd([py, "-m", "pytest", "tests/test_cache.py::test_returns_computed_value", "-q", "--tb=line"], tmp_path)
        assert code == 0, f"Expected cache guard to exit 0, got {code}"
        print("[PASS] All 3 guard tests exit 0 on buggy code")
        
        # 3. Log-only patch to cache.py keeps target red (exit 1)
        log_patch = """_last = None
import logging

def get_or_compute(key, compute):
    global _last
    try:
        _last = compute()
        return _last
    except Exception:
        logging.exception("compute failed")
        return _last
"""
        (tmp_path / "src" / "cache.py").write_text(log_patch, encoding="utf-8")
        code, out, _ = run_cmd([py, "-m", "pytest", "tests/test_cache.py::test_compute_failure_contract", "-q", "--tb=line"], tmp_path)
        assert code == 1, f"Expected log-only patch target to exit 1, got {code}"
        print("[PASS] Log-only patch to cache.py still exits 1")
        
        # 4. Apply obvious fixes -> targets and guards both exit 0
        paginate_fix = """def page(items, number, size):
    start = number * size
    end = start + size
    return items[start:end]
"""
        (tmp_path / "src" / "paginate.py").write_text(paginate_fix, encoding="utf-8")
        code, _, _ = run_cmd([py, "-m", "pytest", "tests/test_paginate.py", "-q", "--tb=line"], tmp_path)
        assert code == 0, f"Expected fixed paginate to exit 0, got {code}"
        
        merge_fix = """def merge(left, right):
    return {**left, **right}
"""
        (tmp_path / "src" / "merge.py").write_text(merge_fix, encoding="utf-8")
        code, _, _ = run_cmd([py, "-m", "pytest", "tests/test_merge.py", "-q", "--tb=line"], tmp_path)
        assert code == 0, f"Expected fixed merge to exit 0, got {code}"
        
        cache_fix = """_last = None

def get_or_compute(key, compute):
    global _last
    try:
        _last = compute()
        return _last
    except Exception:
        raise
"""
        (tmp_path / "src" / "cache.py").write_text(cache_fix, encoding="utf-8")
        code, _, _ = run_cmd([py, "-m", "pytest", "tests/test_cache.py", "-q", "--tb=line"], tmp_path)
        assert code == 0, f"Expected fixed cache to exit 0, got {code}"
        print("[PASS] Obvious fixes pass all tests (targets + guards exit 0)")

if __name__ == "__main__":
    test_phase1()
    print("ALL PHASE 1 ACCEPTANCE CHECKS PASSED!")
