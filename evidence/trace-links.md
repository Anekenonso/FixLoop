# FixLoop Neatlogs Trace Links

All observability spans for FixLoop runs are ingested and materialized in the Neatlogs dashboard under project `265a1b5d-2171-404c-ad4a-102c70bed8b7`.

## Verified Ingest Probe
- **Trace ID:** `3cff2685c42a413ed0cf3a1256d1611e`
- **Dashboard URL:** [https://app.neatlogs.com/projects/265a1b5d-2171-404c-ad4a-102c70bed8b7/traces/3cff2685c42a413ed0cf3a1256d1611e](https://app.neatlogs.com/projects/265a1b5d-2171-404c-ad4a-102c70bed8b7/traces/3cff2685c42a413ed0cf3a1256d1611e)
- **Status:** Ingestion succeeded, materialized & verified via `doctor --probe`

## Headline Runs (Issue 03, Temp 0.0)
| Arm | Workflow Name | Evidence File | Status |
|---|---|---|:---:|
| `baseline` | `fixloop-baseline` | [`evidence/baseline.json`](file:///evidence/baseline.json) | `passed` |
| `intervention` (`full`) | `fixloop-full` | [`evidence/intervention.json`](file:///evidence/intervention.json) | `passed` |
| `removal` | `fixloop-removal` | [`evidence/removal.json`](file:///evidence/removal.json) | `passed` |
| `nogate` | `fixloop-nogate` | [`evidence/nogate.json`](file:///evidence/nogate.json) | `passed` |

## Live Acceptance Verification Runs (Claude Sonnet 4.6 via LiteLLM)
- **Issue 01 (Paginate):** [`evidence/live/spans-01.jsonl`](file:///evidence/live/spans-01.jsonl)
- **Issue 02 (Merge):** [`evidence/live/spans-02.jsonl`](file:///evidence/live/spans-02.jsonl)
- **Issue 03 (Cache):** [`evidence/live/spans-03.jsonl`](file:///evidence/live/spans-03.jsonl)
