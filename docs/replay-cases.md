# Pre-Registration: Three Real Historical Bug Replay Cases (W2)

**Pre-registration timestamp:** 2026-10-10 18:27 UTC  
**Discipline rule:** This document is committed to git *before* any model run is performed on these cases. All three cases must be reported honestly with their resulting trust receipts (whether resolved or stopped).

---

## Selection Criteria (per W2 / Section 15 of Build Plan)
1. **Permissive open-source license** (BSD-3-Clause, Apache-2.0, MIT).
2. **Pure Python**; executes cleanly and deterministically with pytest.
3. **Offline feasibility**: The named test node runs completely offline in <60 seconds with zero external network or credentials.
4. **Authentic historical issue**: Real issue reports and fix commits from established third-party repositories in SWE-bench Lite.
5. **Small diff size**: Fix fits within FixLoop's gate limit (<= 80 lines changed).
6. **Difficulty gradation**:
   - Case 01: Low/Medium (validation exception on illegal dot in Blueprint name).
   - Case 02: Medium (dispatch handling for list of callback hooks).
   - Case 03: Medium/Hard (API extension adding boolean `text` mode for binary formats like TOML).

---

## Case 01: `pallets/flask` (Issue 4045)
- **Repository:** `pallets/flask` (https://github.com/pallets/flask)
- **Issue URL:** https://github.com/pallets/flask/issues/4045
- **Base Commit:** `d8c37f43724cd9fb0870f77877b7c4c7e38a19e0`
- **License:** BSD-3-Clause
- **Problem Statement:** "Blueprints cannot have a dot in their name because the dot is used to separate the blueprint name and endpoint in url_for. Currently, Blueprint allows dots in names which later leads to confusing errors."
- **Target Node:** `tests/test_blueprints.py::test_dotted_name_not_allowed`
- **Why Chosen:** Classic input validation defect in one of the most widely used Python web frameworks.
- **Feasibility Verification (No Model):**
  - Base commit: Exit code 1 (FAILED: ValueError not raised on dotted name).
  - Golden patch applied: Exit code 0 (PASSED in 0.04s).
  - Base restored: Exit code 1.
  - **Verdict:** FEASIBLE.

---

## Case 02: `psf/requests` (Issue 863)
- **Repository:** `psf/requests` (https://github.com/psf/requests)
- **Issue URL:** https://github.com/psf/requests/issues/863
- **Base Commit:** `a0df2cbb10419037d11d04352b3175405ab52941`
- **License:** Apache-2.0
- **Problem Statement:** "Allow lists in the dict values of the hooks argument. When passing a list of hooks (e.g. `hooks={'response': [f1, f2]}`) or calling `register_hook('response', [f1, f2])`, requests appends the list itself rather than extending the hook list with each callback. As a result, items in the hook list are not callable."
- **Target Node:** `tests/test_requests.py::test_allow_list_of_hooks_to_register_hook`
- **Why Chosen:** Type polymorphic API contract defect in the standard Python HTTP library.
- **Feasibility Verification (No Model):**
  - Base commit: Exit code 1 (FAILED: list object is not callable).
  - Golden patch applied: Exit code 0 (PASSED in 0.04s).
  - Base restored: Exit code 1.
  - **Verdict:** FEASIBLE.

---

## Case 03: `pallets/flask` (Issue 4992)
- **Repository:** `pallets/flask` (https://github.com/pallets/flask)
- **Issue URL:** https://github.com/pallets/flask/issues/4992
- **Base Commit:** `4c288bc97ea371817199908d0d9b12de9dae327e`
- **License:** BSD-3-Clause
- **Problem Statement:** "Add a file mode parameter to flask.Config.from_file(). `flask.Config.from_file` currently always opens files in text mode (`r`). However, modern standard library loaders such as `tomllib.load` require opening files in binary mode (`rb`). Add a `text: bool = True` parameter to `from_file` so binary loaders can pass `text=False`."
- **Target Node:** `tests/test_config.py::test_config_from_file_toml`
- **Why Chosen:** API signature evolution defect requiring optional parameter addition while preserving backwards compatibility.
- **Feasibility Verification (No Model):**
  - Base commit: Exit code 1 (FAILED: TypeError: File must be opened in binary mode).
  - Golden patch applied: Exit code 0 (PASSED in 0.05s).
  - Base restored: Exit code 1.
  - **Verdict:** FEASIBLE.

---

## Execution Protocol
Each replay case will be executed using FixLoop's generic CLI against its isolated clone:
```powershell
.\.venv\Scripts\python.exe -m src.fixloop run `
  --repo evidence/replay/<case-dir> `
  --issue-file <case-dir>/issue.md `
  --test <test-node> `
  --edit-root src/ `
  --model openai
```

Every run will emit:
1. Complete 14-field neatlogs span trace.
2. Saved state file in `evidence/replay/<case-id>.json`.
3. Deterministic Trust Receipt in `evidence/replay/receipt-<case-id>.md`.
4. Summary table in `evidence/replay/summary.md`.
