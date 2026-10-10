# FixLoop Build Log (neatHack)

All commands and outputs logged in accordance with hackathon rules and build plan operating discipline.

---

## Phase 0 — Preflight & Environment Setup

- **Python Version:** Python 3.12.10
- **Git Version:** git version 2.48.1.windows.1
- **GitHub CLI:** gh version 2.101.0, authenticated as `Anekenonso`
- **Neatlogs SDK:** Installed `neatlogs==1.4.26` in virtual environment (`.venv`).
  - Command: `python -m neatlogs doctor --local --json` -> Exit 0 (PASS), saved to `evidence/doctor-local.json`
  - Command: `python -m neatlogs doctor --probe --json` -> Exit 0 (PASS, 8/8 checks passed, readback trace ID: `3cff2685c42a413ed0cf3a1256d1611e`), saved to `evidence/doctor-probe.json`
  - Live Sample Trace: `python -m src.fixloop.run_sample_trace` -> Exit 0, flushed and shut down cleanly.
- **Entire CLI:** Installed `entire` 0.11.4 (`windows/amd64`).
  - Command: `entire enable --agent antigravity --yes` -> Exit 0
  - Command: `entire login --device` -> Exit 0, authenticated as `github:Anekenonso`
  - Command: `entire doctor` -> Exit 0, all metadata and hooks OK.
  - Setup details recorded in `evidence/entire/setup.md`.
- **Security:** `.env` configured with `NEATLOGS_API_KEY` and `NEATLOGS_PROJECT_ID`, confirmed ignored by `.gitignore`.

---

## Phase 1 — Fixtures & Sandboxes

Created `sandbox_template/` containing:
- `pytest.ini` (`pythonpath = .`)
- `src/__init__.py`
- `src/paginate.py`, `tests/test_paginate.py`, `issues/01-paginate.md` (Issue 01: off-by-one bug)
- `src/merge.py`, `tests/test_merge.py`, `issues/02-merge.md` (Issue 02: dict merge precedence bug)
- `src/cache.py`, `tests/test_cache.py`, `issues/03-cache.md` (Issue 03: swallowed exception bug)

### Phase 1 Acceptance Verification
Executed automated acceptance test suite in isolated temporary copy:
- `python -m pytest tests/test_paginate.py::test_page_size_is_exact -q --tb=line` -> Exit 1 (Buggy)
- `python -m pytest tests/test_merge.py::test_right_wins -q --tb=line` -> Exit 1 (Buggy)
- `python -m pytest tests/test_cache.py::test_compute_failure_contract -q --tb=line` -> Exit 1 (Buggy)
- Guard tests on buggy code:
  - `test_paginate.py::test_first_page_starts_at_zero` -> Exit 0 (Guarded)
  - `test_merge.py::test_disjoint_keys_merge` -> Exit 0 (Guarded)
  - `test_cache.py::test_returns_computed_value` -> Exit 0 (Guarded)
- Log-only patch on `cache.py`:
  - `test_cache.py::test_compute_failure_contract` -> Exit 1 (Proves logging cannot fake fix)
- Obvious fixes applied:
  - All test files exit 0 (100% target and guard pass)
- **Status:** **ALL PHASE 1 ACCEPTANCE CHECKS PASSED**

---

## Phase 2 — `state.py`, `gate.py` + tests

- **State Management (`src/fixloop/state.py`):**
  - Canonical state data structure initialized with default fields.
  - Atomic persistence implemented via temporary file + `os.replace`.
  - Stateless projection engine implemented (`project_state`): strips attempt 1 failure details/diffs on attempt 2, leaving only pointer `span_id` when lookup is enabled.
- **Pure Code Gatekeeper (`src/fixloop/gate.py`):**
  - Robust unified diff parser (`parse_diff`) preventing regex evasion.
  - Strict priority order evaluation:
    1. `no_prior_red_run` (must be real failure, not 0 or 124 timeout)
    2. `empty_diff` (empty text or no changes)
    3. `protected_path_touched` (confinement to `src/` or configured `--edit-root`)
    4. `assert_deleted` (deleting asserts strictly prohibited)
    5. `test_skipped` (adding `pytest.skip`, `xfail`, etc. strictly prohibited)
    6. `diff_too_large` (added + removed > 80 lines)
    7. `node_not_green` (target test node must exit 0)
    8. `file_not_green` (full test file must exit 0 regression guard)
    9. `allowed: True, reason: "ok"`
- **Acceptance Verification:**
  - Command: `pytest -q -rA tests/test_gate.py` -> 14 passed in 0.08s
  - Command: `pytest -q -rA tests/test_state.py` -> 4 passed in 0.12s
  - Output captured to `evidence/gate-reject.txt`.
- **Status:** **ALL PHASE 2 ACCEPTANCE CHECKS PASSED**

---

## Phase 3 — `tools.py` & Security Invariant Tests

- **Tool Implementations (`src/fixloop/tools.py`):**
  - `read_issue`: Parses issue markdown files. Extracts `# title`, body, and `TEST_NODE: tests/...::...`. Missing issue returns `missing_issue`; missing/malformed `TEST_NODE` returns `malformed_issue`.
  - `read_file`: Sandboxed reading of numbered lines (1-indexed inclusive, max 200 lines). Enforces `target.resolve().relative_to(repo)` to strictly prevent path traversal (`../`), absolute paths, and external symlink escapes (`path_outside_repo`).
  - `edit_file`: Exact substring replacement confined to `edit_root` (default `src/`). Rejects protected paths like `tests/` or `pytest.ini` (`protected_path`). Enforces exact-occurrence check (`count(old) == 1`, returning `mismatch` and leaving file untouched otherwise). Rejects additions containing `pytest.skip`, `importorskip`, `xfail`, `skipif`, `mark.skip` (`test_skipped`). Automatically commits valid changes as `fixloop attempt <attempt>: <test_node>`.
  - `run_tests`: Validates `node_id == state['test_node']` and matches strict regex `^tests/[A-Za-z0-9_/]+\.py::[A-Za-z0-9_]+$` to prevent flag injection (`-x --pdb`) or arbitrary execution (`invalid_node_id`). Calls `run_tests_raw`.
  - `run_tests_raw`: Sanitized subprocess execution. Passes only `PATH`, `HOME=<tmp>`, `USERPROFILE=<tmp>`, `PYTHONDONTWRITEBYTECODE=1`, `LANG=C.UTF-8` (+ Windows OS runtime variables `SYSTEMROOT`/`SystemDrive`). Guarantees environment secrets (e.g. `FIXLOOP_PLANTED_SECRET`, API keys) are strictly absent. Exact argv format: `[sys.executable, "-m", "pytest", node_id, "-q", "--tb=line"]`. Enforces timeout (default 60s) returning exit code 124.
  - `trace_lookup`: Reads `evidence/spans.jsonl` locally without any network or external HTTP calls. Respects `--no-trace-lookup` (`flags['lookup'] = False`) returning `{"disabled": True}`.
  - `open_pr`: Enforces title <= 120 chars, body <= 4000 chars. Invokes gate verification prior to any PR actions. Under dry-run mode (default), saves body to `evidence/pr-body-<run_id>.md`.
- **Acceptance Verification (`tests/test_tools.py`):**
  - Command: `pytest tests/test_tools.py -v -rA` -> 12 passed in 74.34s
  - Command: `pytest -q` (full test suite) -> 31 passed in 62.49s
  - Verified Break-Matrix rows:
    - Row 1: Issue file without `TEST_NODE` -> `malformed_issue`
    - Row 2: `read_file` with `../`, absolute path, symlink out of repo -> `path_outside_repo`
    - Row 3: `edit_file` with `old` absent or duplicate -> `mismatch`, file hash unchanged
    - Row 4: `edit_file` path `tests/...` or `pytest.ini` -> `protected_path`, file hash unchanged
    - Row 5: `edit_file` new text with `pytest.skip` / `xfail` -> `test_skipped`, file hash unchanged
    - Row 12: `run_tests` with another node id or `-x --pdb` -> `invalid_node_id`
    - Row 16: Planted secret in env -> strictly invisible inside pytest subprocess (asserted in test)
    - Row 17: Test hangs (timeout) -> exit code 124
    - Exact argv assertion: verified `[sys.executable, "-m", "pytest", node_id, "-q", "--tb=line"]` via monkeypatched `subprocess.run`.
- **Status:** **ALL PHASE 3 ACCEPTANCE CHECKS PASSED**

---

## Phase 4 — `driver.py`, `cli.py`, `fake` Model Adapter & Tests

- **System Prompt (`src/fixloop/prompt.txt`):**
  - Concise prompt (< 600 words) defining the six tools, JSON schema, authority boundaries, untrusted data handling, confinement under `src/`, 2 verifying run limit, and mandatory `trace_lookup` on attempts >= 2.
- **Model Adapter & Fake Simulator (`src/fixloop/model.py`):**
  - `Action` dataclass (`tool`, `args`, `usage`) and `ModelError`.
  - `parse_action_response`: Strict JSON parsing with markdown code-fence stripping.
  - `FakeModelAdapter`: Purely view-driven simulation without hidden counters.
    - Issue 01: Off-by-one fix in 1 attempt.
    - Issue 02: Dict merge precedence fix in 1 attempt.
    - Issue 03: Attempt 1 naive comment-only edit (fails). Attempt 2 with pointer inspects trace via `trace_lookup`, applies `raise` patch, passes, and opens PR. Attempt 2 without pointer (removal arm) repeats attempt 1 edit, mismatches, and halts.
    - Error injection modes (`unknown_tool`, `invalid_json`, `junk_loop`) for break-matrix validation.
  - `get_adapter`: Factory supporting `fake`, `openai`, `anthropic`.
- **Authoritative Driver Loop (`src/fixloop/driver.py`):**
  - PID-based atomic locking (`.fixloop/state.lock`) verifying process liveness via Windows API / POSIX signals; cleanly replaces stale locks from dead processes.
  - Enforces clean repository check at start (`git status --porcelain`).
  - Baseline verification run (Attempt 0) logged to spans before model actions.
  - Step budget (max 24) and rejection budget (max 6) enforcement.
  - Enforces `allowed_tools` state machine:
    - On `mismatch` -> forced `read_file`
    - On `timeout_retry` -> forced `run_tests`
    - On `green` -> forced `open_pr`
    - On `attempt >= 2` with lookup enabled -> forced `trace_lookup` until called
  - Local span generation append-only to `evidence/spans.jsonl`.
  - Independent post-run `oracle` execution verifying target test node and test suite pass on final tree; computes authoritative `false_pr` metric.
  - Standard exit codes: 0 (`passed`/`pr_opened`), 1 (`stopped`), 2 (config/lock/dirty repo error), 3 (`proposed_ungated`).
- **CLI & Packaging (`src/fixloop/cli.py`, `src/fixloop/__main__.py`, `pyproject.toml`):**
  - Configured `python -m fixloop run` with all flags (`--repo`, `--issue`, `--model`, `--arm`, `--no-gate`, `--no-trace-lookup`, `--pr`, etc.).
  - Configured `pyproject.toml` with dependencies, Python `>=3.10,<3.14`, and `prompt.txt` package data.
- **Acceptance Verification (`tests/test_driver_fake_model.py`):**
  - Command: `pytest tests/test_driver_fake_model.py -v -rA` -> 12 passed in 169.84s
    - `test_driver_issue03_full_arm`: red -> comment patch -> red -> `trace_lookup` -> re-raise -> green -> gate ok -> `passed`, oracle resolved, `false_pr` false.
    - `test_driver_issue03_removal_arm`: `--no-trace-lookup` attempt 2 halted -> `stopped`, stop file generated, oracle unresolved.
    - `test_driver_issue03_baseline_ungated_arm`: `--no-gate --max-attempts 1` ends `proposed_ungated`, oracle unresolved, `false_pr` true (proves false PR detection metric).
    - `test_driver_issue01_full_arm` & `test_driver_issue02_full_arm`: both pass in 1 attempt.
    - Security / resilience cases passed: unknown tool, invalid JSON, junk loop, lock held (exit 2), stale lock recovery (exit 0), dirty repo at start (exit 2), missing `TEST_NODE` (exit 1).
    - `test_cli_execution_python_m_fixloop`: confirmed `python -m src.fixloop run --repo <tmp> --issue 03 --model fake` exits 0.
  - Full test suite: `pytest -q` -> 43 passed in 135.35s across all 4 phases.
- **Status:** **ALL PHASE 4 ACCEPTANCE CHECKS PASSED**

---

## Phase 5 — `tracing.py`, Neatlogs Observability & Spans Ingestion

- **Tracing Implementation (`src/fixloop/tracing.py`):**
  - Implemented `init_tracing(workflow_name)`: Initializes Neatlogs SDK (`endpoint="https://ingest.neatlogs.com"`) if `NEATLOGS_API_KEY` is present; gracefully falls back to local logging if absent.
  - Implemented `flush_tracing()`: Flushes pending spans to Neatlogs on attempt transitions.
  - Implemented `shutdown_tracing()`: Cleanly flushes and shuts down Neatlogs SDK before process termination.
  - Implemented `redact_args(args)`: Sanitizes sensitive argument keys (`token`, `key`, `secret`, `password`, `auth`, `credential`).
  - Implemented `log_span(spans_path, ...)`: Records JSONL span with all 14 required fields (Section 3.7):
    - `span_id, parent_span_id, run_id, attempt, name, tool, args_redacted, exit_code, tail (max 80 lines), diff, cost_usd, tokens, recovery_of, model_id`
- **Driver Integration (`src/fixloop/driver.py`):**
  - Wired `tracing.init_tracing(workflow_name=f"fixloop-{cfg.arm}")` at loop start.
  - Baseline run (Attempt 0) logged with all 14 fields as tool `run_tests_raw`.
  - Main loop tool calls logged with all 14 fields; tracks `parent_span_id` and records `recovery_of` on `trace_lookup`.
  - Added `tracing.flush_tracing()` on red run attempt transitions.
  - Added `tracing.shutdown_tracing()` in driver `finally` block before process lock release.
- **Acceptance Verification (`tests/test_tracing.py`):**
  - Command: `pytest tests/test_tracing.py -v -rA` -> 6 passed in 28.65s:
    - `test_fake_model_spans_schema_and_fields`: Verified `evidence/spans.jsonl` contains all 14 fields with correct types, tail <= 80 lines, and `recovery_of` populated on `trace_lookup`.
    - `test_spans_written_without_neatlogs_api_key`: Verified driver writes complete spans JSONL even when `NEATLOGS_API_KEY` is unset.
    - `test_doctor_local_evidence_valid`: Verified `evidence/doctor-local.json` exists with status `"pass"`.
    - `test_model_sdk_not_imported_at_top_level`: AST check verifies `openai` and `anthropic` are not imported at module top-level before `neatlogs.init`.
    - `test_redact_sensitive_args`: Verified argument redaction.
    - `test_tail_truncation_max_80_lines`: Verified tail is capped at 80 lines.
- **Status:** **ALL PHASE 5 ACCEPTANCE CHECKS PASSED**

---

## Phase 6 — Live Model Adapter, Cost Accounting & Live Verification Runs

- **Model Adapters (`src/fixloop/model.py`):**
  - Implemented `OpenAIAdapter`: Uses OpenAI Chat Completions API with strict JSON formatting (`response_format={"type": "json_object"}`), configurable `temperature`, and base URL support (`OPENAI_BASE_URL` pointing to LiteLLM sponsored proxy `https://litellm.vision.aivar.app/v1`).
  - Implemented `AnthropicAdapter`: Alternative provider using Anthropic Messages API.
  - Implemented `compute_cost`: Reads `FIXLOOP_PRICE_IN_PER_MTOK` and `FIXLOOP_PRICE_OUT_PER_MTOK` from environment to compute exact USD costs per call.
  - Robust JSON parsing in `parse_action_response`: Strips markdown fences, parses direct JSON, and safely extracts JSON objects if model prepends conversational text.
  - Lazy SDK import inside adapter initialization: Preserves import ordering guarantee where `neatlogs.init` executes before model SDK load.
- **Unit & Offline Testing (`tests/test_model.py`):**
  - Command: `pytest tests/test_model.py -v -rA` -> 8 passed:
    - JSON parser, markdown fence stripping, invalid JSON / missing keys error handling.
    - Cost computation with and without pricing environment variables.
    - Missing credentials error handling (exit 2 compliance).
    - Mocked OpenAI Chat Completion test verifying token counting and cost attribution.
    - Transport error propagation as `ModelError`.
- **Live Acceptance Runs (`evidence/live/`):**
  - Tested on `claude-sonnet-4.6` via the sponsored hackathon LiteLLM proxy:
    - **Issue 01 (Paginate):**
      - Exit code: 0, status: `passed`, attempts: 1, tokens: 4,330, cost: $0.00075 USD
      - Oracle resolved: `True`, False PR: `False`
    - **Issue 02 (Merge):**
      - Exit code: 0, status: `passed`, attempts: 1, tokens: 5,552, cost: $0.00098 USD
      - Oracle resolved: `True`, False PR: `False`
    - **Issue 03 (Cache):**
      - Exit code: 0, status: `passed`, attempts: 1, tokens: 7,284, cost: $0.00132 USD
      - Oracle resolved: `True`, False PR: `False`
  - Total token spend across all 3 live issues: 17,166 tokens (< 15% of single-run cap of 120,000).
  - Total dollar spend across all 3 live issues: $0.003 USD (well within $0.50 budget cap).
  - Live traces ingested, flushed to Neatlogs, and saved to `evidence/live/spans-*.jsonl` and `evidence/live/state-*.json`.
- **Status:** **ALL PHASE 6 ACCEPTANCE CHECKS PASSED**

---

## Phase 7 — Experiments & Statistical Rate Table

- **Experiment Engine (`src/fixloop/experiment.py`, `src/fixloop/cli.py`):**
  - Implemented `run_experiment()` executing matrix of issues, arms, and trials in isolated subprocess sandboxes.
  - Implemented arm parameter mapping:
    - `baseline`: `--max-attempts 1 --no-gate --no-trace-lookup` (naive single-shot agent)
    - `nogate`: `--no-gate` (measures unverified proposal behavior)
    - `removal`: `--no-trace-lookup` (isolates causal effect of state memory across attempts)
    - `full`: standard FixLoop with gate and trace memory
  - Implemented statistical table generator: Computes resolved rate, false PR rate, mean attempts, mean tokens, mean cost, and red->green recoveries.
  - Implemented `evidence/recovery.json` generator adhering strictly to the section 5 selection rule (first full-arm trial showing red->green, or explicit non-cherry-picked statement if none observed live).
- **Unit & Offline Testing (`tests/test_experiment.py`):**
  - Command: `pytest tests/test_experiment.py -v -rA` -> 4 passed:
    - `test_arm_flag_mapping`: Verifies CLI arguments mapped for each arm.
    - `test_detect_recovery`: Verifies red->green recovery detection.
    - `test_generate_summary_table`: Verifies rate table computation.
    - `test_recovery_selection_fallback`: Verifies non-cherry-picked fallback schema.
- **Headline Runs (Issue 03 at Temp 0.0):**
  - Executed reproducible headline runs across all 4 arms:
    - `evidence/baseline.json` (`baseline` arm): Status `passed`, oracle resolved: `True`, false PR: `False`
    - `evidence/intervention.json` (`full` arm): Status `passed`, oracle resolved: `True`, false PR: `False`
    - `evidence/removal.json` (`removal` arm): Status `passed`, oracle resolved: `True`, false PR: `False`
    - `evidence/nogate.json` (`nogate` arm): Status `passed`, oracle resolved: `True`, false PR: `False`
  - Documented trace IDs and dashboard URLs in `evidence/trace-links.md`.
- **Statistical Experiment Matrix (36 Runs at Temp 0.7):**
  - Command: `python -m src.fixloop experiment --model openai --issues 01 02 03 --arms baseline nogate removal full --trials 3 --temperature 0.7 --total-budget-usd 8.0` -> Exit 0
  - Completed all 36 runs (3 issues × 4 arms × 3 trials).
  - Total dollar spend: $0.037 USD (well under $8.00 cap).
  - Saved individual trial results to `evidence/experiments/<issue>-<arm>-<trial>.json`.
  - Generated `evidence/experiments/summary.md` and `evidence/experiments/summary.json`.
  - Generated `evidence/recovery.json` per section 5 selection rule:
    `{"status": "not_run", "reason": "no full-arm trial showed red->green live (models solved in attempt 1 or halted)"}`
  - Verified 0% false PR rate across all `full` arm runs.
- **Full Test Suite Verification:**
  - Command: `pytest -q` -> 61 passed in 164s (100% pass across all components).
- **Status:** **ALL PHASE 7 ACCEPTANCE CHECKS PASSED**

---

## Phase 8 — Break Matrix & Security Invariants

- **Security & Authority Verification Suite (`tests/test_break_matrix.py`):**
  - Implemented unit tests for all 20 attack rows specified in Section 6 of the build plan:
    - Row 1: Issue file missing `TEST_NODE` -> stops with `malformed_issue`, exit 1.
    - Row 2: `read_file` with directory traversal (`../`, absolute path) -> `path_outside_repo`.
    - Row 3: `edit_file` with `old` absent or duplicate -> `mismatch`, file hash unchanged.
    - Row 4: `edit_file` on `tests/` or `pytest.ini` -> `protected_path`, hash unchanged.
    - Row 5: `edit_file` injecting `pytest.skip` / `xfail` -> `test_skipped`, rejected before write.
    - Row 6: Diff deleting an `assert` -> gate `assert_deleted`, allowed: False.
    - Row 7: Diff editing a test file only -> gate `protected_path_touched`, allowed: False.
    - Row 8: `open_pr` before green run -> gate `node_not_green`, allowed: False.
    - Row 9: Unknown tool name -> counted in rejections, no state corruption.
    - Row 10: Non-JSON model output -> `invalid_action`, counted in rejections.
    - Row 11: Junk loop on premature PR -> halts on `gate_reject_limit` / `too_many_rejections`.
    - Row 12: `run_tests` flag injection (`-x --pdb`) -> `invalid_node_id`, no subprocess spawned.
    - Row 13: Second process while lock held -> exit 2.
    - Row 14: Stale lock (dead PID) -> lock replaced, run proceeds, exit 0.
    - Row 15: Missing model API key -> exit 2 without silent fake fallback.
    - Row 16: Planted host secret -> invisible inside pytest subprocess.
    - Row 17: Hanging test (timeout) -> exit 124, one retry, then stop.
    - Row 18: Dirty git repo at start -> exit 2.
    - Row 19: Token cap exceeded (`--max-tokens-per-run`) -> stops with `budget_exceeded`.
    - Row 20: `--model fake` with headline `--out` -> refused with exit 2.
- **Break Matrix Artifact (`docs/break-matrix.md`):**
  - Complete 20-row table mapping attack description, expected behavior, exact command executed, observed result, and status `done`.
  - Zero rows skipped, zero placeholders.
- **Acceptance Verification:**
  - Command: `pytest tests/test_break_matrix.py -v -rA` -> **20 passed in 70.48s** (100% pass across all 20 rows).
- **Status:** **ALL PHASE 8 ACCEPTANCE CHECKS PASSED**

---

## Phase 9 — Unit Economics & cfo.ai Inputs

- **Unit Economics Model (`plans/unit-economics.md`):**
  - Synthesized measured empirical data from `evidence/experiments/summary.json` and `evidence/intervention.json`.
  - Defined explicit classifications for all metrics:
    - `MEASURED`: Mean model cost per run ($0.001007 USD), mean tokens (5,649), resolve rate (100%), false PR rate (0%).
    - `SCENARIO`: Price per merged fix ($40.00, refund on unverified stop), CI overhead per run ($0.02).
    - `UNKNOWN`: Cash runway labeled `cash unknown; model-budget runway only` (strictly obeying rule against invented cash).
  - Derived core economic formulas:
    - Cost per resolved fix = mean cost per run ÷ resolve rate = $0.001007 USD (at measured 1.0 resolve rate).
    - Gross margin = 99.95% at measured baseline; 99.84% under conservative 33% resolve rate downside shock.
  - Modeled 3 core scenarios:
    - Scenario A: 100 fixes/month at measured resolve rate ($4,000 revenue, $2.10 COGS, 99.95% margin).
    - Scenario B: Provider token prices doubled (99.94% margin).
    - Scenario C: Lower-bound 33% resolve rate with 200 refunded stops ($4,000 revenue, $6.30 COGS, 99.84% margin).
  - Runway Analysis:
    - Model budget runway on $8.00 credit cap = **7,944 autonomous fix runs**.
    - Full 36-trial headline matrix consumed only $0.03705 USD total.
  - Provided cfo.ai inputs mapping for hackathon judging requirements.
- **Status:** **ALL PHASE 9 ACCEPTANCE CHECKS PASSED**



