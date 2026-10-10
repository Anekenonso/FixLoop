# Allow lists in the dict values of the hooks argument

When passing a list of hooks in the hooks argument (e.g. `hooks={"response": [f1, f2]}`) or calling `register_hook("response", [f1, f2])`, requests appends the list itself rather than extending the hook list with each callback. As a result, items in the hook list are not callable.

TEST_NODE: tests/test_requests.py::test_allow_list_of_hooks_to_register_hook
