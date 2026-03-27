"""
WordPress backend — uses the WP REST API (``wp-json/wp/v2/posts``).

Required env vars:
    WP_URL            Base URL of the WP site, e.g. https://myblog.com
    WP_USER           WordPress username with edit_posts capability
    WP_APP_PASSWORD   Application password (generate in WP admin)

Uses urllib with Basic auth (no extra deps).
"""

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from .base import BlogBackend


class WordPressBackend(BlogBackend):
    """Push/pull blog posts via the WordPress REST API."""

    def __init__(self):
        self._base = os.environ.get("WP_URL", "").rstrip("/")
        self._user = os.environ.get("WP_USER", "")
        self._password = os.environ.get("WP_APP_PASSWORD", "")

        if not self._base:
            raise RuntimeError("WP_URL is not set. See .env.example.")
        if not self._user or not self._password:
            raise RuntimeError(
                "WP_USER and WP_APP_PASSWORD are required for the wordpress backend."
            )

    def _auth_header(self) -> str:
        cred = f"{self._user}:{self._password}"
        return "Basic " + base64.b64encode(cred.encode()).decode()

    def _request(self, method: str, endpoint: str, body=None, params=None) -> Any:
        url = f"{self._base}/wp-json/wp/v2/{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": self._auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode()
            return {"error": err_body, "status": exc.code}

    # -- field mapping ---------------------------------------------------

    @staticmethod
    def _to_wp(post: Dict[str, Any]) -> Dict[str, Any]:
        """Map our standard post dict to WP REST API fields."""
        status = "publish" if post.get("published", True) else "draft"
        wp = {
            "title": post.get("title", ""),
            "content": post.get("content", ""),
            "status": status,
        }
        # Tags and categories are IDs in WP; pass as tag names via ``tags`` needs
        # the tag to exist.  We embed keywords in excerpt for simplicity.
        keywords = post.get("seo_keywords", [])
        if keywords:
            wp["excerpt"] = ", ".join(keywords)
        return wp

    @staticmethod
    def _from_wp(wp: Dict[str, Any]) -> Dict[str, Any]:
        """Map WP REST response to standard post dict."""
        title_obj = wp.get("title", {})
        content_obj = wp.get("content", {})
        return {
            "title": title_obj.get("rendered", "") if isinstance(title_obj, dict) else str(title_obj),
            "content": content_obj.get("rendered", "") if isinstance(content_obj, dict) else str(content_obj),
            "published": wp.get("status") == "publish",
            "created_at": wp.get("date", ""),
            "wp_id": wp.get("id"),
        }

    # -- public API ------------------------------------------------------

    def fetch_titles(self, limit: int = 500) -> List[str]:
        per_page = min(limit, 100)
        titles: List[str] = []
        page = 1
        while len(titles) < limit:
            resp = self._request("GET", "posts", params={
                "per_page": per_page,
                "page": page,
                "status": "publish,draft",
                "_fields": "title",
            })
            if not isinstance(resp, list) or not resp:
                break
            for item in resp:
                t = item.get("title", {})
                rendered = t.get("rendered", "") if isinstance(t, dict) else str(t)
                if rendered:
                    titles.append(rendered)
            if len(resp) < per_page:
                break
            page += 1
        return titles[:limit]

    def push_post(self, post: Dict[str, Any]) -> bool:
        wp_data = self._to_wp(post)
        result = self._request("POST", "posts", body=wp_data)
        return "error" not in result and isinstance(result, dict) and "id" in result

    def unpublish(self, title: str) -> bool:
        # Find the post first
        resp = self._request("GET", "posts", params={
            "search": title,
            "status": "publish,draft",
            "per_page": 5,
        })
        if not isinstance(resp, list):
            return False
        for item in resp:
            t = item.get("title", {})
            rendered = t.get("rendered", "") if isinstance(t, dict) else str(t)
            if rendered.strip().lower() == title.strip().lower():
                wp_id = item["id"]
                result = self._request("POST", f"posts/{wp_id}", body={"status": "draft"})
                return "error" not in result
        return False

    def list_posts(self, published_only: bool = False) -> List[Dict[str, Any]]:
        status = "publish" if published_only else "publish,draft"
        results: List[Dict[str, Any]] = []
        page = 1
        while True:
            resp = self._request("GET", "posts", params={
                "per_page": 100,
                "page": page,
                "status": status,
            })
            if not isinstance(resp, list) or not resp:
                break
            results.extend(self._from_wp(item) for item in resp)
            if len(resp) < 100:
                break
            page += 1
        return results
