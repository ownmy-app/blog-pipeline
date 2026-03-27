"""Tests for blog storage backends — filesystem backend end-to-end."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def tmp_blog_dir(tmp_path):
    """Create a temporary directory and patch BLOGS_DIR."""
    blog_dir = tmp_path / "blogs"
    blog_dir.mkdir()
    with patch("blog_pipeline.config.BLOGS_DIR", blog_dir):
        yield blog_dir


def _make_post(title="Test Post", content="# Hello\n\nThis is a test post.", published=True):
    """Helper to create a standard post dict."""
    return {
        "title": title,
        "content": content,
        "author": "Test Author",
        "author_title": "Tester",
        "author_image": "",
        "category": "Tutorial",
        "tags": ["python", "testing"],
        "seo_keywords": ["test", "blog"],
        "cover_image": "",
        "published": published,
        "created_at": "2025-01-01T00:00:00",
    }


class TestFilesystemBackend:
    """End-to-end tests for FilesystemBackend."""

    def test_push_and_fetch_titles(self, tmp_blog_dir):
        from blog_pipeline.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend()
        post = _make_post()

        # Push
        assert backend.push_post(post) is True

        # Fetch titles
        titles = backend.fetch_titles()
        assert "Test Post" in titles

    def test_push_creates_md_file(self, tmp_blog_dir):
        from blog_pipeline.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend()
        post = _make_post(title="My Great Article")
        backend.push_post(post)

        md_files = list(tmp_blog_dir.glob("*.md"))
        assert len(md_files) == 1
        assert "my-great-article" in md_files[0].name
        assert md_files[0].read_text(encoding="utf-8") == post["content"]

    def test_push_creates_metadata(self, tmp_blog_dir):
        from blog_pipeline.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend()
        post = _make_post()
        backend.push_post(post)

        meta_path = tmp_blog_dir / "_metadata.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert "Test Post" in meta
        assert meta["Test Post"]["author"] == "Test Author"

    def test_list_posts(self, tmp_blog_dir):
        from blog_pipeline.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend()
        backend.push_post(_make_post(title="Post One"))
        backend.push_post(_make_post(title="Post Two"))

        posts = backend.list_posts()
        assert len(posts) == 2
        titles = {p["title"] for p in posts}
        assert titles == {"Post One", "Post Two"}

    def test_list_posts_published_only(self, tmp_blog_dir):
        from blog_pipeline.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend()
        backend.push_post(_make_post(title="Published", published=True))
        backend.push_post(_make_post(title="Draft", published=False))

        all_posts = backend.list_posts(published_only=False)
        assert len(all_posts) == 2

        published = backend.list_posts(published_only=True)
        assert len(published) == 1
        assert published[0]["title"] == "Published"

    def test_unpublish(self, tmp_blog_dir):
        from blog_pipeline.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend()
        backend.push_post(_make_post(title="To Unpublish"))

        assert backend.unpublish("To Unpublish") is True

        posts = backend.list_posts(published_only=True)
        assert len(posts) == 0

    def test_unpublish_nonexistent(self, tmp_blog_dir):
        from blog_pipeline.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend()
        assert backend.unpublish("Nonexistent") is False

    def test_fetch_titles_includes_orphan_md(self, tmp_blog_dir):
        """Markdown files without metadata entries should still appear."""
        from blog_pipeline.backends.filesystem import FilesystemBackend

        # Write an orphan md file
        (tmp_blog_dir / "orphan-post.md").write_text("# Orphan")

        backend = FilesystemBackend()
        titles = backend.fetch_titles()
        assert any("Orphan" in t for t in titles)

    def test_fetch_titles_limit(self, tmp_blog_dir):
        from blog_pipeline.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend()
        for i in range(10):
            backend.push_post(_make_post(title=f"Post {i}"))

        titles = backend.fetch_titles(limit=5)
        assert len(titles) == 5

    def test_push_multiple_same_title_overwrites(self, tmp_blog_dir):
        from blog_pipeline.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend()
        backend.push_post(_make_post(title="Same Title", content="Version 1"))
        backend.push_post(_make_post(title="Same Title", content="Version 2"))

        posts = backend.list_posts()
        # Should have 1 post (overwritten)
        same = [p for p in posts if p["title"] == "Same Title"]
        assert len(same) == 1
        assert same[0]["content"] == "Version 2"


class TestGetBackend:
    """Tests for the backend factory."""

    def test_default_is_filesystem(self, tmp_blog_dir):
        from blog_pipeline.backends import get_backend
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BLOG_BACKEND", None)
            backend = get_backend()
            assert backend.__class__.__name__ == "FilesystemBackend"

    def test_explicit_filesystem(self, tmp_blog_dir):
        from blog_pipeline.backends import get_backend
        backend = get_backend("filesystem")
        assert backend.__class__.__name__ == "FilesystemBackend"

    def test_unknown_backend_raises(self):
        from blog_pipeline.backends import get_backend
        with pytest.raises(ValueError, match="Unknown BLOG_BACKEND"):
            get_backend("redis")

    def test_supabase_missing_env_raises(self):
        from blog_pipeline.backends import get_backend
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""}):
            with pytest.raises(RuntimeError, match="SUPABASE_URL"):
                get_backend("supabase")
