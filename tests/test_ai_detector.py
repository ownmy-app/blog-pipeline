"""Tests for the AI content detector."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── Sample content ───────────────────────────────────────────────────────────

AI_LIKE_TEXT = """\
In the ever-evolving landscape of modern software development, leveraging \
cutting-edge technologies has become paramount for organizations seeking to \
streamline their workflows and unlock transformative value.

Furthermore, the robust ecosystem of tools available today empowers developers \
to harness the full potential of their platforms. This holistic approach to \
development facilitates seamless integration across the entire stack.

Moreover, innovative solutions continue to revolutionize how we think about \
scalability. The synergy between frontend and backend technologies creates a \
paradigm shift in how we build applications.

Additionally, it's worth noting that the journey toward comprehensive digital \
transformation requires a multifaceted strategy. Each endeavor builds upon \
the pivotal foundations laid by groundbreaking research.

In conclusion, the proliferation of these indispensable tools underscores \
the vital importance of staying current with the latest developments \u2014 \
particularly in areas where the overarching goal is to foster growth and \
encompass a myriad of use cases.
"""

HUMAN_LIKE_TEXT = """\
We shipped a login page last Tuesday. Took about four hours, including the
OAuth flow. Here's what we did and why.

Our app needed Google and GitHub login. We picked next-auth because it handles
the session cookie stuff and has decent docs. The setup was three files.

First, the API route. Drop a file at pages/api/auth/[...nextauth].ts and
configure your providers. Google wants a client ID and secret from their
console. GitHub is the same deal.

Then we added a SessionProvider wrapper in _app.tsx. That gives every page
access to the user session via useSession(). Simple hook, works everywhere.

The tricky part was the redirect. After login, Google sends you to a callback
URL. If that URL doesn't match what's in the Google console, you get a
cryptic error. We burned an hour on this. Pro tip: check trailing slashes.

Testing was manual. Click the button. Log in. Check the session cookie shows
up in dev tools. Log out. Try again with GitHub. Done.

Total cost: zero. next-auth is free. Google and GitHub OAuth is free. We
added rate limiting on the API route just in case. That's another story.
"""


class TestScoreAi:
    """Tests for the composite score_ai() function."""

    def test_ai_text_scores_high(self):
        from blog_pipeline.ai_detector import score_ai
        result = score_ai(AI_LIKE_TEXT)
        assert result["ai_score"] > 0.25, (
            f"AI-like text should score > 0.25, got {result['ai_score']}"
        )

    def test_human_text_scores_low(self):
        from blog_pipeline.ai_detector import score_ai
        result = score_ai(HUMAN_LIKE_TEXT)
        assert result["ai_score"] < 0.4, (
            f"Human-like text should score < 0.4, got {result['ai_score']}"
        )

    def test_returns_expected_keys(self):
        from blog_pipeline.ai_detector import score_ai
        result = score_ai(AI_LIKE_TEXT)
        assert "ai_score" in result
        assert "breakdown" in result
        assert "flags" in result

    def test_score_range(self):
        from blog_pipeline.ai_detector import score_ai
        result = score_ai(AI_LIKE_TEXT)
        assert 0.0 <= result["ai_score"] <= 1.0

    def test_ai_text_has_flags(self):
        from blog_pipeline.ai_detector import score_ai
        result = score_ai(AI_LIKE_TEXT)
        assert len(result["flags"]) > 0

    def test_human_text_has_few_flags(self):
        from blog_pipeline.ai_detector import score_ai
        result = score_ai(HUMAN_LIKE_TEXT)
        # Human text should have very few or no flags
        assert len(result["flags"]) <= 2

    def test_breakdown_has_all_heuristics(self):
        from blog_pipeline.ai_detector import score_ai
        result = score_ai(AI_LIKE_TEXT)
        expected = [
            "banned_word_density",
            "sentence_uniformity",
            "paragraph_opening_variety",
            "passive_voice_ratio",
            "sentence_length_variance",
            "em_dash_density",
            "exclamation_density",
        ]
        for key in expected:
            assert key in result["breakdown"], f"Missing breakdown key: {key}"

    def test_weights_sum_to_one(self):
        from blog_pipeline.ai_detector import _WEIGHTS
        total = sum(_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_empty_text(self):
        from blog_pipeline.ai_detector import score_ai
        result = score_ai("")
        assert result["ai_score"] == 0.0


class TestIndividualHeuristics:
    """Tests for individual heuristic functions."""

    def test_banned_word_density_high(self):
        from blog_pipeline.ai_detector import _banned_word_density
        text = "We leverage synergies to streamline robust solutions and unlock transformative value."
        score = _banned_word_density(text)
        assert score > 0.5

    def test_banned_word_density_clean(self):
        from blog_pipeline.ai_detector import _banned_word_density
        text = "We built a login page and deployed it to production last week."
        score = _banned_word_density(text)
        assert score < 0.2

    def test_em_dash_density_high(self):
        from blog_pipeline.ai_detector import _em_dash_density
        text = "This is great \u2014 really great \u2014 the best \u2014 no question."
        score = _em_dash_density(text)
        assert score > 0.5

    def test_em_dash_density_zero(self):
        from blog_pipeline.ai_detector import _em_dash_density
        text = "This is a clean sentence. No em-dashes here. Just periods."
        score = _em_dash_density(text)
        assert score == 0.0

    def test_exclamation_density_high(self):
        from blog_pipeline.ai_detector import _exclamation_density
        text = "Amazing! Incredible! Wow! This is great! So exciting!"
        score = _exclamation_density(text)
        assert score > 0.5

    def test_exclamation_density_low(self):
        from blog_pipeline.ai_detector import _exclamation_density
        text = "This works. Nothing special. Just code."
        score = _exclamation_density(text)
        assert score == 0.0

    def test_paragraph_opening_variety_repetitive(self):
        from blog_pipeline.ai_detector import _paragraph_opening_variety
        text = (
            "The system is truly great and handles all our needs perfectly well.\n\n"
            "The system handles load well and scales to millions of users easily.\n\n"
            "The system scales horizontally across multiple regions and datacenters.\n\n"
            "The system rocks because it was designed with reliability in mind always."
        )
        score = _paragraph_opening_variety(text)
        assert score > 0.5

    def test_passive_voice_detection(self):
        from blog_pipeline.ai_detector import _passive_voice_ratio
        text = (
            "The code was written by the team. "
            "The tests were run automatically. "
            "The results were analyzed carefully. "
            "The report was generated daily. "
            "The data was processed overnight."
        )
        score = _passive_voice_ratio(text)
        assert score > 0.3
