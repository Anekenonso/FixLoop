import pytest
from src import cache

def test_compute_failure_contract():
    cache._last = None
    def boom():
        raise ValueError("boom")
    with pytest.raises(ValueError):
        cache.get_or_compute("k", boom)

def test_returns_computed_value():             # guard, passes on bug
    cache._last = None
    assert cache.get_or_compute("k", lambda: 7) == 7
