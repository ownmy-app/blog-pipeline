"""
Humanizer pass — removes AI writing tells from generated blog content.

The prompt enforces:
  - No em-dashes (—)
  - No semicolons as sentence connectors
  - No filler emojis
  - No banned power-words: "leverage", "seamless", "robust", "cutting-edge",
    "game-changer", "revolutionize", "synergy", "paradigm", "transformative",
    "unlock", "delve", "streamline", "elevate", "empower"
  - Requires: contractions (it's, we're, you'll), active voice, plain English
  - Max one exclamation mark per post
  - No "In conclusion / In summary / To summarize" openers

Use standalone:
    from humanizer import humanize_post
    clean = humanize_post(my_draft)
"""

BANNED_WORDS = [
    "leverage", "seamless", "robust", "cutting-edge", "game-changer",
    "revolutionize", "synergy", "paradigm", "transformative", "unlock",
    "delve", "streamline", "elevate", "empower", "holistic", "utilize",
    "facilitate", "innovative", "solution", "ecosystem", "journey",
]

HUMANIZER_SYSTEM = """\
You are a senior technical editor. Your job is to rewrite AI-generated blog posts \
so they read like they were written by a smart human engineer who actually ships code.

Rules (non-negotiable):
1. Remove ALL em-dashes (—). Replace with commas, full stops, or rephrase.
2. Remove semicolons used to connect sentences. Use a full stop or restructure.
3. Remove all emojis.
4. Replace every instance of these words with plain alternatives: \
leverage, seamless, robust, cutting-edge, game-changer, revolutionize, synergy, \
paradigm, transformative, unlock, delve, streamline, elevate, empower, \
holistic, utilize, facilitate, innovative, solution, ecosystem, journey.
5. Use contractions: write "it's", "we're", "you'll", "don't", "can't".
6. Use active voice. Kill passive constructions.
7. Maximum ONE exclamation mark in the entire post.
8. Never open a section with "In conclusion", "In summary", or "To summarize".
9. Keep technical accuracy. Do not change code blocks.
10. Return only the rewritten blog post — no commentary, no preamble.\
"""


def humanize_post(content: str, model: str = None) -> str:
    """
    Run the humanizer pass on a blog post draft.

    Args:
        content: Raw markdown content to humanize.
        model:   Anthropic model override (default: from config.CLAUDE_MODEL).

    Returns:
        Humanized markdown string.
    """
    import anthropic
    from .config import CLAUDE_MODEL, require_anthropic
    require_anthropic()

    client = anthropic.Anthropic()
    used_model = model or CLAUDE_MODEL

    message = client.messages.create(
        model=used_model,
        max_tokens=8096,
        system=HUMANIZER_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Rewrite this blog post following all rules:\n\n{content}",
            }
        ],
    )
    return (message.content[0].text or content).strip()


def check_banned_words(content: str) -> list[str]:
    """Returns list of banned words still present in content (for QC)."""
    import re
    found = []
    for word in BANNED_WORDS:
        if re.search(r'\b' + re.escape(word) + r'\b', content, re.IGNORECASE):
            found.append(word)
    return found


def _cli():
    """CLI entry point: blog-humanize <file.md> [--check-only]"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        prog="blog-humanize",
        description="Remove AI writing tells from a markdown blog post.",
    )
    parser.add_argument("file", nargs="?", help="Markdown file to humanize (default: stdin)")
    parser.add_argument("--check-only", action="store_true", help="Only report banned words, don't rewrite")
    parser.add_argument("--in-place", action="store_true", help="Overwrite input file")
    args = parser.parse_args()

    if args.file:
        from pathlib import Path
        content = Path(args.file).read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()

    banned = check_banned_words(content)
    if banned:
        print(f"⚠️  Banned words found: {', '.join(banned)}", file=sys.stderr)
    else:
        print("✅ No banned words found.", file=sys.stderr)

    if args.check_only:
        sys.exit(1 if banned else 0)

    humanized = humanize_post(content)
    remaining = check_banned_words(humanized)
    if remaining:
        print(f"⚠️  Still has banned words after humanize: {', '.join(remaining)}", file=sys.stderr)

    if args.in_place and args.file:
        from pathlib import Path
        Path(args.file).write_text(humanized, encoding="utf-8")
        print(f"✅ Saved to {args.file}", file=sys.stderr)
    else:
        print(humanized)
