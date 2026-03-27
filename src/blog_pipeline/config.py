"""
Configuration for the blog pipeline.
All settings read from environment variables with sensible defaults.
"""
import os
from pathlib import Path

# ── LLM provider ─────────────────────────────────────────────────────────────
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()
LLM_MODEL    = os.environ.get("LLM_MODEL", "")

# ── API keys ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")

# ── Supabase (optional — set if you want to push/pull from DB) ───────────────
SUPABASE_URL      = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY      = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_TABLE    = os.environ.get("SUPABASE_BLOGS_TABLE", "blogs")

# ── Legacy model setting (falls back to LLM_MODEL) ──────────────────────────
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-5")

# ── Backend ──────────────────────────────────────────────────────────────────
BLOG_BACKEND = os.environ.get("BLOG_BACKEND", "filesystem").strip().lower()

# ── Local file paths ──────────────────────────────────────────────────────────
BLOGS_DIR    = Path(os.environ.get("BLOGS_DIR", "blogs"))
TOPICS_CACHE = BLOGS_DIR / "_topics.json"
PLANS_CACHE  = BLOGS_DIR / "_plans.json"
REGISTRY     = BLOGS_DIR / "_registry.json"

# ── Blog metadata ────────────────────────────────────────────────────────────
DEFAULT_AUTHOR       = os.environ.get("BLOG_AUTHOR",       "Your Team")
DEFAULT_AUTHOR_TITLE = os.environ.get("BLOG_AUTHOR_TITLE", "Engineering & Product")
DEFAULT_AUTHOR_IMAGE = os.environ.get("BLOG_AUTHOR_IMAGE", "")

# ── Humanizer ────────────────────────────────────────────────────────────────
HUMANIZER_RULES = os.environ.get("HUMANIZER_RULES", "")

# ── WordPress backend ────────────────────────────────────────────────────────
WP_URL          = os.environ.get("WP_URL", "")
WP_USER         = os.environ.get("WP_USER", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

# ── Notion backend ───────────────────────────────────────────────────────────
NOTION_API_KEY     = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")

# ── Contentful backend ───────────────────────────────────────────────────────
CONTENTFUL_SPACE_ID   = os.environ.get("CONTENTFUL_SPACE_ID", "")
CONTENTFUL_MGMT_TOKEN = os.environ.get("CONTENTFUL_MGMT_TOKEN", "")
CONTENTFUL_ENVIRONMENT = os.environ.get("CONTENTFUL_ENVIRONMENT", "master")

# ── Postgres backend ─────────────────────────────────────────────────────────
POSTGRES_DSN = os.environ.get("POSTGRES_DSN", "")

# ── Category -> tag mapping ──────────────────────────────────────────────────
CATEGORY_MAP = {
    "comparison":          "Best Practices",
    "technical-deep-dive": "Tutorial",
    "case-study":          "Case Study",
    "how-to":              "Tutorial",
    "opinion":             "Industry Insights",
}

# ── Validation ────────────────────────────────────────────────────────────────

def require_llm():
    """Validate that the selected LLM provider has credentials configured."""
    provider = LLM_PROVIDER
    if provider == "anthropic":
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. See .env.example.")
    elif provider == "openai":
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set. See .env.example.")
    elif provider == "litellm":
        pass  # litellm handles its own auth
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER={provider!r}. Supported: anthropic, openai, litellm")


# Legacy alias
require_anthropic = require_llm


def require_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for DB sync.")


def require_backend():
    """Validate that the selected backend has the required env vars."""
    backend = BLOG_BACKEND
    if backend == "supabase":
        require_supabase()
    elif backend == "filesystem":
        pass  # always available
    elif backend == "postgres":
        if not POSTGRES_DSN:
            raise RuntimeError("POSTGRES_DSN is not set. See .env.example.")
    elif backend == "wordpress":
        if not WP_URL or not WP_USER or not WP_APP_PASSWORD:
            raise RuntimeError("WP_URL, WP_USER, and WP_APP_PASSWORD are required for the wordpress backend.")
    elif backend == "notion":
        if not NOTION_API_KEY or not NOTION_DATABASE_ID:
            raise RuntimeError("NOTION_API_KEY and NOTION_DATABASE_ID are required for the notion backend.")
    elif backend == "contentful":
        if not CONTENTFUL_SPACE_ID or not CONTENTFUL_MGMT_TOKEN:
            raise RuntimeError("CONTENTFUL_SPACE_ID and CONTENTFUL_MGMT_TOKEN are required for the contentful backend.")
    else:
        raise RuntimeError(f"Unknown BLOG_BACKEND={backend!r}.")
