"""
Notion backend — creates pages in a Notion database via the Notion API.

Required env vars:
    NOTION_API_KEY         Integration token (starts with ``ntn_`` or ``secret_``)
    NOTION_DATABASE_ID     ID of the target database

Uses urllib (no extra deps). Expects the database to have at least a
``Title`` title-type property, plus optional ``Content``, ``Category``,
``Tags``, ``Published``, ``Author``, ``Cover Image`` properties.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .base import BlogBackend

_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionBackend(BlogBackend):
    """Store blog posts as pages in a Notion database."""

    def __init__(self):
        self._token = os.environ.get("NOTION_API_KEY", "")
        self._db_id = os.environ.get("NOTION_DATABASE_ID", "")

        if not self._token:
            raise RuntimeError("NOTION_API_KEY is not set. See .env.example.")
        if not self._db_id:
            raise RuntimeError("NOTION_DATABASE_ID is not set. See .env.example.")

    def _request(self, method: str, path: str, body=None) -> Any:
        url = f"{_API_BASE}/{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            return {"error": exc.read().decode(), "status": exc.code}

    # -- field mapping ---------------------------------------------------

    def _post_to_properties(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """Build Notion page properties from a standard post dict."""
        props: Dict[str, Any] = {
            "Title": {
                "title": [{"text": {"content": post.get("title", "")}}]
            },
        }
        # Rich text properties
        for key, prop_name in [
            ("author", "Author"),
            ("category", "Category"),
            ("author_title", "Author Title"),
        ]:
            val = post.get(key, "")
            if val:
                props[prop_name] = {
                    "rich_text": [{"text": {"content": val}}]
                }
        # Checkbox
        props["Published"] = {"checkbox": post.get("published", True)}
        # URL
        cover = post.get("cover_image", "")
        if cover:
            props["Cover Image"] = {"url": cover}
        # Multi-select for tags
        tags = post.get("tags", [])
        if tags:
            props["Tags"] = {
                "multi_select": [{"name": t} for t in tags[:10]]
            }
        return props

    def _content_to_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Convert markdown content to Notion blocks (simplified)."""
        blocks: List[Dict[str, Any]] = []
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # Headings
            if line.startswith("### "):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": line[4:].strip()}}]
                    },
                })
                i += 1
                continue
            if line.startswith("## "):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": line[3:].strip()}}]
                    },
                })
                i += 1
                continue
            if line.startswith("# "):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:].strip()}}]
                    },
                })
                i += 1
                continue

            # Code blocks
            if line.startswith("```"):
                lang = line[3:].strip()
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing ```
                code_text = "\n".join(code_lines)
                # Notion limits rich_text content to 2000 chars
                if len(code_text) > 2000:
                    code_text = code_text[:2000]
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": code_text}}],
                        "language": lang if lang else "plain text",
                    },
                })
                continue

            # Regular paragraph
            text = line.strip()
            if text:
                if len(text) > 2000:
                    text = text[:2000]
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": text}}]
                    },
                })
            i += 1

        # Notion API limits to 100 blocks per request
        return blocks[:100]

    @staticmethod
    def _page_to_post(page: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standard post dict from a Notion page object."""
        props = page.get("properties", {})

        def _get_title(p):
            t = p.get("title", [])
            return t[0].get("text", {}).get("content", "") if t else ""

        def _get_rich_text(p):
            rt = p.get("rich_text", [])
            return rt[0].get("text", {}).get("content", "") if rt else ""

        title = _get_title(props.get("Title", {}))
        author = _get_rich_text(props.get("Author", {}))
        category = _get_rich_text(props.get("Category", {}))
        published_prop = props.get("Published", {})
        published = published_prop.get("checkbox", True)
        created_at = page.get("created_time", "")

        return {
            "title": title,
            "content": "",  # full content requires block retrieval
            "author": author,
            "category": category,
            "published": published,
            "created_at": created_at,
            "notion_id": page.get("id", ""),
        }

    # -- public API ------------------------------------------------------

    def fetch_titles(self, limit: int = 500) -> List[str]:
        body = {
            "page_size": min(limit, 100),
            "filter_properties": ["Title"],
        }
        resp = self._request("POST", f"databases/{self._db_id}/query", body)
        if "error" in resp:
            return []
        titles: List[str] = []
        results = resp.get("results", [])
        for page in results:
            props = page.get("properties", {})
            title_prop = props.get("Title", {})
            t = title_prop.get("title", [])
            if t:
                titles.append(t[0].get("text", {}).get("content", ""))
        return titles[:limit]

    def push_post(self, post: Dict[str, Any]) -> bool:
        properties = self._post_to_properties(post)
        children = self._content_to_blocks(post.get("content", ""))
        body: Dict[str, Any] = {
            "parent": {"database_id": self._db_id},
            "properties": properties,
        }
        if children:
            body["children"] = children

        cover_url = post.get("cover_image", "")
        if cover_url:
            body["cover"] = {"type": "external", "external": {"url": cover_url}}

        result = self._request("POST", "pages", body)
        return "id" in result and "error" not in result

    def unpublish(self, title: str) -> bool:
        # Search for the page
        body = {
            "filter": {
                "property": "Title",
                "title": {"equals": title},
            },
            "page_size": 1,
        }
        resp = self._request("POST", f"databases/{self._db_id}/query", body)
        results = resp.get("results", [])
        if not results:
            return False
        page_id = results[0]["id"]
        update = {
            "properties": {
                "Published": {"checkbox": False},
            }
        }
        result = self._request("PATCH", f"pages/{page_id}", update)
        return "error" not in result

    def list_posts(self, published_only: bool = False) -> List[Dict[str, Any]]:
        body: Dict[str, Any] = {"page_size": 100}
        if published_only:
            body["filter"] = {
                "property": "Published",
                "checkbox": {"equals": True},
            }
        posts: List[Dict[str, Any]] = []
        has_more = True
        start_cursor = None
        while has_more:
            if start_cursor:
                body["start_cursor"] = start_cursor
            resp = self._request("POST", f"databases/{self._db_id}/query", body)
            if "error" in resp:
                break
            for page in resp.get("results", []):
                posts.append(self._page_to_post(page))
            has_more = resp.get("has_more", False)
            start_cursor = resp.get("next_cursor")
        return posts
