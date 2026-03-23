#!/usr/bin/env python3
"""
6-pass blog generation pipeline.

Passes:
  0  Fetch existing titles from Supabase (skip duplicates)
  1  Identify new topics to write
  2  Plan structure per topic (comparison / technical-deep-dive / case-study / how-to / opinion)
  3  Generate full markdown content
  4  Humanize (remove AI tells — see humanizer.py)
  5  Add internal links across the batch
  6  Push to Supabase + update local registry

Run:
  python pipeline.py --passes 1-6 --count 5
  python pipeline.py --passes 3-4    # re-humanize existing drafts
  python pipeline.py --passes 6      # push already-written blogs to DB

Environment: see .env.example
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import anthropic

from .config import (
    BLOGS_DIR, TOPICS_CACHE, PLANS_CACHE, REGISTRY,
    CATEGORY_MAP, CLAUDE_MODEL, SUPABASE_URL, SUPABASE_KEY, SUPABASE_TABLE,
    DEFAULT_AUTHOR, DEFAULT_AUTHOR_TITLE, DEFAULT_AUTHOR_IMAGE,
    require_anthropic,
)
from .humanizer import humanize_post, check_banned_words

# ── Unsplash cover pool (deterministic pick via UUID hash) ────────────────────
COVER_POOL = {
    "comparison":          ["1518770660439-4636190af475", "1551288049-bebda4e38f71", "1460925895917-afdab827c52f"],
    "technical-deep-dive": ["1555066931-4365d14bab8c", "1515879218367-8466049037b5", "1542831371-29b0f74f9713"],
    "case-study":          ["1559136555-9303baea8eae", "1553877522-43269e7f0f4",    "1454165804606-c3d57bc86b40"],
    "how-to":              ["1484417894907-623942c8ee29","1507238691740-187a5b1d37b8","1488590528505-98d2b5aba04b"],
    "opinion":             ["1507003211169-0a1dd7228f2d","1543269865-cbf427effbad", "1476514525535-07fb3b4ae5f1"],
}

UNSPLASH_BASE = "https://images.unsplash.com/photo-"


def pick_cover(blog_type: str, title: str) -> str:
    pool = COVER_POOL.get(blog_type, COVER_POOL["technical-deep-dive"])
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    idx = uuid.uuid5(uuid.NAMESPACE_DNS, slug).int % len(pool)
    photo_id = pool[idx]
    return f"{UNSPLASH_BASE}{photo_id}?w=1200&q=80&auto=format&fit=crop"


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _supa_request(method: str, path: str, body=None) -> dict:
    import urllib.request, urllib.error
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()}


def fetch_live_titles() -> list[str]:
    if not SUPABASE_URL:
        return []
    rows = _supa_request("GET", f"{SUPABASE_TABLE}?select=title&limit=500")
    if isinstance(rows, list):
        return [r.get("title", "") for r in rows if r.get("title")]
    return []


def push_blog(blog: dict) -> bool:
    if not SUPABASE_URL:
        return False
    result = _supa_request("POST", SUPABASE_TABLE, blog)
    return "error" not in result


# ── Claude helper ─────────────────────────────────────────────────────────────

def ask_claude(prompt: str, system: str = "", max_tokens: int = 8096) -> str:
    client = anthropic.Anthropic()
    kwargs = dict(model=CLAUDE_MODEL, max_tokens=max_tokens,
                  messages=[{"role": "user", "content": prompt}])
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    return (msg.content[0].text or "").strip()


# ── Pass implementations ──────────────────────────────────────────────────────

def pass1_topics(existing_titles: list[str], count: int, niche: str) -> list[dict]:
    """Identify `count` new blog topics not already covered."""
    existing_json = json.dumps(existing_titles[:100])
    prompt = f"""
Generate {count} high-value blog post topics for a technical audience interested in: {niche}

Return JSON array of objects: [{{"title": "...", "type": "comparison|technical-deep-dive|case-study|how-to|opinion"}}]

Avoid these existing titles:
{existing_json}

Rules:
- No overlap with existing titles (semantic check too)
- Mix of types
- Titles that would rank on Google
- Return ONLY the JSON array
"""
    raw = ask_claude(prompt)
    try:
        start, end = raw.find("["), raw.rfind("]") + 1
        return json.loads(raw[start:end]) if start >= 0 else []
    except json.JSONDecodeError:
        return []


def pass2_plan(topic: dict) -> dict:
    """Plan the structure of one blog post."""
    prompt = f"""
Plan a blog post titled: "{topic['title']}"
Type: {topic.get('type', 'technical-deep-dive')}

Return JSON: {{
  "title": "...",
  "type": "...",
  "outline": ["section 1", "section 2", ...],
  "word_count": 1200,
  "seo_keywords": ["kw1", "kw2", "kw3"],
  "tags": ["tag1", "tag2"]
}}
Return ONLY the JSON object.
"""
    raw = ask_claude(prompt)
    try:
        start, end = raw.find("{"), raw.rfind("}") + 1
        plan = json.loads(raw[start:end])
        plan.setdefault("title", topic["title"])
        plan.setdefault("type", topic.get("type", "how-to"))
        return plan
    except json.JSONDecodeError:
        return {**topic, "outline": [], "seo_keywords": [], "tags": []}


def pass3_content(plan: dict) -> str:
    """Generate full markdown content from a plan."""
    prompt = f"""
Write a complete blog post in markdown.

Title: {plan['title']}
Type: {plan.get('type', 'technical-deep-dive')}
Outline: {json.dumps(plan.get('outline', []))}
Target word count: {plan.get('word_count', 1200)}
SEO keywords to include: {', '.join(plan.get('seo_keywords', []))}

Rules:
- Start with a strong hook (no "Introduction" heading)
- Use H2 and H3 headings
- Include code examples where relevant
- End with a clear CTA or key takeaway
- Write for senior developers and technical founders
- Return ONLY the markdown content
"""
    return ask_claude(prompt, max_tokens=8096)


def pass5_internal_links(blogs: list[dict], all_titles: list[str]) -> list[dict]:
    """Add 2-3 internal links per blog to related posts."""
    # Build a simple title → slug map
    def slugify(t):
        return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")

    title_slugs = {t: f"/blog/{slugify(t)}" for t in all_titles}

    linked = []
    for blog in blogs:
        content = blog.get("content", "")
        other_titles = [t for t in all_titles if t != blog["title"]][:20]
        if not other_titles:
            linked.append(blog)
            continue
        prompt = f"""
Add 2-3 internal links to this blog post. Only link to titles from the provided list.
Format: [Title](/blog/slug)  where slug = lowercase-hyphenated-title.

Available titles:
{json.dumps(other_titles)}

Blog content:
{content[:3000]}

Return ONLY the updated markdown content with links added naturally in the text.
"""
        new_content = ask_claude(prompt, max_tokens=4096)
        linked.append({**blog, "content": new_content or content})
    return linked


def pass6_push(blogs: list[dict]) -> int:
    """Push finalised blogs to Supabase."""
    pushed = 0
    for blog in blogs:
        if push_blog(blog):
            pushed += 1
        time.sleep(0.2)
    return pushed


# ── Registry helpers ──────────────────────────────────────────────────────────

def load_registry() -> dict:
    BLOGS_DIR.mkdir(exist_ok=True)
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text())
        except Exception:
            pass
    return {}


def save_registry(reg: dict):
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    require_anthropic()
    BLOGS_DIR.mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="AI blog pipeline")
    parser.add_argument("--passes", default="1-6", help="Passes to run, e.g. 1-6 or 3-4 or 4")
    parser.add_argument("--count", type=int, default=5, help="Number of blogs to generate")
    parser.add_argument("--niche", default="developer tooling and infrastructure",
                        help="Topic niche for topic generation")
    args = parser.parse_args()

    # Parse pass range
    p = args.passes.split("-")
    start_pass = int(p[0])
    end_pass   = int(p[-1])

    registry = load_registry()

    # Pass 0: fetch live titles
    live_titles = fetch_live_titles()
    local_titles = list(registry.keys())
    all_known = list(dict.fromkeys(live_titles + local_titles))
    print(f"Pass 0: {len(all_known)} existing titles loaded")

    topics = []
    plans  = []
    blogs  = []

    # Pass 1: topics
    if start_pass <= 1 <= end_pass:
        print(f"Pass 1: generating {args.count} topics...")
        raw = json.loads(TOPICS_CACHE.read_text()) if TOPICS_CACHE.exists() else []
        new_topics = pass1_topics(all_known, args.count, args.niche)
        topics = (raw + new_topics)[:args.count]
        TOPICS_CACHE.write_text(json.dumps(topics, indent=2))
        print(f"  → {len(topics)} topics ready")
    else:
        topics = json.loads(TOPICS_CACHE.read_text()) if TOPICS_CACHE.exists() else []

    # Pass 2: plans
    if start_pass <= 2 <= end_pass:
        print("Pass 2: planning structures...")
        existing_plans = json.loads(PLANS_CACHE.read_text()) if PLANS_CACHE.exists() else {}
        planned = dict(existing_plans)
        for t in topics:
            title = t["title"]
            if title not in planned:
                planned[title] = pass2_plan(t)
                time.sleep(0.5)
        PLANS_CACHE.write_text(json.dumps(planned, indent=2))
        plans = list(planned.values())
        print(f"  → {len(plans)} plans ready")
    else:
        planned = json.loads(PLANS_CACHE.read_text()) if PLANS_CACHE.exists() else {}
        plans = list(planned.values())

    # Pass 3: generate content
    if start_pass <= 3 <= end_pass:
        print("Pass 3: generating content...")
        for plan in plans[:args.count]:
            title = plan["title"]
            slug  = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            path  = BLOGS_DIR / f"{slug[:80]}.md"
            if path.exists():
                print(f"  skip (exists): {slug[:50]}")
                continue
            content = pass3_content(plan)
            path.write_text(content, encoding="utf-8")
            print(f"  wrote: {path.name}")
            time.sleep(1)

    # Pass 4: humanize
    if start_pass <= 4 <= end_pass:
        print("Pass 4: humanizing...")
        for md_file in sorted(BLOGS_DIR.glob("*.md")):
            if md_file.name.startswith("_"):
                continue
            content = md_file.read_text(encoding="utf-8")
            if "<!-- humanized -->" in content:
                continue
            print(f"  humanizing: {md_file.name}")
            humanized = humanize_post(content)
            remaining = check_banned_words(humanized)
            if remaining:
                print(f"  ⚠ still has banned words: {remaining}")
            md_file.write_text(humanized + "\n<!-- humanized -->", encoding="utf-8")
            time.sleep(0.5)

    # Load all written blogs for passes 5-6
    all_blog_titles = []
    for md_file in sorted(BLOGS_DIR.glob("*.md")):
        if not md_file.name.startswith("_"):
            all_blog_titles.append(md_file.stem.replace("-", " "))

    # Pass 5: internal links
    if start_pass <= 5 <= end_pass:
        print("Pass 5: adding internal links...")
        blog_objects = []
        for md_file in sorted(BLOGS_DIR.glob("*.md")):
            if md_file.name.startswith("_"):
                continue
            blog_objects.append({
                "title": md_file.stem.replace("-", " "),
                "content": md_file.read_text(encoding="utf-8"),
                "_path": md_file,
            })
        linked = pass5_internal_links(blog_objects, all_blog_titles)
        for b in linked:
            b["_path"].write_text(b["content"], encoding="utf-8")

    # Pass 6: push to Supabase
    if start_pass <= 6 <= end_pass:
        if not SUPABASE_URL:
            print("Pass 6: skipped (SUPABASE_URL not set)")
        else:
            print("Pass 6: pushing to Supabase...")
            to_push = []
            for md_file in sorted(BLOGS_DIR.glob("*.md")):
                if md_file.name.startswith("_"):
                    continue
                title = md_file.stem.replace("-", " ").title()
                if title in registry:
                    continue
                content = md_file.read_text(encoding="utf-8").replace("\n<!-- humanized -->", "")
                plan    = planned.get(title, {})
                blog_type = plan.get("type", "how-to")
                to_push.append({
                    "title":       title,
                    "content":     content,
                    "author":      DEFAULT_AUTHOR,
                    "author_title": DEFAULT_AUTHOR_TITLE,
                    "author_image": DEFAULT_AUTHOR_IMAGE,
                    "category":    CATEGORY_MAP.get(blog_type, "Tutorial"),
                    "tags":        plan.get("tags", []),
                    "seo_keywords": plan.get("seo_keywords", []),
                    "cover_image": pick_cover(blog_type, title),
                    "published":   True,
                    "created_at":  datetime.utcnow().isoformat(),
                })
            pushed = pass6_push(to_push)
            for b in to_push:
                registry[b["title"]] = {"pushed_at": datetime.utcnow().isoformat()}
            save_registry(registry)
            print(f"  → pushed {pushed}/{len(to_push)} blogs")

    print("\nDone.")


if __name__ == "__main__":
    main()
