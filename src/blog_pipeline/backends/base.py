"""
Abstract base class for blog storage backends.

Every backend must implement these four methods. The ``post`` dict
has the following shape::

    {
        "title":        str,
        "content":      str,       # markdown body
        "author":       str,
        "author_title": str,
        "author_image": str,       # URL or empty
        "category":     str,
        "tags":         list[str],
        "seo_keywords": list[str],
        "cover_image":  str,       # URL or empty
        "published":    bool,
        "created_at":   str,       # ISO-8601
    }
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BlogBackend(ABC):
    """Interface that all storage backends must satisfy."""

    @abstractmethod
    def fetch_titles(self, limit: int = 500) -> List[str]:
        """Return up to *limit* existing post titles."""

    @abstractmethod
    def push_post(self, post: Dict[str, Any]) -> bool:
        """
        Create / insert a new blog post.

        Returns True on success, False on failure.
        """

    @abstractmethod
    def unpublish(self, title: str) -> bool:
        """
        Mark a post as unpublished by title.

        Returns True on success, False on failure.
        """

    @abstractmethod
    def list_posts(self, published_only: bool = False) -> List[Dict[str, Any]]:
        """
        Return all posts (or only published ones) as dicts.

        Each dict should at minimum contain ``title``, ``content``,
        and ``published`` keys.
        """
