import pytest
import tomllib
import flask
from pathlib import Path

def test_config_from_file_toml(tmp_path):
    toml_file = tmp_path / "config.toml"
    toml_file.write_bytes(b'TEST_KEY = "foo"\nSECRET_KEY = "config"\n')

    conf = flask.Config(root_path=str(tmp_path))
    conf.from_file(str(toml_file), tomllib.load, text=False)
    assert conf["TEST_KEY"] == "foo"
    assert conf["SECRET_KEY"] == "config"
