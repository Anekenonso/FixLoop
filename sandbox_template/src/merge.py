def merge(left, right):
    return {**right, **left}  # BUG: left overwrites right; right must win
