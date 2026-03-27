"""Tests for the audit module — score_post and run_audit."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── Sample content ───────────────────────────────────────────────────────────

GOOD_BLOG = """\
# How to Build a REST API with FastAPI

Building a REST API doesn't have to be complicated. FastAPI makes it
straightforward, and you can have something running in under an hour.

## Why FastAPI

FastAPI is built on Starlette and Pydantic. It's fast, it validates input
automatically, and it generates OpenAPI docs for free. If you've used Flask,
the learning curve is small.

## Setting Up Your Project

Start with a virtual environment and install FastAPI plus uvicorn:

```bash
pip install fastapi uvicorn
```

Create a main.py file:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
```

## Adding Routes

Routes in FastAPI use decorators. You define the HTTP method and path,
then write a function. Type hints on parameters give you automatic
validation and documentation.

```python
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float

@app.post("/items")
def create_item(item: Item):
    return {"created": item.name}
```

## Running in Production

Don't use the built-in server in production. Use gunicorn with uvicorn
workers instead. Set the number of workers to 2x your CPU cores plus one.

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

That's it. You've got a production-ready API with automatic validation,
docs, and proper concurrency handling.
"""

WEAK_BLOG = """\
This leverages synergies to deliver holistic value. The seamless ecosystem
facilitates transformative outcomes. Furthermore, the robust solution
empowers organizations to streamline their journey \u2014 unlocking paradigm
shifts \u2014 and revolutionizing how we think about innovation.
"""


class TestScorePost:
    """Tests for score_post()."""

    def test_good_blog_scores_well(self):
        from blog_pipeline.audit import score_post
        result = score_post(GOOD_BLOG)
        assert result["score"] >= 60, (
            f"Good blog should score >= 60, got {result['score']}"
        )

    def test_weak_blog_scores_poorly(self):
        from blog_pipeline.audit import score_post
        result = score_post(WEAK_BLOG)
        assert result["score"] < 60, (
            f"Weak blog should score < 60, got {result['score']}"
        )

    def test_returns_expected_keys(self):
        from blog_pipeline.audit import score_post
        result = score_post(GOOD_BLOG)
        expected_keys = [
            "score", "quality_score", "ai_human_score", "ai_detection_score",
            "ai_flags", "words", "headings_h2", "code_blocks",
            "em_dashes", "sentence_semicolons", "banned_words", "grade",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_grade_assignment(self):
        from blog_pipeline.audit import score_post
        result = score_post(GOOD_BLOG)
        assert result["grade"] in ("A", "B", "C", "F")

    def test_weak_blog_has_banned_words(self):
        from blog_pipeline.audit import score_post
        result = score_post(WEAK_BLOG)
        assert len(result["banned_words"]) > 0

    def test_good_blog_has_headings(self):
        from blog_pipeline.audit import score_post
        result = score_post(GOOD_BLOG)
        assert result["headings_h2"] >= 3

    def test_seo_scoring(self):
        from blog_pipeline.audit import score_post
        result = score_post(GOOD_BLOG, seo=True)
        assert "seo_score" in result
        assert "seo_details" in result
        assert result["seo_score"] >= 0

    def test_score_without_seo(self):
        from blog_pipeline.audit import score_post
        result = score_post(GOOD_BLOG, seo=False)
        assert "seo_score" not in result

    def test_ai_detection_included(self):
        from blog_pipeline.audit import score_post
        result = score_post(WEAK_BLOG)
        assert result["ai_detection_score"] > 0
        assert result["ai_human_score"] < 100


class TestRunAudit:
    """Tests for run_audit()."""

    def test_audits_directory(self, tmp_path):
        from blog_pipeline.audit import run_audit

        # Write test files
        (tmp_path / "good-post.md").write_text(GOOD_BLOG, encoding="utf-8")
        (tmp_path / "weak-post.md").write_text(WEAK_BLOG, encoding="utf-8")

        results = run_audit(tmp_path)
        assert len(results) == 2
        # Should be sorted by score ascending
        assert results[0]["score"] <= results[1]["score"]

    def test_skips_underscore_files(self, tmp_path):
        from blog_pipeline.audit import run_audit

        (tmp_path / "good-post.md").write_text(GOOD_BLOG, encoding="utf-8")
        (tmp_path / "_metadata.json").write_text("{}", encoding="utf-8")
        (tmp_path / "_topics.json").write_text("[]", encoding="utf-8")

        results = run_audit(tmp_path)
        assert len(results) == 1

    def test_includes_file_info(self, tmp_path):
        from blog_pipeline.audit import run_audit

        (tmp_path / "test-post.md").write_text(GOOD_BLOG, encoding="utf-8")

        results = run_audit(tmp_path)
        assert results[0]["file"] == "test-post.md"
        assert "title" in results[0]

    def test_empty_directory(self, tmp_path):
        from blog_pipeline.audit import run_audit

        results = run_audit(tmp_path)
        assert results == []

    def test_with_seo_flag(self, tmp_path):
        from blog_pipeline.audit import run_audit

        (tmp_path / "post.md").write_text(GOOD_BLOG, encoding="utf-8")
        results = run_audit(tmp_path, seo=True)
        assert "seo_score" in results[0]
