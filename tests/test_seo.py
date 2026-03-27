"""Tests for the SEO analysis module."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── Sample content ───────────────────────────────────────────────────────────

GOOD_POST = """\
# How to Deploy a Python App to Production

Getting your Python app from laptop to production doesn't have to be painful.
Here's what actually works, based on shipping dozens of services over the past year.

## Choose Your deploy Target

You've got three main options: a VPS, a container platform, or a serverless function.
Each has trade-offs. VPS gives you full control but means you handle updates.
Container platforms like Fly.io or Railway handle scaling but abstract away the OS.
Serverless works great for APIs but can surprise you with cold starts.

## Set Up Your CI Pipeline

Before anything touches production, you need automated tests running on every push.
GitHub Actions is the simplest way to get started. Add a workflow file and you're done.

```yaml
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest
```

## Configure Your deploy Environment

Environment variables are the right way to handle secrets in production.
Don't hardcode database credentials. Use a .env file locally and your platform's
secret management for deploy environments.

## Monitor After You deploy

Shipping is only half the battle. You need to know when things break.
Set up basic health checks, error tracking, and log aggregation from day one.
Sentry and Datadog both have generous free tiers.

The best deploy setup is one you actually maintain. Start simple, add complexity
only when the pain justifies it.
"""

SHORT_POST = "This is too short to be a real blog post."

NO_HEADINGS_POST = """\
This is a blog post without any headings at all. It talks about Python deployment.
You should use CI pipelines. Environment variables are important.
Monitoring matters. Start simple and iterate.
"""


class TestCalculateReadability:
    """Tests for calculate_readability()."""

    def test_returns_expected_keys(self):
        from blog_pipeline.seo import calculate_readability
        result = calculate_readability(GOOD_POST)
        assert "flesch_reading_ease" in result
        assert "flesch_kincaid_grade" in result
        assert "total_words" in result
        assert "total_sentences" in result
        assert "avg_words_per_sentence" in result

    def test_reasonable_grade_for_tech_content(self):
        from blog_pipeline.seo import calculate_readability
        result = calculate_readability(GOOD_POST)
        # Tech content should be between grade 5-16
        assert 3 <= result["flesch_kincaid_grade"] <= 18

    def test_word_count_positive(self):
        from blog_pipeline.seo import calculate_readability
        result = calculate_readability(GOOD_POST)
        assert result["total_words"] > 100

    def test_empty_content(self):
        from blog_pipeline.seo import calculate_readability
        result = calculate_readability("")
        assert result["total_words"] == 0


class TestCheckKeywordDensity:
    """Tests for check_keyword_density()."""

    def test_keyword_present(self):
        from blog_pipeline.seo import check_keyword_density
        density = check_keyword_density(GOOD_POST, "deploy")
        assert density > 0.0

    def test_keyword_absent(self):
        from blog_pipeline.seo import check_keyword_density
        density = check_keyword_density(GOOD_POST, "kubernetes")
        assert density == 0.0

    def test_empty_keyword(self):
        from blog_pipeline.seo import check_keyword_density
        density = check_keyword_density(GOOD_POST, "")
        assert density == 0.0

    def test_case_insensitive(self):
        from blog_pipeline.seo import check_keyword_density
        text = "Python is great. python rocks. PYTHON forever."
        density = check_keyword_density(text, "python")
        assert density > 0


class TestAnalyzeHeadings:
    """Tests for analyze_headings()."""

    def test_counts_h2(self):
        from blog_pipeline.seo import analyze_headings
        result = analyze_headings(GOOD_POST)
        assert result["h2_count"] >= 3

    def test_proper_hierarchy(self):
        from blog_pipeline.seo import analyze_headings
        result = analyze_headings(GOOD_POST)
        assert result["has_proper_hierarchy"] is True

    def test_no_headings(self):
        from blog_pipeline.seo import analyze_headings
        result = analyze_headings(NO_HEADINGS_POST)
        assert result["h2_count"] == 0

    def test_skipped_hierarchy(self):
        from blog_pipeline.seo import analyze_headings
        text = "# Title\n\n#### Skip to H4\n"
        result = analyze_headings(text)
        assert result["has_proper_hierarchy"] is False


class TestAnalyzeLinks:
    """Tests for analyze_links()."""

    def test_internal_links(self):
        from blog_pipeline.seo import analyze_links
        text = "Check out [our guide](/blog/guide) and [another post](/blog/other)."
        result = analyze_links(text)
        assert result["internal_links"] == 2
        assert result["external_links"] == 0

    def test_external_links(self):
        from blog_pipeline.seo import analyze_links
        text = "Visit [GitHub](https://github.com) for more."
        result = analyze_links(text)
        assert result["external_links"] == 1
        assert result["internal_links"] == 0

    def test_mixed_links(self):
        from blog_pipeline.seo import analyze_links
        text = "See [internal](/blog/test) and [external](https://example.com)."
        result = analyze_links(text)
        assert result["total_links"] == 2
        assert result["internal_links"] == 1
        assert result["external_links"] == 1


class TestGenerateMetaDescription:
    """Tests for generate_meta_description()."""

    def test_returns_string(self):
        from blog_pipeline.seo import generate_meta_description
        result = generate_meta_description(GOOD_POST)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_reasonable_length(self):
        from blog_pipeline.seo import generate_meta_description
        result = generate_meta_description(GOOD_POST, "deploy")
        # Should be between 50 and 200 chars
        assert 50 <= len(result) <= 200

    def test_empty_content(self):
        from blog_pipeline.seo import generate_meta_description
        result = generate_meta_description("")
        assert result == ""


class TestScoreSeo:
    """Tests for the composite score_seo()."""

    def test_good_post_scores_well(self):
        from blog_pipeline.seo import score_seo
        result = score_seo(GOOD_POST, primary_keyword="deploy")
        assert result["seo_score"] >= 40  # good post should score decently

    def test_short_post_scores_poorly(self):
        from blog_pipeline.seo import score_seo
        result = score_seo(SHORT_POST)
        assert result["seo_score"] < 50

    def test_returns_breakdown(self):
        from blog_pipeline.seo import score_seo
        result = score_seo(GOOD_POST)
        assert "breakdown" in result
        assert "readability" in result
        assert "headings" in result
        assert "links" in result
        assert "meta_description" in result

    def test_score_range(self):
        from blog_pipeline.seo import score_seo
        result = score_seo(GOOD_POST)
        assert 0 <= result["seo_score"] <= 100

    def test_no_keyword_gives_partial_credit(self):
        from blog_pipeline.seo import score_seo
        result = score_seo(GOOD_POST)
        # Without keyword, should still get some score
        assert result["seo_score"] > 0
        assert result["breakdown"]["keyword_density"]["score"] > 0
