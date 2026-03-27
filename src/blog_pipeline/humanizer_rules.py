"""
Humanizer rules engine — configurable via YAML or programmatic defaults.

Priority:
    1. Path from ``HUMANIZER_RULES`` env var
    2. ``humanizer_rules.yml`` next to caller (if exists)
    3. Built-in ``humanizer_rules.default.yml`` shipped with the package

Usage::

    from blog_pipeline.humanizer_rules import load_rules, build_system_prompt
    rules = load_rules()                       # auto-detects source
    prompt = build_system_prompt(rules)         # dynamic system prompt
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class HumanizerRules:
    """All tuneable knobs for the humanizer pass."""

    banned_words: List[str] = field(default_factory=list)
    banned_phrases: List[str] = field(default_factory=list)
    sentence_start_flags: List[str] = field(default_factory=list)
    max_exclamations: int = 1
    require_contractions: bool = True
    max_paragraph_repeat_starts: int = 2
    rules: List[str] = field(default_factory=list)


def get_default_rules() -> HumanizerRules:
    """Return a HumanizerRules instance populated with all built-in defaults."""
    return HumanizerRules(
        banned_words=[
            "leverage", "seamless", "robust", "cutting-edge", "game-changer",
            "revolutionize", "synergy", "paradigm", "transformative", "unlock",
            "delve", "streamline", "elevate", "empower", "holistic", "utilize",
            "facilitate", "innovative", "solution", "ecosystem", "journey",
            "furthermore", "moreover", "consequently", "nevertheless",
            "aforementioned", "groundbreaking", "spearhead", "harness",
            "pivotal", "endeavor", "realm", "landscape", "foster",
            "encompass", "comprehensive", "intricate", "multifaceted",
            "nuanced", "paramount", "plethora", "myriad", "commendable",
            "noteworthy", "crucial", "vital", "indispensable", "testament",
            "underscores", "underpin", "underpinning", "overarching",
            "proliferation", "burgeoning", "quintessential",
        ],
        banned_phrases=[
            "in conclusion",
            "in summary",
            "to summarize",
            "it's worth noting",
            "it is worth noting",
            "it's important to note",
            "it bears mentioning",
            "needless to say",
            "at the end of the day",
            "in today's rapidly evolving",
            "in the ever-evolving",
            "dive deep into",
            "deep dive into",
            "let's delve into",
            "without further ado",
            "in this article, we will",
            "in this blog post",
        ],
        sentence_start_flags=[
            "Furthermore,",
            "Moreover,",
            "Additionally,",
            "Consequently,",
            "Nevertheless,",
            "Notably,",
            "Importantly,",
            "Interestingly,",
            "Significantly,",
            "Essentially,",
            "Fundamentally,",
            "Ultimately,",
        ],
        max_exclamations=1,
        require_contractions=True,
        max_paragraph_repeat_starts=2,
        rules=[
            "Remove ALL em-dashes. Replace with commas, full stops, or rephrase.",
            "Remove semicolons used to connect sentences. Use a full stop or restructure.",
            "Remove all emojis.",
            "Replace every banned word with a plain alternative.",
            "Use contractions: write it's, we're, you'll, don't, can't.",
            "Use active voice. Kill passive constructions.",
            "Maximum {max_exclamations} exclamation mark(s) in the entire post.",
            "Never open a section with banned phrases like 'In conclusion' or 'In summary'.",
            "Keep technical accuracy. Do not change code blocks.",
            "Return only the rewritten blog post, no commentary, no preamble.",
            "Vary paragraph openings. No more than {max_paragraph_repeat_starts} paragraphs in a row can start with the same word.",
            "Do not start sentences with flagged transition words like 'Furthermore,' or 'Moreover,'.",
            "Write like a human engineer talking to peers. Be direct and opinionated.",
            "Prefer short sentences. If a sentence is over 30 words, break it up.",
        ],
    )


def _load_yaml(path: Path) -> Dict:
    """Parse a YAML file. Tries pyyaml first, falls back to basic parsing."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        # Minimal YAML parsing for simple key-value + list structures
        return _mini_yaml_parse(text)


def _mini_yaml_parse(text: str) -> Dict:
    """Extremely simple YAML parser for our specific schema only."""
    import re
    result: Dict = {}
    current_key: Optional[str] = None
    current_list: Optional[List] = None

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Top-level key with scalar value: key: value
        m = re.match(r'^(\w[\w_]*)\s*:\s*(.+)$', line)
        if m and not stripped.startswith("-"):
            if current_key and current_list is not None:
                result[current_key] = current_list
            key, val = m.group(1), m.group(2).strip()
            # Check if value is a number or boolean
            if val.lower() in ("true", "yes"):
                result[key] = True
            elif val.lower() in ("false", "no"):
                result[key] = False
            elif val.isdigit():
                result[key] = int(val)
            else:
                result[key] = val
            current_key = None
            current_list = None
            continue

        # Top-level key starting a list: key:
        m = re.match(r'^(\w[\w_]*)\s*:\s*$', line)
        if m:
            if current_key and current_list is not None:
                result[current_key] = current_list
            current_key = m.group(1)
            current_list = []
            continue

        # List item:   - value
        if stripped.startswith("- ") and current_key is not None and current_list is not None:
            val = stripped[2:].strip().strip('"').strip("'")
            current_list.append(val)
            continue

    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def _dict_to_rules(data: Dict) -> HumanizerRules:
    """Convert a parsed YAML dict to a HumanizerRules dataclass."""
    defaults = get_default_rules()
    return HumanizerRules(
        banned_words=data.get("banned_words", defaults.banned_words),
        banned_phrases=data.get("banned_phrases", defaults.banned_phrases),
        sentence_start_flags=data.get("sentence_start_flags", defaults.sentence_start_flags),
        max_exclamations=int(data.get("max_exclamations", defaults.max_exclamations)),
        require_contractions=bool(data.get("require_contractions", defaults.require_contractions)),
        max_paragraph_repeat_starts=int(data.get("max_paragraph_repeat_starts", defaults.max_paragraph_repeat_starts)),
        rules=data.get("rules", defaults.rules),
    )


def load_rules(path: Optional[str] = None) -> HumanizerRules:
    """
    Load humanizer rules from the highest-priority source.

    Resolution order:
        1. Explicit *path* argument
        2. ``HUMANIZER_RULES`` environment variable
        3. ``humanizer_rules.yml`` in the current working directory
        4. Built-in ``humanizer_rules.default.yml`` shipped with the package
        5. Hardcoded defaults (if YAML is missing from the wheel)
    """
    # 1. Explicit path
    if path:
        p = Path(path)
        if p.exists():
            return _dict_to_rules(_load_yaml(p))

    # 2. Env var
    env_path = os.environ.get("HUMANIZER_RULES", "")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return _dict_to_rules(_load_yaml(p))

    # 3. CWD
    cwd_yaml = Path.cwd() / "humanizer_rules.yml"
    if cwd_yaml.exists():
        return _dict_to_rules(_load_yaml(cwd_yaml))

    # 4. Package default
    pkg_yaml = Path(__file__).parent / "humanizer_rules.default.yml"
    if pkg_yaml.exists():
        return _dict_to_rules(_load_yaml(pkg_yaml))

    # 5. Hardcoded
    return get_default_rules()


def build_system_prompt(rules: HumanizerRules) -> str:
    """
    Generate the HUMANIZER_SYSTEM string dynamically from rules.

    This is what gets sent as the system prompt to the LLM during
    the humanizer pass.
    """
    lines = [
        "You are a senior technical editor. Your job is to rewrite AI-generated "
        "blog posts so they read like they were written by a smart human engineer "
        "who actually ships code.",
        "",
        "Rules (non-negotiable):",
    ]

    for i, rule in enumerate(rules.rules, 1):
        # Substitute template variables
        rendered = rule.format(
            max_exclamations=rules.max_exclamations,
            max_paragraph_repeat_starts=rules.max_paragraph_repeat_starts,
        )
        lines.append(f"{i}. {rendered}")

    # Append the banned words list
    if rules.banned_words:
        lines.append("")
        lines.append(
            "Banned words (replace with plain alternatives): "
            + ", ".join(rules.banned_words)
        )

    # Append banned phrases
    if rules.banned_phrases:
        lines.append("")
        lines.append(
            "Banned phrases (never use): "
            + "; ".join(f'"{p}"' for p in rules.banned_phrases)
        )

    # Append sentence start flags
    if rules.sentence_start_flags:
        lines.append("")
        lines.append(
            "Do not start sentences with: "
            + ", ".join(rules.sentence_start_flags)
        )

    return "\n".join(lines)
