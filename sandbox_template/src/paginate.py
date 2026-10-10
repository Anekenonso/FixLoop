def page(items, number, size):
    start = number * size
    end = start + size + 1  # BUG: off by one
    return items[start:end]
