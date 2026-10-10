# FixLoop Claims Audit

> **Verification Rule:** Every numerical claim, rate, cost, and latency presented in FixLoop's `README.md`, video demo script, and public announcements is traced here to an exact file in `evidence/`. If a claim cannot be directly supported by a saved artifact, it is explicitly excluded.

---

## 1. Core Statistical Rate Claims

| Claim | Value | Source Artifact | Verification Method |
|---|---|---|---|
| **False PR Rate (Gated Runs)** | **0.0% (0/9 planted, 0/3 replay)** | [`evidence/experiments/summary.json`](../evidence/experiments/summary.json), [`evidence/replay/summary.json`](../evidence/replay/summary.json) | Oracle check `false_pr == False` across all 9 `full`-arm planted trials and all 3 real bug replay runs. |
| **Statistical Trials Evaluated** | **36 trials** | [`evidence/experiments/summary.json`](../evidence/experiments/summary.json) | 3 issues × 4 arms (`baseline`, `nogate`, `removal`, `full`) × 3 trials at temperature 0.7. |
| **Total Experiment Model Spend** | **$0.03705 USD** | [`evidence/experiments/summary.json`](../evidence/experiments/summary.json) | Sum of `cost_usd` across all 36 statistical trials. |
| **Mean Cost per Planted Run** | **$0.001007 USD** | [`plans/unit-economics.md`](../plans/unit-economics.md) | Calculated from measured tokens across all runs via standard model pricing. |
| **Mean Tokens per Planted Run** | **5,649 tokens** | [`evidence/experiments/summary.json`](../evidence/experiments/summary.json) | Arithmetic mean across 36 runs. |
| **Model Budget Runway** | **7,944 fix runs** | [`plans/unit-economics.md`](../plans/unit-economics.md) | $8.00 credit cap divided by $0.001007 mean cost per run. |

---

## 2. Real-World Historical Bug Replay Claims (`W2`)

| Claim | Value | Source Artifact | Verification Method |
|---|---|---|---|
| **Real Bug Cases Evaluated** | **3 cases** | [`docs/replay-cases.md`](replay-cases.md), [`evidence/replay/summary.md`](../evidence/replay/summary.md) | SWE-bench Lite instances: `pallets/flask` #4045, `psf/requests` #863, `pallets/flask` #4992. |
| **Pre-Registration Discipline** | **Committed prior to runs** | Git log commit `bcd86c7` | Commit timestamp precedes all `evidence/replay/*.json` creation timestamps. |
| **Real Bug Resolve Rate** | **3/3 (100.0%)** | [`evidence/replay/summary.json`](../evidence/replay/summary.json) | All 3 trials exited 0 with `oracle.resolved == True`. |
| **Real Bug False PR Rate** | **0/3 (0.0%)** | [`evidence/replay/summary.json`](../evidence/replay/summary.json) | Zero unverified or tampered PRs opened. |
| **Total Real Bug Spend** | **$0.00525 USD** | [`evidence/replay/summary.json`](../evidence/replay/summary.json) | Sum of costs across Case 01 ($0.00125), Case 02 ($0.00281), and Case 03 ($0.00118). |
| **Mean Tokens per Real Bug** | **9,994 tokens** | [`evidence/replay/summary.json`](../evidence/replay/summary.json) | Mean tokens across the 3 historical cases. |

---

## 3. Security & Break Matrix Claims

| Claim | Value | Source Artifact | Verification Method |
|---|---|---|---|
| **Break Matrix Scenarios** | **20 / 20 passed** | [`docs/break-matrix.md`](break-matrix.md), [`tests/test_break_matrix.py`](../tests/test_break_matrix.py) | Automated test suite executing all 20 adversary rows in isolated sandboxes. |
| **Maximum Diff Threshold** | **80 lines** | [`src/fixloop/gate.py`](../src/fixloop/gate.py) | Gate check 4 enforces `diff_lines <= 80`. Verified in Break Matrix Row 6. |
| **Maximum Verifying Attempts** | **2 attempts** | [`src/fixloop/driver.py`](../src/fixloop/driver.py) | Hardcoded loop invariant. Verified in Break Matrix Row 11. |
| **Gate Rejection Limit** | **2 rejections** | [`src/fixloop/driver.py`](../src/fixloop/driver.py) | Halts with `gate_reject_limit` upon second gate rejection. |

---

## 4. Partner Integration Verification

| Partner | Role Claimed | Evidence Artifact |
|---|---|---|
| **Neatlogs** | 14-field span telemetry & trace lookup memory across attempts | [`evidence/trace-links.md`](../evidence/trace-links.md), [`evidence/live/spans-*.jsonl`](../evidence/live/) |
| **Entire** | Complete build trajectory tracking and checkpoint git trailers | [`evidence/entire/`](../evidence/entire/), Git commit history |
| **cfo.ai** | Empirical unit economics model, gross margin analysis (99.95%), and downside shock sensitivity | [`plans/unit-economics.md`](../plans/unit-economics.md) |

---

## 5. Live Demonstration PR Verification (Phase 11)

| Claim | Value | Source Artifact | Verification Method |
|---|---|---|---|
| **Public Fixture Repo** | `Anekenonso/fixloop-sandbox` | [GitHub Repo](https://github.com/Anekenonso/fixloop-sandbox) | Clean fixture repository populated with `sandbox_template` files. |
| **Live PR Created** | [PR #1](https://github.com/Anekenonso/fixloop-sandbox/pull/1) | [`evidence/final-pr.json`](../evidence/final-pr.json) | Created via `gh pr create` with `status: pr_opened`, exit code 0. |
| **Trust Receipt Embedded** | Verified | [`evidence/receipt-final-pr.md`](../evidence/receipt-final-pr.md) | Deterministic receipt header with `Verdict: FIXED, gate ok` and diff stats. |
| **Live PR Tokens & Cost** | 7,263 tokens / $0.00131 USD | [`evidence/final-pr.json`](../evidence/final-pr.json) | Measured live on Issue 03 with LiteLLM proxy adapter. |

