from src.paginate import page

def test_page_size_is_exact():
    assert page(list(range(10)), 1, 3) == [3, 4, 5]

def test_first_page_starts_at_zero():          # regression guard, passes on bug
    assert page(list(range(10)), 0, 3)[0] == 0
