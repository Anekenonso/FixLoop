# FixLoop Neatlogs Trace Links

All observability spans for FixLoop runs are ingested and materialized in the Neatlogs dashboard under project `265a1b5d-2171-404c-ad4a-102c70bed8b7`.

## Verified Ingest Probe
- **Trace ID:** `4982756b3b764d51d2f8cb7cc20fd98c`
- **Dashboard URL:** [https://app.neatlogs.com/projects/265a1b5d-2171-404c-ad4a-102c70bed8b7/traces/4982756b3b764d51d2f8cb7cc20fd98c](https://app.neatlogs.com/projects/265a1b5d-2171-404c-ad4a-102c70bed8b7/traces/4982756b3b764d51d2f8cb7cc20fd98c)
- **Status:** Ingestion succeeded, materialized & verified via `doctor --probe` (8/8 checks passed).

## Headline "Before vs After" Traces (Issue 03)

Judges can inspect and compare these two live traces in Neatlogs to verify the contrast between an un-gated agent run and FixLoop's causal gated recovery:

| Arm | Description | Live Neatlogs Trace Link | Status / Outcome |
|---|---|---|:---:|
| **Before: `baseline`** | Naive un-gated single attempt; test failure halts without recovery path | [Trace `3f2f940d8ee1e1c91980f75571b251d5`](https://app.neatlogs.com/projects/265a1b5d-2171-404c-ad4a-102c70bed8b7/traces/3f2f940d8ee1e1c91980f75571b251d5) | `proposed_ungated` (Red / Unverified) |
| **After: `full` (Intervention)** | Multi-attempt gated recovery: Attempt 1 red -> Neatlogs span saved -> Attempt 2 `trace_lookup` -> fix applied -> green verified -> Gate OK | [Trace `f8dae75f6877187698e6d961e84b1eb7`](https://app.neatlogs.com/projects/265a1b5d-2171-404c-ad4a-102c70bed8b7/traces/f8dae75f6877187698e6d961e84b1eb7) | `passed` (Green / Gate OK + Trust Receipt) |

## Live Acceptance Verification Evidence
- **Issue 01 (Paginate):** [`evidence/live/spans-01.jsonl`](file:///evidence/live/spans-01.jsonl)
- **Issue 02 (Merge):** [`evidence/live/spans-02.jsonl`](file:///evidence/live/spans-02.jsonl)
- **Issue 03 (Cache):** [`evidence/live/spans-03.jsonl`](file:///evidence/live/spans-03.jsonl)
- **GitHub PR #1 with Live Receipt:** [fixloop-sandbox/pull/1](https://github.com/Anekenonso/fixloop-sandbox/pull/1)
