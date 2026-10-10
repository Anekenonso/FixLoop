_last = None

def get_or_compute(key, compute):
    global _last
    try:
        _last = compute()
        return _last
    except Exception:
        return _last   # BUG: swallows the error silently
