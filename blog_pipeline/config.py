"""
Configuration for the blog pipeline.
All settings read from environment variables with sensible defaults.
"""
import os
from pathlib import Path

# ── Required ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Supabase (optional — set if you want to push/pull from DB) ───────────────
SUPABASE_URL      = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY      = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_TABLE    = os.environ.get("SUPABASE_BLOGS_TABLE", "blogs")

# ── Anthropic model ───────────────────────────────────────────────────────────
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-5")

# ── Local file paths ──────────────────────────────────────────────────────────
BLOGS_DIR    = Path(os.environ.get("BLOGS_DIR", "blogs"))
TOPICS_CACHE = BLOGS_DIR / "_topics.json"
PLANS_CACHE  = BLOGS_DIR / "_plans.json"
REGISTRY     = BLOGS_DIR / "_registry.json"

# ── Blog metadata ────────────────────────────────────────────────────────────
DEFAULT_AUTHOR       = os.environ.get("BLOG_AUTHOR",       "Your Team")
DEFAULT_AUTHOR_TITLE = os.environ.get("BLOG_AUTHOR_TITLE", "Engineering & Product")
DEFAULT_AUTHOR_IMAGE = os.environ.get("BLOG_AUTHOR_IMAGE", "")

# ── Category → tag mapping ───────────────────────────────────────────────────
CATEGORY_MAP = {
    "comparison":          "Best Practices",
    "technical-deep-dive": "Tutorial",
    "case-study":          "Case Study",
    "how-to":              "Tutorial",
    "opinion":             "Industry Insights",
}

# ── Validation ────────────────────────────────────────────────────────────────
def require_anthropic():
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. See .env.example.")

def require_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for DB sync.")
