"""
Supabase backend — talks to the Supabase REST API via urllib (no extra deps).

Required env vars:
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    SUPABASE_BLOGS_TABLE  (default: blogs)
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from .base import BlogBackend


class SupabaseBackend(BlogBackend):
    """Store and retrieve blog posts from a Supabase PostgREST table."""

    def __init__(self):
        from ..config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_TABLE

        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY are required for the "
                "supabase backend. See .env.example."
            )
        self._url = SUPABASE_URL.rstrip("/")
        self._key = SUPABASE_KEY
        self._table = SUPABASE_TABLE

    # -- internal -------------------------------------------------------

    def _request(self, method: str, path: str, body=None, headers_extra=None) -> Any:
        url = f"{self._url}/rest/v1/{path}"
        data = json.dumps(body).encode() if body else None
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        if headers_extra:
            headers.update(headers_extra)
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            return {"error": exc.read().decode()}

    # -- public API -----------------------------------------------------

    def fetch_titles(self, limit: int = 500) -> List[str]:
        rows = self._request("GET", f"{self._table}?select=title&limit={limit}")
        if isinstance(rows, list):
            return [r.get("title", "") for r in rows if r.get("title")]
        return []

    def push_post(self, post: Dict[str, Any]) -> bool:
        result = self._request("POST", self._table, post)
        return "error" not in result

    def unpublish(self, title: str) -> bool:
        encoded = urllib.parse.quote(f"eq.{title}")
        path = f"{self._table}?title={encoded}"
        result = self._request("PATCH", path, {"published": False})
        return "error" not in result if isinstance(result, dict) else True

    def list_posts(self, published_only: bool = False) -> List[Dict[str, Any]]:
        qs = f"{self._table}?select=*&limit=1000"
        if published_only:
            qs += "&published=eq.true"
        rows = self._request("GET", qs)
        if isinstance(rows, list):
            return rows
        return []
