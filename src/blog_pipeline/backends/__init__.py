"""
Blog storage backends — factory + lazy imports.

Usage:
    from blog_pipeline.backends import get_backend
    backend = get_backend()          # reads BLOG_BACKEND env
    backend = get_backend("supabase")
"""

import os

_BACKEND_MAP = {
    "supabase":   ".supabase",
    "filesystem": ".filesystem",
    "postgres":   ".postgres",
    "wordpress":  ".wordpress",
    "notion":     ".notion",
    "contentful": ".contentful",
}


def get_backend(name: str = None):
    """
    Return an instantiated BlogBackend for *name*.

    If *name* is None, reads BLOG_BACKEND env var (default: ``filesystem``).
    """
    backend_name = (name or os.environ.get("BLOG_BACKEND", "filesystem")).strip().lower()

    if backend_name not in _BACKEND_MAP:
        supported = ", ".join(sorted(_BACKEND_MAP))
        raise ValueError(
            f"Unknown BLOG_BACKEND={backend_name!r}. Supported: {supported}"
        )

    module_path = _BACKEND_MAP[backend_name]

    # Lazy import to avoid pulling in optional deps until needed
    import importlib
    mod = importlib.import_module(module_path, package=__name__)

    # Each module exposes a Backend class
    class_map = {
        "supabase":   "SupabaseBackend",
        "filesystem": "FilesystemBackend",
        "postgres":   "PostgresBackend",
        "wordpress":  "WordPressBackend",
        "notion":     "NotionBackend",
        "contentful": "ContentfulBackend",
    }

    cls = getattr(mod, class_map[backend_name])
    return cls()
