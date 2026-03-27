"""Tests for the LLM abstraction layer."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_get_provider_default():
    """Default provider should be anthropic."""
    from blog_pipeline.llm import _get_provider
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LLM_PROVIDER", None)
        assert _get_provider() == "anthropic"


def test_get_provider_from_env():
    """LLM_PROVIDER env var should be respected."""
    from blog_pipeline.llm import _get_provider
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
        assert _get_provider() == "openai"


def test_get_provider_case_insensitive():
    """Provider name should be lowercased."""
    from blog_pipeline.llm import _get_provider
    with patch.dict(os.environ, {"LLM_PROVIDER": "  OpenAI  "}):
        assert _get_provider() == "openai"


def test_get_model_default_anthropic():
    """Default model for anthropic should be claude-opus-4-5."""
    from blog_pipeline.llm import _get_model
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LLM_MODEL", None)
        os.environ.pop("CLAUDE_MODEL", None)
        assert _get_model("anthropic") == "claude-opus-4-5"


def test_get_model_explicit():
    """LLM_MODEL env var should override default."""
    from blog_pipeline.llm import _get_model
    with patch.dict(os.environ, {"LLM_MODEL": "claude-3-haiku-20240307"}):
        assert _get_model("anthropic") == "claude-3-haiku-20240307"


def test_get_model_legacy_claude():
    """CLAUDE_MODEL should be used as fallback for anthropic."""
    from blog_pipeline.llm import _get_model
    with patch.dict(os.environ, {"CLAUDE_MODEL": "claude-sonnet-4-20250514"}, clear=False):
        os.environ.pop("LLM_MODEL", None)
        assert _get_model("anthropic") == "claude-sonnet-4-20250514"


def test_get_model_default_openai():
    """Default model for openai should be gpt-4o."""
    from blog_pipeline.llm import _get_model
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LLM_MODEL", None)
        assert _get_model("openai") == "gpt-4o"


def test_ask_llm_unknown_provider():
    """ask_llm should raise ValueError for unknown providers."""
    from blog_pipeline.llm import ask_llm
    with patch.dict(os.environ, {"LLM_PROVIDER": "grok"}):
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            ask_llm("test prompt")


def test_ask_llm_routes_to_anthropic():
    """ask_llm should route to _ask_anthropic when provider is anthropic."""
    from blog_pipeline import llm

    mock_fn = MagicMock(return_value="test response")
    with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}):
        with patch.dict(llm._PROVIDERS, {"anthropic": mock_fn}):
            result = llm.ask_llm("hello", system="sys", max_tokens=100)
            mock_fn.assert_called_once_with("hello", system="sys", max_tokens=100)
            assert result == "test response"


def test_ask_llm_routes_to_openai():
    """ask_llm should route to _ask_openai when provider is openai."""
    from blog_pipeline import llm

    mock_fn = MagicMock(return_value="openai response")
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
        with patch.dict(llm._PROVIDERS, {"openai": mock_fn}):
            result = llm.ask_llm("hello")
            mock_fn.assert_called_once()
            assert result == "openai response"


def test_ask_llm_routes_to_litellm():
    """ask_llm should route to _ask_litellm when provider is litellm."""
    from blog_pipeline import llm

    mock_fn = MagicMock(return_value="litellm response")
    with patch.dict(os.environ, {"LLM_PROVIDER": "litellm"}):
        with patch.dict(llm._PROVIDERS, {"litellm": mock_fn}):
            result = llm.ask_llm("hello")
            mock_fn.assert_called_once()
            assert result == "litellm response"


def test_ask_anthropic_missing_key():
    """_ask_anthropic should raise RuntimeError if ANTHROPIC_API_KEY is not set."""
    from blog_pipeline.llm import _ask_anthropic
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            _ask_anthropic("test")


def test_ask_openai_missing_key():
    """_ask_openai should raise RuntimeError if OPENAI_API_KEY is not set."""
    from blog_pipeline.llm import _ask_openai
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
        with pytest.raises((RuntimeError, ImportError)):
            _ask_openai("test")


def test_ask_anthropic_with_mock_sdk():
    """_ask_anthropic should call the anthropic SDK correctly."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="response text")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    mock_anthropic_mod = MagicMock()
    mock_anthropic_mod.Anthropic.return_value = mock_client

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        with patch.dict(sys.modules, {"anthropic": mock_anthropic_mod}):
            # Re-import to pick up the mocked module
            from blog_pipeline.llm import _ask_anthropic
            result = _ask_anthropic("test prompt", system="be helpful", max_tokens=1000)
            assert result == "response text"
            mock_client.messages.create.assert_called_once()
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"] == "be helpful"
            assert call_kwargs["max_tokens"] == 1000
