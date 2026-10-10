import json
import os
from unittest.mock import MagicMock, patch
import pytest

from src.fixloop import model

def test_parse_action_response_valid():
    raw = '{"tool": "read_file", "args": {"path": "src/cache.py", "start": 1, "end": 20}}'
    act = model.parse_action_response(raw, usage={"tokens": 42, "cost_usd": 0.001})
    assert act.tool == "read_file"
    assert act.args == {"path": "src/cache.py", "start": 1, "end": 20}
    assert act.usage["tokens"] == 42
    assert act.usage["cost_usd"] == 0.001

def test_parse_action_response_code_fence():
    raw = '```json\n{"tool": "edit_file", "args": {"path": "src/cache.py", "old": "x", "new": "y"}}\n```'
    act = model.parse_action_response(raw)
    assert act.tool == "edit_file"
    assert act.args["old"] == "x"

def test_parse_action_response_invalid_json():
    with pytest.raises(model.ModelError) as exc_info:
        model.parse_action_response("I will fix this bug for you.")
    assert "invalid_json" in str(exc_info.value)

def test_parse_action_response_missing_keys():
    with pytest.raises(model.ModelError) as exc_info:
        model.parse_action_response('{"status": "ok"}')
    assert "missing_tool_or_args" in str(exc_info.value)

def test_compute_cost(monkeypatch):
    # When pricing environment variables are absent -> 0.0
    monkeypatch.delenv("FIXLOOP_PRICE_IN_PER_MTOK", raising=False)
    monkeypatch.delenv("FIXLOOP_PRICE_OUT_PER_MTOK", raising=False)
    assert model.compute_cost(1000, 500) == 0.0

    # When pricing is specified: e.g. $2.50 per MTok input, $10.00 per MTok output
    monkeypatch.setenv("FIXLOOP_PRICE_IN_PER_MTOK", "2.50")
    monkeypatch.setenv("FIXLOOP_PRICE_OUT_PER_MTOK", "10.00")
    cost = model.compute_cost(1_000_000, 500_000)
    assert cost == 7.5

def test_get_adapter_missing_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.delenv("FIXLOOP_MODEL", raising=False)
    with pytest.raises(ValueError) as exc:
        model.get_adapter("openai")
    assert "OPENAI_API_KEY or LITELLM_API_KEY must be set" in str(exc.value)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key")
    with pytest.raises(ValueError) as exc:
        model.get_adapter("openai")
    assert "FIXLOOP_MODEL must be set" in str(exc.value)

def test_openai_adapter_mocked_completion(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key")
    monkeypatch.setenv("FIXLOOP_MODEL", "gpt-4o")
    monkeypatch.setenv("FIXLOOP_PRICE_IN_PER_MTOK", "2.50")
    monkeypatch.setenv("FIXLOOP_PRICE_OUT_PER_MTOK", "10.00")

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "tool": "read_file",
        "args": {"path": "src/cache.py", "start": 1, "end": 30}
    })
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 1000
    mock_usage.completion_tokens = 200
    mock_usage.total_tokens = 1200

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        adapter = model.get_adapter("openai", temperature=0.2)
        assert isinstance(adapter, model.OpenAIAdapter)
        assert adapter.temperature == 0.2

        view = {"test_node": "tests/test_cache.py::test_compute_failure_contract"}
        action = adapter.next_action(view)

        assert action.tool == "read_file"
        assert action.args["path"] == "src/cache.py"
        assert action.usage["tokens"] == 1200
        assert action.usage["cost_usd"] > 0.0

def test_openai_adapter_transport_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key")
    monkeypatch.setenv("FIXLOOP_MODEL", "gpt-4o")

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("Connection timeout")

    with patch("openai.OpenAI", return_value=mock_client):
        adapter = model.get_adapter("openai")
        with pytest.raises(model.ModelError) as exc:
            adapter.next_action({"view": {}})
        assert "openai_transport_error" in str(exc.value)
