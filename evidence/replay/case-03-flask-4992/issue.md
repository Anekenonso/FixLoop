# Add a file mode parameter to flask.Config.from_file()

flask.Config.from_file currently always opens files in text mode (`r`). However, modern standard library loaders such as `tomllib.load` require opening files in binary mode (`rb`). Add a `text: bool = True` parameter to `from_file` so binary loaders can pass `text=False`.

TEST_NODE: tests/test_config.py::test_config_from_file_toml
