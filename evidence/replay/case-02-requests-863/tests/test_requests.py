import pytest
import requests

def test_allow_list_of_hooks_to_register_hook():
    """Issue 863: Allow lists in the dict values of the hooks argument."""
    def hook_a(): pass
    def hook_b(): pass
    hooks = [hook_a, hook_b]

    # Directly register list
    r = requests.Request()
    r.register_hook("args", hooks)
    for h in r.hooks["args"]:
        assert callable(h) is True

    # Register via constructor dict
    r2 = requests.Request(hooks={"args": hooks})
    for h in r2.hooks["args"]:
        assert callable(h) is True
