# Dashboards showed stale numbers after the upstream outage, and nobody could tell why

get_or_compute quietly hands back the previous value when compute fails. There is no trace of the failure anywhere, so we lost hours. Please make this diagnosable.

TEST_NODE: tests/test_cache.py::test_compute_failure_contract
