#!/usr/bin/env python3
"""
Blog audit pass — scores existing posts and optionally unpublishes weak ones.

Scoring criteria:
  - Word count (target 800-2000)
  - Banned word density (fail if > 2 banned words)
  - Heading structure (at least 3 H2s)
  - Code blocks present (good for technical posts)
  - Em-dash / semicolon count (AI tell markers)

Run:
  python audit.py                     # score all blogs, print report
  python audit.py --unpublish         # also unpublish score < 50 in Supabase
  python audit.py --fix               # re-humanize weak posts in-place
  python audit.py --min-score 60      # set custom threshold

Environment: see .env.example (SUPABASE_URL required for --unpublish)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any


def _count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _count_headings(text: str, level: int = 2) -> int:
    prefix = "#" * level + " "
    return sum(1 for line in text.splitlines() if line.startswith(prefix))


def _count_code_blocks(text: str) -> int:
    return text.count("```")


BANNED_WORDS = [
    "leverage", "seamless", "robust", "cutting-edge", "game-changer",
    "revolutionize", "synergy", "paradigm", "transformative", "unlock",
    "delve", "streamline", "elevate", "empower", "holistic", "utilize",
]


def score_post(content: str) -> Dict[str, Any]:
    """
    Score a blog post 0–100.
    Returns detailed breakdown dict with 'score' key.
    """
    clean = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    words = _count_words(clean)
    headings = _count_headings(clean, 2)
    code_blocks = _count_code_blocks(clean)
    em_dashes = clean.count("—")
    semicolons = len(re.findall(r";(?!\s*[{}\n])", clean))  # sentence semicolons

    banned_found = [w for w in BANNED_WORDS if re.search(r"\b" + w + r"\b", clean, re.I)]

    # Scoring
    score = 100

    # Word count
    if words < 400:
        score -= 30
    elif words < 600:
        score -= 15
    elif words > 3000:
        score -= 5  # too long is a minor issue

    # Structure
    if headings < 2:
        score -= 20
    elif headings < 3:
        score -= 10

    # AI tells
    score -= len(banned_found) * 8   # -8 per banned word
    score -= min(em_dashes * 5, 20)  # max -20 for em-dashes
    score -= min(semicolons * 3, 15)  # max -15 for semicolons

    # Positive signals
    if code_blocks >= 2:
        score += 5
    if words >= 800 and words <= 2000:
        score += 5

    score = max(0, min(100, score))

    return {
        "score": score,
        "words": words,
        "headings_h2": headings,
        "code_blocks": code_blocks // 2,  # opening ``` only
        "em_dashes": em_dashes,
        "sentence_semicolons": semicolons,
        "banned_words": banned_found,
        "grade": "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "F",
    }


def unpublish_in_supabase(title: str) -> bool:
    """Set published=false for a blog by title in Supabase."""
    import urllib.request
    import urllib.error
    from .config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_TABLE, require_supabase
    require_supabase()

    encoded_title = urllib.parse.quote(f"eq.{title}")
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?title={encoded_title}"
    data = json.dumps({"published": False}).encode()
    req = urllib.request.Request(url, data=data, method="PATCH", headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    })
    try:
        with urllib.request.urlopen(req):
            return True
    except Exception:
        return False


def main():

    parser = argparse.ArgumentParser(description="Audit blog posts for quality")
    parser.add_argument("--dir", default="blogs", help="Blog directory (default: blogs)")
    parser.add_argument("--min-score", type=int, default=50, help="Min score threshold (default: 50)")
    parser.add_argument("--unpublish", action="store_true", help="Unpublish posts below threshold in Supabase")
    parser.add_argument("--fix", action="store_true", help="Re-humanize posts below threshold in-place")
    parser.add_argument("--json", dest="json_out", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    blogs_dir = Path(args.dir)
    if not blogs_dir.exists():
        print(f"Directory not found: {blogs_dir}", file=sys.stderr)
        sys.exit(1)

    results: List[Dict[str, Any]] = []
    for md_file in sorted(blogs_dir.glob("*.md")):
        if md_file.name.startswith("_"):
            continue
        content = md_file.read_text(encoding="utf-8")
        info = score_post(content)
        info["file"] = md_file.name
        info["title"] = md_file.stem.replace("-", " ").title()
        results.append(info)

    results.sort(key=lambda r: r["score"])

    if args.json_out:
        print(json.dumps(results, indent=2))
        return

    # Human-readable report
    print(f"\n{'─'*72}")
    print(f"{'BLOG AUDIT REPORT':^72}")
    print(f"{'─'*72}")
    print(f"{'File':<45} {'Score':>6} {'Grade':>5} {'Words':>6} {'Issues'}")
    print(f"{'─'*72}")

    fail_count = 0
    for r in results:
        issues = []
        if r["banned_words"]:
            issues.append(f"banned:{','.join(r['banned_words'][:2])}")
        if r["em_dashes"]:
            issues.append(f"emdash:{r['em_dashes']}")
        if r["headings_h2"] < 2:
            issues.append("no-headings")

        status = "⚠️ " if r["score"] < args.min_score else "  "
        print(f"{status}{r['file'][:43]:<43} {r['score']:>6} {r['grade']:>5} {r['words']:>6}  {', '.join(issues)}")
        if r["score"] < args.min_score:
            fail_count += 1

    print(f"{'─'*72}")
    print(f"Total: {len(results)} posts | Below threshold ({args.min_score}): {fail_count}")

    if args.unpublish and fail_count:
        print(f"\nUnpublishing {fail_count} posts in Supabase...")
        for r in results:
            if r["score"] < args.min_score:
                ok = unpublish_in_supabase(r["title"])
                print(f"  {'✅' if ok else '❌'} {r['title'][:50]}")

    if args.fix and fail_count:
        print(f"\nRe-humanizing {fail_count} posts...")
        from .humanizer import humanize_post
        for r in results:
            if r["score"] < args.min_score:
                path = blogs_dir / r["file"]
                content = path.read_text(encoding="utf-8")
                fixed = humanize_post(content)
                path.write_text(fixed + "\n<!-- humanized -->", encoding="utf-8")
                print(f"  ✅ Re-humanized: {r['file']}")


if __name__ == "__main__":
    main()
