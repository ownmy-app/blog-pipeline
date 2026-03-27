"""Tests for humanizer rules loading, defaults, and check_ai_tells."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestGetDefaultRules:
    """Tests for get_default_rules()."""

    def test_returns_humanizer_rules(self):
        from blog_pipeline.humanizer_rules import get_default_rules, HumanizerRules
        rules = get_default_rules()
        assert isinstance(rules, HumanizerRules)

    def test_has_banned_words(self):
        from blog_pipeline.humanizer_rules import get_default_rules
        rules = get_default_rules()
        assert len(rules.banned_words) >= 50
        assert "leverage" in rules.banned_words
        assert "delve" in rules.banned_words

    def test_has_banned_phrases(self):
        from blog_pipeline.humanizer_rules import get_default_rules
        rules = get_default_rules()
        assert len(rules.banned_phrases) >= 14
        assert "in conclusion" in rules.banned_phrases
        assert "in summary" in rules.banned_phrases

    def test_has_sentence_start_flags(self):
        from blog_pipeline.humanizer_rules import get_default_rules
        rules = get_default_rules()
        assert len(rules.sentence_start_flags) >= 10
        assert "Furthermore," in rules.sentence_start_flags

    def test_defaults(self):
        from blog_pipeline.humanizer_rules import get_default_rules
        rules = get_default_rules()
        assert rules.max_exclamations == 1
        assert rules.require_contractions is True
        assert rules.max_paragraph_repeat_starts == 2

    def test_has_rules_list(self):
        from blog_pipeline.humanizer_rules import get_default_rules
        rules = get_default_rules()
        assert len(rules.rules) >= 10


class TestLoadRules:
    """Tests for load_rules()."""

    def test_load_from_explicit_path(self, tmp_path):
        from blog_pipeline.humanizer_rules import load_rules

        yaml_content = """
banned_words:
  - "custom_word_1"
  - "custom_word_2"
max_exclamations: 3
"""
        yaml_file = tmp_path / "custom_rules.yml"
        yaml_file.write_text(yaml_content)

        rules = load_rules(str(yaml_file))
        assert "custom_word_1" in rules.banned_words
        assert "custom_word_2" in rules.banned_words
        assert rules.max_exclamations == 3

    def test_load_from_env_var(self, tmp_path):
        from blog_pipeline.humanizer_rules import load_rules

        yaml_content = """
banned_words:
  - "env_word"
max_exclamations: 5
"""
        yaml_file = tmp_path / "env_rules.yml"
        yaml_file.write_text(yaml_content)

        with patch.dict(os.environ, {"HUMANIZER_RULES": str(yaml_file)}):
            rules = load_rules()
            assert "env_word" in rules.banned_words
            assert rules.max_exclamations == 5

    def test_falls_back_to_defaults(self):
        from blog_pipeline.humanizer_rules import load_rules

        with patch.dict(os.environ, {"HUMANIZER_RULES": ""}):
            rules = load_rules()
            assert len(rules.banned_words) >= 50

    def test_load_from_package_default_yaml(self):
        """The package ships a default YAML that should load successfully."""
        from blog_pipeline.humanizer_rules import load_rules
        pkg_yaml = Path(__file__).parent.parent / "src" / "blog_pipeline" / "humanizer_rules.default.yml"
        if pkg_yaml.exists():
            rules = load_rules(str(pkg_yaml))
            assert len(rules.banned_words) >= 50
            assert "leverage" in rules.banned_words

    def test_nonexistent_path_falls_back(self):
        from blog_pipeline.humanizer_rules import load_rules
        rules = load_rules("/nonexistent/path/rules.yml")
        # Should fall back to defaults
        assert len(rules.banned_words) >= 50


class TestBuildSystemPrompt:
    """Tests for build_system_prompt()."""

    def test_returns_string(self):
        from blog_pipeline.humanizer_rules import get_default_rules, build_system_prompt
        rules = get_default_rules()
        prompt = build_system_prompt(rules)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_contains_banned_words(self):
        from blog_pipeline.humanizer_rules import get_default_rules, build_system_prompt
        rules = get_default_rules()
        prompt = build_system_prompt(rules)
        assert "leverage" in prompt
        assert "delve" in prompt

    def test_contains_rules(self):
        from blog_pipeline.humanizer_rules import get_default_rules, build_system_prompt
        rules = get_default_rules()
        prompt = build_system_prompt(rules)
        assert "em-dash" in prompt.lower()
        assert "contraction" in prompt.lower()

    def test_substitutes_template_vars(self):
        from blog_pipeline.humanizer_rules import get_default_rules, build_system_prompt
        rules = get_default_rules()
        rules.max_exclamations = 3
        prompt = build_system_prompt(rules)
        assert "3 exclamation mark(s)" in prompt

    def test_contains_banned_phrases(self):
        from blog_pipeline.humanizer_rules import get_default_rules, build_system_prompt
        rules = get_default_rules()
        prompt = build_system_prompt(rules)
        assert "in conclusion" in prompt.lower()


class TestCheckAiTells:
    """Tests for check_ai_tells()."""

    def test_detects_banned_words(self):
        from blog_pipeline.humanizer import check_ai_tells
        text = "This solution leverages synergy to deliver holistic value."
        result = check_ai_tells(text)
        # "synergy", "holistic", and "solution" are banned words
        assert len(result["words"]) >= 2
        assert "holistic" in result["words"]
        assert "synergy" in result["words"]

    def test_detects_banned_phrases(self):
        from blog_pipeline.humanizer import check_ai_tells
        text = "In conclusion, this is a great approach."
        result = check_ai_tells(text)
        assert any("in conclusion" in p.lower() for p in result["phrases"])

    def test_detects_sentence_start_flags(self):
        from blog_pipeline.humanizer import check_ai_tells
        text = "Furthermore, this is important.\nMoreover, it works well."
        result = check_ai_tells(text)
        assert len(result["patterns"]) >= 2

    def test_counts_em_dashes(self):
        from blog_pipeline.humanizer import check_ai_tells
        text = "This is great \u2014 really great \u2014 the best."
        result = check_ai_tells(text)
        assert result["em_dashes"] == 2

    def test_clean_text_has_no_tells(self):
        from blog_pipeline.humanizer import check_ai_tells
        text = "Here's how to build a login page in ten minutes. It's straightforward."
        result = check_ai_tells(text)
        assert len(result["words"]) == 0
        assert len(result["phrases"]) == 0
        assert len(result["patterns"]) == 0
