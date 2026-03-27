"""
PostgreSQL backend — uses psycopg2 to store posts in a ``blog_posts`` table.

Required env var:
    POSTGRES_DSN   e.g. postgresql://user:pass@host:5432/dbname

The table is created automatically on first use if it does not exist.
"""

import json
import os
from typing import Any, Dict, List

from .base import BlogBackend

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS blog_posts (
    id            SERIAL PRIMARY KEY,
    title         TEXT UNIQUE NOT NULL,
    content       TEXT NOT NULL DEFAULT '',
    author        TEXT NOT NULL DEFAULT '',
    author_title  TEXT NOT NULL DEFAULT '',
    author_image  TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT '',
    tags          JSONB NOT NULL DEFAULT '[]',
    seo_keywords  JSONB NOT NULL DEFAULT '[]',
    cover_image   TEXT NOT NULL DEFAULT '',
    published     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class PostgresBackend(BlogBackend):
    """Read/write blog posts in PostgreSQL via psycopg2."""

    def __init__(self):
        try:
            import psycopg2  # noqa: F401
        except ImportError:
            raise ImportError(
                "psycopg2 is not installed. "
                "Run: pip install 'blog-pipeline[postgres]'"
            )

        dsn = os.environ.get("POSTGRES_DSN", "")
        if not dsn:
            raise RuntimeError("POSTGRES_DSN is not set. See .env.example.")

        self._dsn = dsn
        self._ensure_table()

    def _connect(self):
        import psycopg2
        return psycopg2.connect(self._dsn)

    def _ensure_table(self):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(_CREATE_TABLE)
            conn.commit()
        finally:
            conn.close()

    # -- public API ------------------------------------------------------

    def fetch_titles(self, limit: int = 500) -> List[str]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT title FROM blog_posts ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def push_post(self, post: Dict[str, Any]) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO blog_posts
                        (title, content, author, author_title, author_image,
                         category, tags, seo_keywords, cover_image, published, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (title) DO UPDATE SET
                        content      = EXCLUDED.content,
                        author       = EXCLUDED.author,
                        author_title = EXCLUDED.author_title,
                        author_image = EXCLUDED.author_image,
                        category     = EXCLUDED.category,
                        tags         = EXCLUDED.tags,
                        seo_keywords = EXCLUDED.seo_keywords,
                        cover_image  = EXCLUDED.cover_image,
                        published    = EXCLUDED.published
                    """,
                    (
                        post.get("title", ""),
                        post.get("content", ""),
                        post.get("author", ""),
                        post.get("author_title", ""),
                        post.get("author_image", ""),
                        post.get("category", ""),
                        json.dumps(post.get("tags", [])),
                        json.dumps(post.get("seo_keywords", [])),
                        post.get("cover_image", ""),
                        post.get("published", True),
                        post.get("created_at", None),
                    ),
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def unpublish(self, title: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE blog_posts SET published = FALSE WHERE title = %s",
                    (title,),
                )
                affected = cur.rowcount
            conn.commit()
            return affected > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def list_posts(self, published_only: bool = False) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                q = "SELECT title, content, author, author_title, author_image, category, tags, seo_keywords, cover_image, published, created_at FROM blog_posts"
                if published_only:
                    q += " WHERE published = TRUE"
                q += " ORDER BY created_at DESC"
                cur.execute(q)
                cols = [
                    "title", "content", "author", "author_title", "author_image",
                    "category", "tags", "seo_keywords", "cover_image", "published",
                    "created_at",
                ]
                rows = []
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    # created_at may be datetime; stringify
                    if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                        d["created_at"] = d["created_at"].isoformat()
                    rows.append(d)
                return rows
        finally:
            conn.close()
