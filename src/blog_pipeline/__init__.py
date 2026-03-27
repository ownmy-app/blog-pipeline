"""blog-pipeline — AI blog generation with humanizer pass."""

from .humanizer import humanize_post, check_banned_words, check_ai_tells, humanize_post_scored
from .llm import ask_llm
from .backends import get_backend
from .humanizer_rules import load_rules, build_system_prompt, HumanizerRules
from .seo import score_seo, calculate_readability, check_keyword_density
from .ai_detector import score_ai

__all__ = [
    # Humanizer
    "humanize_post",
    "check_banned_words",
    "check_ai_tells",
    "humanize_post_scored",
    # LLM
    "ask_llm",
    # Backends
    "get_backend",
    # Rules
    "load_rules",
    "build_system_prompt",
    "HumanizerRules",
    # SEO
    "score_seo",
    "calculate_readability",
    "check_keyword_density",
    # AI detection
    "score_ai",
]

__version__ = "0.2.0"
