class Request:
    def __init__(self, hooks=None):
        self.hooks = {"args": []}
        if hooks:
            for k, v in hooks.items():
                self.register_hook(k, v)

    def register_hook(self, event, hook):
        """Properly register a hook."""
        if isinstance(hook, list):
            self.hooks[event].extend(hook)
        else:
            self.hooks[event].append(hook)
