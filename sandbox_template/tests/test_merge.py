from src.merge import merge

def test_right_wins():
    assert merge({"a": 1, "b": 1}, {"b": 2}) == {"a": 1, "b": 2}

def test_disjoint_keys_merge():                # guard, passes on bug
    assert merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
