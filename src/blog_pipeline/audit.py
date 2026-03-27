#!/usr/bin/env python3
"""
Blog audit pass — scores existing posts and optionally unpublishes weak ones.

Composite scoring:
  - Quality:       60%  (word count, headings, code blocks, AI tells)
  - AI detection:  20%  (banned words, sentence uniformity, em-dashes, etc.)
  - SEO:           20%  (keyword density, readability, headings, links)

Run:
  blog-audit                      # score all blogs, print report
  blog-audit --unpublish          # also unpublish score < 50 via backend
  blog-audit --fix                # re-humanize weak posts in-place
  blog-audit --seo                # include SEO analysis in report
  blog-audit --min-score 60       # set custom threshold
  blog-audit --json               # output as JSON

Environment: see .env.example
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from .humanizer_rules import load_rules
from .ai_detector import score_ai
from .seo import score_seo


# Load shared rules
_rules = load_rules()


def _count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _count_headings(text: str, level: int = 2) -> int:
    prefix = "#" * level + " "
    return sum(1 for line in text.splitlines() if line.startswith(prefix))


def _count_code_blocks(text: str) -> int:
    return text.count("```")


def score_post(content: str, seo: bool = False) -> Dict[str, Any]:
    """
    Score a blog post 0-100.

    Composite:
        quality    60%  — word count, headings, code blocks, basic AI tells
        ai_detect  20%  — from ai_detector.score_ai()
        seo_score  20%  — from seo.score_seo() (only when seo=True)

    Returns detailed breakdown dict with 'score' key.
    """
    clean = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    words = _count_words(clean)
    headings = _count_headings(clean, 2)
    code_blocks = _count_code_blocks(clean)
    em_dashes = clean.count("\u2014")
    semicolons = len(re.findall(r";(?!\s*[{}\n])", clean))

    # Check for banned words using rules
    banned_found = []
    for w in _rules.banned_words:
        if re.search(r"\b" + re.escape(w) + r"\b", clean, re.IGNORECASE):
            banned_found.append(w)

    # ── Quality score (out of 100, will be weighted to 60%) ──────────────
    quality = 100

    # Word count
    if words < 400:
        quality -= 30
    elif words < 600:
        quality -= 15
    elif words > 3000:
        quality -= 5

    # Structure
    if headings < 2:
        quality -= 20
    elif headings < 3:
        quality -= 10

    # AI tells (basic)
    quality -= len(banned_found) * 8
    quality -= min(em_dashes * 5, 20)
    quality -= min(semicolons * 3, 15)

    # Positive signals
    if code_blocks >= 2:
        quality += 5
    if 800 <= words <= 2000:
        quality += 5

    quality = max(0, min(100, quality))

    # ── AI detection score ───────────────────────────────────────────────
    ai_result = score_ai(content, rules=_rules)
    # Convert from 0-1 (where 1=AI) to 0-100 (where 100=human-like)
    ai_human_score = int((1.0 - ai_result["ai_score"]) * 100)

    # ── SEO score ────────────────────────────────────────────────────────
    seo_score_val = 0
    seo_result = {}
    if seo:
        seo_result = score_seo(content)
        seo_score_val = seo_result.get("seo_score", 0)

    # ── Composite ────────────────────────────────────────────────────────
    if seo:
        composite = int(quality * 0.6 + ai_human_score * 0.2 + seo_score_val * 0.2)
    else:
        # When SEO is disabled, reweight: quality 75%, AI 25%
        composite = int(quality * 0.75 + ai_human_score * 0.25)

    composite = max(0, min(100, composite))

    result = {
        "score": composite,
        "quality_score": quality,
        "ai_human_score": ai_human_score,
        "ai_detection_score": round(ai_result["ai_score"], 3),
        "ai_flags": ai_result["flags"],
        "words": words,
        "headings_h2": headings,
        "code_blocks": code_blocks // 2,
        "em_dashes": em_dashes,
        "sentence_semicolons": semicolons,
        "banned_words": banned_found,
        "grade": "A" if composite >= 80 else "B" if composite >= 65 else "C" if composite >= 50 else "F",
    }

    if seo:
        result["seo_score"] = seo_score_val
        result["seo_details"] = seo_result

    return result


def run_audit(
    blogs_dir: Path,
    min_score: int = 50,
    seo: bool = False,
) -> List[Dict[str, Any]]:
    """
    Run audit on all markdown files in a directory.

    Returns list of result dicts, sorted by score ascending.
    Callable from both CLIs (blog-audit and blog-generate --audit).
    """
    results: List[Dict[str, Any]] = []
    for md_file in sorted(blogs_dir.glob("*.md")):
        if md_file.name.startswith("_"):
            continue
        content = md_file.read_text(encoding="utf-8")
        info = score_post(content, seo=seo)
        info["file"] = md_file.name
        info["title"] = md_file.stem.replace("-", " ").title()
        results.append(info)

    results.sort(key=lambda r: r["score"])
    return results


def main():
    parser = argparse.ArgumentParser(description="Audit blog posts for quality")
    parser.add_argument("--dir", default="blogs", help="Blog directory (default: blogs)")
    parser.add_argument("--min-score", type=int, default=50, help="Min score threshold (default: 50)")
    parser.add_argument("--unpublish", action="store_true", help="Unpublish posts below threshold via backend")
    parser.add_argument("--fix", action="store_true", help="Re-humanize posts below threshold in-place")
    parser.add_argument("--seo", action="store_true", help="Include SEO scoring in the audit")
    parser.add_argument("--json", dest="json_out", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    blogs_dir = Path(args.dir)
    if not blogs_dir.exists():
        print(f"Directory not found: {blogs_dir}", file=sys.stderr)
        sys.exit(1)

    results = run_audit(blogs_dir, min_score=args.min_score, seo=args.seo)

    if args.json_out:
        # Remove non-serializable parts
        output = []
        for r in results:
            clean_r = {k: v for k, v in r.items() if k != "seo_details"}
            if "seo_details" in r:
                seo_d = r["seo_details"]
                clean_seo = {k: v for k, v in seo_d.items() if k not in ("headings", "links")}
                clean_r["seo_details"] = clean_seo
            output.append(clean_r)
        print(json.dumps(output, indent=2))
        return

    # Human-readable report
    header = "BLOG AUDIT REPORT"
    if args.seo:
        header += " (with SEO)"
    print(f"\n{'─'*80}")
    print(f"{header:^80}")
    print(f"{'─'*80}")
    cols = f"{'File':<40} {'Score':>5} {'Qual':>4} {'AI':>5} "
    if args.seo:
        cols += f"{'SEO':>4} "
    cols += f"{'Grade':>5} {'Words':>6} {'Issues'}"
    print(cols)
    print(f"{'─'*80}")

    fail_count = 0
    for r in results:
        issues = []
        if r["banned_words"]:
            issues.append(f"banned:{','.join(r['banned_words'][:2])}")
        if r["em_dashes"]:
            issues.append(f"emdash:{r['em_dashes']}")
        if r["headings_h2"] < 2:
            issues.append("no-headings")
        if r["ai_flags"]:
            issues.append(f"ai-flags:{len(r['ai_flags'])}")

        status = "!! " if r["score"] < args.min_score else "   "
        line = f"{status}{r['file'][:37]:<37} {r['score']:>5} {r['quality_score']:>4} {r['ai_detection_score']:>5.2f} "
        if args.seo:
            line += f"{r.get('seo_score', 0):>4} "
        line += f"{r['grade']:>5} {r['words']:>6}  {', '.join(issues)}"
        print(line)
        if r["score"] < args.min_score:
            fail_count += 1

    print(f"{'─'*80}")
    print(f"Total: {len(results)} posts | Below threshold ({args.min_score}): {fail_count}")

    # Unpublish via backend
    if args.unpublish and fail_count:
        from .backends import get_backend
        try:
            backend = get_backend()
            print(f"\nUnpublishing {fail_count} posts via {backend.__class__.__name__}...")
            for r in results:
                if r["score"] < args.min_score:
                    ok = backend.unpublish(r["title"])
                    status = "OK" if ok else "FAIL"
                    print(f"  [{status}] {r['title'][:50]}")
        except Exception as e:
            print(f"\nFailed to unpublish: {e}", file=sys.stderr)

    # Re-humanize weak posts
    if args.fix and fail_count:
        print(f"\nRe-humanizing {fail_count} posts...")
        from .humanizer import humanize_post
        for r in results:
            if r["score"] < args.min_score:
                path = blogs_dir / r["file"]
                content = path.read_text(encoding="utf-8")
                fixed = humanize_post(content)
                path.write_text(fixed + "\n<!-- humanized -->", encoding="utf-8")
                print(f"  Re-humanized: {r['file']}")


if __name__ == "__main__":
    main()
