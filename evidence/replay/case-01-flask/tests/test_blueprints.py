import pytest
import flask

def test_dotted_name_not_allowed():
    with pytest.raises(ValueError):
        flask.Blueprint("app.ui", __name__)
