# FixLoop Real-Bug Replay Summary (W2)

**Protocol:** REAL historical bugs from third-party repositories, replayed locally in isolated repositories without network. Each trial executed with `--max-attempts 2 --edit-root src/`.

| Target Bug | Test Node | Status | Oracle Resolved | False PR | Attempts | Tokens | Cost (USD) |
|---|---|---|---|---|---|---|---|
| **pallets/flask (Issue 4045)** | `tests/test_blueprints.py::test_dotted_name_not_allowed` | `passed` | `True` | `False` | 1 | 7,068 | $0.00125 |
| **psf/requests (Issue 863)** | `tests/test_requests.py::test_allow_list_of_hooks_to_register_hook` | `passed` | `True` | `False` | 1 | 16,522 | $0.00281 |
| **pallets/flask (Issue 4992)** | `tests/test_config.py::test_config_from_file_toml` | `passed` | `True` | `False` | 1 | 6,393 | $0.00118 |

## Key Statistical Findings
- **Resolved Rate:** 3/3 (100.0%)
- **False PR Rate:** 0/3 (0.0% false PR rate across all gated runs)
- **Mean Cost per Real Bug:** $0.001749 USD
- **Mean Tokens per Real Bug:** 9,994
- **Total Spend for 3 Real Bugs:** $0.00525 USD

All individual trust receipts are saved in `evidence/replay/receipt-*.md`.
