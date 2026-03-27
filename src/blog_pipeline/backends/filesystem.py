"""
Filesystem backend — stores posts as ``<slug>.md`` + ``_metadata.json`` sidecar.

Always available, zero external deps.

Reads ``BLOGS_DIR`` from config (default: ``./blogs``).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .base import BlogBackend


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]


class FilesystemBackend(BlogBackend):
    """Read/write blog posts as local markdown files with JSON sidecars."""

    def __init__(self):
        from ..config import BLOGS_DIR

        self._dir = BLOGS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self._dir / "_metadata.json"

    # -- metadata store --------------------------------------------------

    def _load_meta(self) -> Dict[str, Dict[str, Any]]:
        if self._meta_path.exists():
            try:
                return json.loads(self._meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_meta(self, meta: Dict[str, Dict[str, Any]]) -> None:
        self._meta_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- public API ------------------------------------------------------

    def fetch_titles(self, limit: int = 500) -> List[str]:
        meta = self._load_meta()
        titles = list(meta.keys())
        # Also pick up .md files that might not be in metadata yet
        for md in sorted(self._dir.glob("*.md")):
            if md.name.startswith("_"):
                continue
            inferred = md.stem.replace("-", " ").title()
            if inferred not in titles:
                titles.append(inferred)
        return titles[:limit]

    def push_post(self, post: Dict[str, Any]) -> bool:
        title = post.get("title", "untitled")
        slug = _slugify(title)
        md_path = self._dir / f"{slug}.md"

        # Write markdown
        content = post.get("content", "")
        md_path.write_text(content, encoding="utf-8")

        # Update metadata sidecar
        meta = self._load_meta()
        entry = {k: v for k, v in post.items() if k != "content"}
        entry.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        entry["slug"] = slug
        entry["file"] = md_path.name
        meta[title] = entry
        self._save_meta(meta)
        return True

    def unpublish(self, title: str) -> bool:
        meta = self._load_meta()
        if title in meta:
            meta[title]["published"] = False
            self._save_meta(meta)
            return True
        # Try case-insensitive match
        for key in meta:
            if key.lower() == title.lower():
                meta[key]["published"] = False
                self._save_meta(meta)
                return True
        return False

    def list_posts(self, published_only: bool = False) -> List[Dict[str, Any]]:
        meta = self._load_meta()
        results: List[Dict[str, Any]] = []
        for title, entry in meta.items():
            if published_only and not entry.get("published", True):
                continue
            slug = entry.get("slug", _slugify(title))
            md_path = self._dir / f"{slug}.md"
            content = ""
            if md_path.exists():
                content = md_path.read_text(encoding="utf-8")
            results.append({**entry, "title": title, "content": content})
        return results
