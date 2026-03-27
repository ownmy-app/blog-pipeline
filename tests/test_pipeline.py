"""Tests for blog-pipeline — no external APIs required."""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_check_banned_words_flags_corporate_speak():
    from blog_pipeline.humanizer import check_banned_words

    text = "This solution leverages synergies to deliver holistic value."
    hits = check_banned_words(text)
    assert len(hits) > 0, "Should flag corporate buzzwords"


def test_check_banned_words_passes_clean_text():
    from blog_pipeline.humanizer import check_banned_words

    text = "Here is how to build a login page in ten minutes."
    hits = check_banned_words(text)
    assert hits == [], f"Should not flag clean text, got: {hits}"


def test_check_banned_words_flags_em_dash_clusters():
    from blog_pipeline.humanizer import check_banned_words

    text = "We did this \u2014 and that \u2014 and also this \u2014 and more."
    hits = check_banned_words(text)
    # Should flag excessive em-dashes as AI-tell
    em_flag = [h for h in hits if "em-dash" in h.lower() or "\u2014" in h]
    assert len(em_flag) > 0, f"Should flag em-dash clusters, got: {hits}"


def test_humanize_post_returns_string(monkeypatch):
    """humanize_post should return a string (mock the LLM call)."""
    from blog_pipeline.humanizer import humanize_post

    # Mock the LLM call
    monkeypatch.setattr(
        "blog_pipeline.llm.ask_llm",
        lambda prompt, system="", max_tokens=8096: "Clean rewritten content.",
    )

    content = "Hello world. This leverages synergies."
    result = humanize_post(content)
    assert isinstance(result, str)
    assert len(result) > 0


def test_version():
    from blog_pipeline import __version__
    assert __version__ == "0.2.0"


def test_check_ai_tells():
    from blog_pipeline.humanizer import check_ai_tells

    text = "Furthermore, this leverages synergies. In conclusion, it's great."
    result = check_ai_tells(text)
    assert isinstance(result, dict)
    assert "words" in result
    assert "phrases" in result
    assert "patterns" in result


def test_ask_llm_import():
    """ask_llm should be importable."""
    from blog_pipeline.llm import ask_llm
    assert callable(ask_llm)


def test_get_backend_import():
    """get_backend should be importable."""
    from blog_pipeline.backends import get_backend
    assert callable(get_backend)


def test_score_seo_import():
    """score_seo should be importable."""
    from blog_pipeline.seo import score_seo
    assert callable(score_seo)


def test_score_ai_import():
    """score_ai should be importable."""
    from blog_pipeline.ai_detector import score_ai
    assert callable(score_ai)
