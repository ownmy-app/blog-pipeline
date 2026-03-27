"""
Contentful backend — uses the Contentful Management API via urllib.

Required env vars:
    CONTENTFUL_SPACE_ID
    CONTENTFUL_MGMT_TOKEN      Management API personal access token
    CONTENTFUL_ENVIRONMENT     (default: master)

Expects a content type ``blogPost`` with fields:
    title (Symbol), content (Text), author (Symbol), category (Symbol),
    tags (Array of Symbols), seoKeywords (Array of Symbols),
    coverImage (Symbol/URL), published (Boolean).

Posts are created as entries and optionally published.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .base import BlogBackend

_API_BASE = "https://api.contentful.com"
_CONTENT_TYPE = "blogPost"


class ContentfulBackend(BlogBackend):
    """Store blog posts in Contentful as ``blogPost`` entries."""

    def __init__(self):
        self._space = os.environ.get("CONTENTFUL_SPACE_ID", "")
        self._token = os.environ.get("CONTENTFUL_MGMT_TOKEN", "")
        self._env = os.environ.get("CONTENTFUL_ENVIRONMENT", "master")

        if not self._space:
            raise RuntimeError("CONTENTFUL_SPACE_ID is not set. See .env.example.")
        if not self._token:
            raise RuntimeError("CONTENTFUL_MGMT_TOKEN is not set. See .env.example.")

    @property
    def _env_url(self) -> str:
        return f"{_API_BASE}/spaces/{self._space}/environments/{self._env}"

    def _request(self, method: str, path: str, body=None, headers_extra=None) -> Any:
        url = f"{self._env_url}/{path}"
        data = json.dumps(body).encode() if body else None
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/vnd.contentful.management.v1+json",
        }
        if headers_extra:
            headers.update(headers_extra)
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            return {"error": exc.read().decode(), "status": exc.code}

    # -- field mapping ---------------------------------------------------

    @staticmethod
    def _to_fields(post: Dict[str, Any], locale: str = "en-US") -> Dict[str, Any]:
        """Map standard post dict to Contentful entry fields."""
        fields: Dict[str, Any] = {}
        simple_map = {
            "title": "title",
            "content": "content",
            "author": "author",
            "category": "category",
            "cover_image": "coverImage",
        }
        for src, dst in simple_map.items():
            val = post.get(src, "")
            if val:
                fields[dst] = {locale: val}

        # Array fields
        for src, dst in [("tags", "tags"), ("seo_keywords", "seoKeywords")]:
            arr = post.get(src, [])
            if arr:
                fields[dst] = {locale: arr}

        # Boolean
        fields["published"] = {locale: post.get("published", True)}

        return fields

    @staticmethod
    def _from_entry(entry: Dict[str, Any], locale: str = "en-US") -> Dict[str, Any]:
        """Extract standard post dict from a Contentful entry."""
        fields = entry.get("fields", {})

        def _get(name, default=""):
            f = fields.get(name, {})
            return f.get(locale, default)

        return {
            "title": _get("title"),
            "content": _get("content"),
            "author": _get("author"),
            "category": _get("category"),
            "tags": _get("tags", []),
            "seo_keywords": _get("seoKeywords", []),
            "cover_image": _get("coverImage"),
            "published": _get("published", True),
            "created_at": entry.get("sys", {}).get("createdAt", ""),
            "contentful_id": entry.get("sys", {}).get("id", ""),
        }

    # -- public API ------------------------------------------------------

    def fetch_titles(self, limit: int = 500) -> List[str]:
        resp = self._request(
            "GET",
            f"entries?content_type={_CONTENT_TYPE}&select=fields.title&limit={min(limit, 1000)}",
        )
        if "error" in resp:
            return []
        titles: List[str] = []
        for item in resp.get("items", []):
            t = item.get("fields", {}).get("title", {}).get("en-US", "")
            if t:
                titles.append(t)
        return titles[:limit]

    def push_post(self, post: Dict[str, Any]) -> bool:
        fields = self._to_fields(post)
        body = {"fields": fields}
        result = self._request(
            "POST",
            "entries",
            body=body,
            headers_extra={"X-Contentful-Content-Type": _CONTENT_TYPE},
        )
        if "error" in result:
            return False

        # Optionally publish the entry immediately
        entry_id = result.get("sys", {}).get("id")
        version = result.get("sys", {}).get("version", 1)
        if entry_id and post.get("published", True):
            self._request(
                "PUT",
                f"entries/{entry_id}/published",
                headers_extra={"X-Contentful-Version": str(version)},
            )
        return True

    def unpublish(self, title: str) -> bool:
        # Find entry by title
        resp = self._request(
            "GET",
            f"entries?content_type={_CONTENT_TYPE}&fields.title='{title}'&limit=1",
        )
        items = resp.get("items", [])
        if not items:
            return False
        entry = items[0]
        entry_id = entry.get("sys", {}).get("id")
        if not entry_id:
            return False
        result = self._request("DELETE", f"entries/{entry_id}/published")
        return "error" not in result

    def list_posts(self, published_only: bool = False) -> List[Dict[str, Any]]:
        posts: List[Dict[str, Any]] = []
        skip = 0
        limit = 100
        while True:
            resp = self._request(
                "GET",
                f"entries?content_type={_CONTENT_TYPE}&limit={limit}&skip={skip}",
            )
            if "error" in resp:
                break
            items = resp.get("items", [])
            if not items:
                break
            for entry in items:
                p = self._from_entry(entry)
                if published_only and not p.get("published", True):
                    continue
                posts.append(p)
            total = resp.get("total", 0)
            skip += limit
            if skip >= total:
                break
        return posts
