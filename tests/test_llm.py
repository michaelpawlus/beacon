"""Tests for LLM integration layer."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from beacon.llm.client import (
    DEFAULT_MODEL,
    LLMResponse,
    generate,
    generate_structured,
    get_client,
)


@pytest.fixture(autouse=True)
def reset_client():
    """Reset the global client before each test."""
    import beacon.llm.client as client_module
    client_module._client = None
    yield
    client_module._client = None


def _mock_response(text="Hello", input_tokens=10, output_tokens=20):
    """Create a mock Anthropic response."""
    response = MagicMock()
    content_block = MagicMock()
    content_block.text = text
    response.content = [content_block]
    response.model = DEFAULT_MODEL
    response.usage = MagicMock()
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


class TestGetClient:
    def test_missing_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                get_client()

    def test_creates_client_with_key(self):
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = MagicMock()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
                client = get_client()
                assert client is not None
                mock_anthropic.Anthropic.assert_called_once_with(api_key="test-key")

    def test_client_is_cached(self):
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = MagicMock()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
                c1 = get_client()
                c2 = get_client()
                assert c1 is c2
                mock_anthropic.Anthropic.assert_called_once()


class TestGenerate:
    @patch("beacon.llm.client.get_client")
    def test_basic_generate(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response("Test output")
        mock_get_client.return_value = mock_client

        result = generate("Test prompt")

        assert isinstance(result, LLMResponse)
        assert result.text == "Test output"
        assert result.input_tokens == 10
        assert result.output_tokens == 20

    @patch("beacon.llm.client.get_client")
    def test_generate_with_system_prompt(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response()
        mock_get_client.return_value = mock_client

        generate("prompt", system="You are helpful")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "You are helpful"

    @patch("beacon.llm.client.get_client")
    def test_generate_without_system_prompt(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response()
        mock_get_client.return_value = mock_client

        generate("prompt")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert "system" not in call_kwargs

    @patch("beacon.llm.client.get_client")
    def test_generate_passes_parameters(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response()
        mock_get_client.return_value = mock_client

        generate("prompt", model="claude-haiku-4-5-20251001", max_tokens=100, temperature=0.5)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["max_tokens"] == 100
        assert call_kwargs["temperature"] == 0.5

    @patch("beacon.llm.client.get_client")
    def test_generate_message_format(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response()
        mock_get_client.return_value = mock_client

        generate("Hello world")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hello world"}]


class TestGenerateStructured:
    @patch("beacon.llm.client.get_client")
    def test_parses_json_response(self, mock_get_client):
        mock_client = MagicMock()
        json_str = json.dumps({"skills": ["Python", "SQL"], "seniority": "senior"})
        mock_client.messages.create.return_value = _mock_response(json_str)
        mock_get_client.return_value = mock_client

        result = generate_structured("Extract skills")
        assert result["skills"] == ["Python", "SQL"]
        assert result["seniority"] == "senior"

    @patch("beacon.llm.client.get_client")
    def test_strips_code_fences(self, mock_get_client):
        mock_client = MagicMock()
        json_str = '```json\n{"key": "value"}\n```'
        mock_client.messages.create.return_value = _mock_response(json_str)
        mock_get_client.return_value = mock_client

        result = generate_structured("prompt")
        assert result["key"] == "value"

    @patch("beacon.llm.client.get_client")
    def test_strips_bare_code_fences(self, mock_get_client):
        mock_client = MagicMock()
        json_str = '```\n{"key": "value"}\n```'
        mock_client.messages.create.return_value = _mock_response(json_str)
        mock_get_client.return_value = mock_client

        result = generate_structured("prompt")
        assert result["key"] == "value"

    @patch("beacon.llm.client.get_client")
    def test_invalid_json_raises(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response("not json at all")
        mock_get_client.return_value = mock_client

        with pytest.raises(json.JSONDecodeError):
            generate_structured("prompt")


class TestPrompts:
    def test_prompts_are_nonempty_strings(self):
        from beacon.llm.prompts import (
            COVER_LETTER_PROMPT,
            COVER_LETTER_SYSTEM_PROMPT,
            REQUIREMENTS_EXTRACTION_PROMPT,
            RESUME_SYSTEM_PROMPT,
            RESUME_TAILOR_PROMPT,
        )
        for prompt in [REQUIREMENTS_EXTRACTION_PROMPT, RESUME_SYSTEM_PROMPT,
                       RESUME_TAILOR_PROMPT, COVER_LETTER_SYSTEM_PROMPT,
                       COVER_LETTER_PROMPT]:
            assert isinstance(prompt, str)
            assert len(prompt) > 50
