# Raise error when blueprint name contains a dot

Blueprints cannot have a dot in their name because the dot is used to separate the blueprint name and endpoint in url_for. Currently, Blueprint allows dots in names which later leads to confusing errors.

TEST_NODE: tests/test_blueprints.py::test_dotted_name_not_allowed
