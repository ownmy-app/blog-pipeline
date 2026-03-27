"""
Humanizer pass — removes AI writing tells from generated blog content.

The rules are loaded from YAML (see humanizer_rules.py) and the system
prompt is built dynamically.  The LLM call routes through the
provider-agnostic ``llm.ask_llm()`` abstraction.

Usage::

    from blog_pipeline.humanizer import humanize_post, humanize_post_scored
    clean = humanize_post(my_draft)
    result = humanize_post_scored(my_draft)
    print(result["ai_score_before"], "->", result["ai_score_after"])
"""

import re
from typing import Any, Dict, List, Optional

from .humanizer_rules import load_rules, build_system_prompt

# Load rules once at module level
_rules = load_rules()


def humanize_post(content: str, model: str = None) -> str:
    """
    Run the humanizer pass on a blog post draft.

    Args:
        content: Raw markdown content to humanize.
        model:   Ignored (kept for backward compat). Model is read from env.

    Returns:
        Humanized markdown string.
    """
    from .llm import ask_llm

    system = build_system_prompt(_rules)
    result = ask_llm(
        prompt=f"Rewrite this blog post following all rules:\n\n{content}",
        system=system,
        max_tokens=8096,
    )
    return result or content


def check_ai_tells(content: str, rules=None) -> Dict[str, Any]:
    """
    Comprehensive check for AI writing tells.

    Args:
        content: Text to analyse.
        rules:   Optional HumanizerRules (defaults to module-level rules).

    Returns::

        {
            "words":    list[str],   # banned words found
            "phrases":  list[str],   # banned phrases found
            "patterns": list[str],   # flagged sentence starters found
            "em_dashes": int,
            "semicolons": int,
            "exclamations": int,
        }
    """
    r = rules or _rules
    lower = content.lower()

    # Banned words
    words_found: List[str] = []
    for w in r.banned_words:
        if re.search(r"\b" + re.escape(w) + r"\b", content, re.IGNORECASE):
            words_found.append(w)

    # Banned phrases
    phrases_found: List[str] = []
    for p in r.banned_phrases:
        if p.lower() in lower:
            phrases_found.append(p)

    # Sentence start flags
    patterns_found: List[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        for flag in r.sentence_start_flags:
            if stripped.startswith(flag):
                patterns_found.append(flag)

    em_dashes = content.count("\u2014")
    semicolons = len(re.findall(r";(?!\s*[{}\n])", content))
    exclamations = content.count("!")

    return {
        "words": words_found,
        "phrases": phrases_found,
        "patterns": patterns_found,
        "em_dashes": em_dashes,
        "semicolons": semicolons,
        "exclamations": exclamations,
    }


def check_banned_words(content: str) -> List[str]:
    """
    Returns list of banned words / AI-tells still present in content.

    This is a backward-compatible wrapper around ``check_ai_tells()``.
    """
    tells = check_ai_tells(content)
    found = list(tells["words"])

    # Add phrase flags
    for p in tells["phrases"]:
        found.append(f'phrase: "{p}"')

    # Flag em-dash clusters (2+ em-dashes = AI tell)
    if tells["em_dashes"] >= 2:
        found.append(f"em-dash used {tells['em_dashes']}x (AI tell)")

    return found


def humanize_post_scored(content: str, model: str = None) -> Dict[str, Any]:
    """
    Humanize a post and return before/after AI detection scores.

    Args:
        content: Raw markdown content to humanize.
        model:   Ignored (kept for backward compat).

    Returns::

        {
            "content":          str,     # humanized text
            "ai_score_before":  float,   # 0.0-1.0
            "ai_score_after":   float,   # 0.0-1.0
            "improvement":      float,   # positive = better
        }
    """
    from .ai_detector import score_ai

    before = score_ai(content, rules=_rules)
    humanized = humanize_post(content, model=model)
    after = score_ai(humanized, rules=_rules)

    return {
        "content": humanized,
        "ai_score_before": before["ai_score"],
        "ai_score_after": after["ai_score"],
        "improvement": before["ai_score"] - after["ai_score"],
    }


def _cli():
    """CLI entry point: blog-humanize <file.md> [--check-only]"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        prog="blog-humanize",
        description="Remove AI writing tells from a markdown blog post.",
    )
    parser.add_argument("file", nargs="?", help="Markdown file to humanize (default: stdin)")
    parser.add_argument("--check-only", action="store_true", help="Only report AI tells, don't rewrite")
    parser.add_argument("--in-place", action="store_true", help="Overwrite input file")
    parser.add_argument("--score", action="store_true", help="Show AI detection scores")
    args = parser.parse_args()

    if args.file:
        from pathlib import Path
        content = Path(args.file).read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()

    # Show AI tells
    tells = check_ai_tells(content)
    banned = check_banned_words(content)
    if banned:
        print(f"Banned words/tells found: {', '.join(banned)}", file=sys.stderr)
    else:
        print("No banned words found.", file=sys.stderr)

    if tells["patterns"]:
        print(f"Flagged sentence starters: {', '.join(tells['patterns'])}", file=sys.stderr)

    # Show AI score if requested
    if args.score or args.check_only:
        from .ai_detector import score_ai
        result = score_ai(content, rules=_rules)
        print(f"AI detection score: {result['ai_score']:.3f} (0=human, 1=AI)", file=sys.stderr)
        if result["flags"]:
            for flag in result["flags"]:
                print(f"  - {flag}", file=sys.stderr)

    if args.check_only:
        sys.exit(1 if banned else 0)

    # Run humanizer with scoring
    result = humanize_post_scored(content)
    humanized = result["content"]
    print(f"AI score: {result['ai_score_before']:.3f} -> {result['ai_score_after']:.3f} "
          f"(improvement: {result['improvement']:.3f})", file=sys.stderr)

    remaining = check_banned_words(humanized)
    if remaining:
        print(f"Still has banned words after humanize: {', '.join(remaining)}", file=sys.stderr)

    if args.in_place and args.file:
        from pathlib import Path
        Path(args.file).write_text(humanized, encoding="utf-8")
        print(f"Saved to {args.file}", file=sys.stderr)
    else:
        print(humanized)
