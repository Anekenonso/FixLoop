import pytest
from src.fixloop import gate
from src.fixloop.state import default_state

@pytest.fixture
def base_state():
    st = default_state()
    st["baseline"] = {"exit_code": 1, "tail": "FAILED test_page_size_is_exact"}
    st["edit_root"] = "src/"
    return st

def test_clean_fix_allowed(base_state):
    diff = """diff --git a/src/paginate.py b/src/paginate.py
index 1234567..89abcdef 100644
--- a/src/paginate.py
+++ b/src/paginate.py
@@ -1,3 +1,3 @@
 def page(items, number, size):
     start = number * size
-    end = start + size + 1
+    end = start + size
     return items[start:end]
"""
    verify_called = False
    def verify():
        nonlocal verify_called
        verify_called = True
        return {"node_exit": 0, "file_exit": 0}

    result = gate.evaluate(base_state, diff, verify)
    assert result == {"allowed": True, "reason": "ok"}
    assert verify_called is True

def test_assert_deleted(base_state):
    diff = """diff --git a/src/paginate.py b/src/paginate.py
--- a/src/paginate.py
+++ b/src/paginate.py
@@ -1,3 +1,2 @@
 def page(items, number, size):
-    assert items is not None
     return items
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "assert_deleted"}

def test_skip_added(base_state):
    diff = """diff --git a/src/paginate.py b/src/paginate.py
--- a/src/paginate.py
+++ b/src/paginate.py
@@ -1,2 +1,3 @@
 def page(items, number, size):
+    pytest.skip("workaround")
     return items
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "test_skipped"}

def test_xfail_added(base_state):
    diff = """diff --git a/src/paginate.py b/src/paginate.py
--- a/src/paginate.py
+++ b/src/paginate.py
@@ -1,2 +1,3 @@
+@pytest.mark.xfail
 def page(items, number, size):
     return items
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "test_skipped"}

def test_diff_too_large(base_state):
    added_lines = "\n".join(f"+    x_{i} = {i}" for i in range(41))
    removed_lines = "\n".join(f"-    old_{i} = {i}" for i in range(41))
    diff = f"""diff --git a/src/paginate.py b/src/paginate.py
--- a/src/paginate.py
+++ b/src/paginate.py
@@ -1,1 +1,1 @@
{removed_lines}
{added_lines}
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "diff_too_large"}

def test_test_file_edited(base_state):
    diff = """diff --git a/tests/test_paginate.py b/tests/test_paginate.py
--- a/tests/test_paginate.py
+++ b/tests/test_paginate.py
@@ -1,2 +1,2 @@
-def test_something(): pass
+def test_something_else(): pass
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "protected_path_touched"}

def test_pytest_ini_edited(base_state):
    diff = """diff --git a/pytest.ini b/pytest.ini
--- a/pytest.ini
+++ b/pytest.ini
@@ -1,2 +1,2 @@
-[pytest]
+[pytest_modified]
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "protected_path_touched"}

def test_conftest_edited(base_state):
    diff = """diff --git a/conftest.py b/conftest.py
--- a/conftest.py
+++ b/conftest.py
@@ -1,1 +1,2 @@
+# hook
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "protected_path_touched"}

def test_no_prior_red_run(base_state):
    base_state["baseline"]["exit_code"] = 0
    diff = """diff --git a/src/paginate.py b/src/paginate.py
--- a/src/paginate.py
+++ b/src/paginate.py
@@ -1,1 +1,1 @@
-old
+new
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "no_prior_red_run"}

def test_timeout_prior_run_not_accepted(base_state):
    base_state["baseline"]["exit_code"] = 124
    diff = """diff --git a/src/paginate.py b/src/paginate.py
--- a/src/paginate.py
+++ b/src/paginate.py
@@ -1,1 +1,1 @@
-old
+new
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "no_prior_red_run"}

def test_node_not_green(base_state):
    diff = """diff --git a/src/paginate.py b/src/paginate.py
--- a/src/paginate.py
+++ b/src/paginate.py
@@ -1,1 +1,1 @@
-old
+new
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 1, "file_exit": 0})
    assert result == {"allowed": False, "reason": "node_not_green"}

def test_file_not_green(base_state):
    diff = """diff --git a/src/paginate.py b/src/paginate.py
--- a/src/paginate.py
+++ b/src/paginate.py
@@ -1,1 +1,1 @@
-old
+new
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 1})
    assert result == {"allowed": False, "reason": "file_not_green"}

def test_empty_diff(base_state):
    result = gate.evaluate(base_state, "", lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "empty_diff"}

def test_rename_touching_protected_path(base_state):
    diff = """diff --git a/src/paginate.py b/tests/paginate.py
similarity index 100%
rename from src/paginate.py
rename to tests/paginate.py
"""
    result = gate.evaluate(base_state, diff, lambda: {"node_exit": 0, "file_exit": 0})
    assert result == {"allowed": False, "reason": "protected_path_touched"}
