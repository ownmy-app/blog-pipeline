"""
AI content detector — heuristic scoring to estimate AI-likeness.

Pure Python, no external dependencies. Returns a score from 0.0 (human)
to 1.0 (very likely AI-generated) based on multiple linguistic signals.

Usage::

    from blog_pipeline.ai_detector import score_ai
    result = score_ai(content)
    print(result["ai_score"])   # 0.0 - 1.0
    print(result["flags"])      # list of detected issues
"""

import math
import re
import statistics
from typing import Any, Dict, List, Optional


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks so they don't skew analysis."""
    return re.sub(r"```[\s\S]*?```", "", text)


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting."""
    text = _strip_code_blocks(text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    text = re.sub(r"`[^`]+`", "", text)
    return text


def _get_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    clean = _strip_markdown(text)
    raw = re.split(r"(?<=[.!?])\s+", clean)
    return [s.strip() for s in raw if s.strip() and len(s.strip()) > 5]


def _get_words(text: str) -> List[str]:
    """Extract words from clean text."""
    return re.findall(r"\b[a-zA-Z']+\b", text)


def _get_paragraphs(text: str) -> List[str]:
    """Split into paragraphs (non-empty blocks separated by blank lines)."""
    clean = _strip_code_blocks(text)
    blocks = re.split(r"\n\s*\n", clean)
    paragraphs = []
    for b in blocks:
        b = b.strip()
        if b and not b.startswith("#") and len(b) > 10:
            paragraphs.append(b)
    return paragraphs


# ── Individual heuristics ────────────────────────────────────────────────────

def _banned_word_density(text: str, rules=None) -> float:
    """
    Score 0.0-1.0 based on density of known AI-tell words.
    Weight: 25%
    """
    if rules is None:
        from .humanizer_rules import get_default_rules
        rules = get_default_rules()

    clean = _strip_markdown(text)
    words = _get_words(clean)
    if not words:
        return 0.0

    total = len(words)
    banned_count = 0
    lower_text = clean.lower()
    for bw in rules.banned_words:
        pattern = re.compile(r"\b" + re.escape(bw) + r"\b", re.IGNORECASE)
        banned_count += len(pattern.findall(lower_text))

    # Also check banned phrases
    for bp in rules.banned_phrases:
        if bp.lower() in lower_text:
            banned_count += 3  # phrases are stronger signals

    density = banned_count / total
    # Scale: 0 banned = 0.0, 2%+ density = 1.0
    return min(1.0, density / 0.02)


def _sentence_uniformity(text: str) -> float:
    """
    Score 0.0-1.0 based on how uniform sentence lengths are.
    AI text tends to have very consistent sentence lengths.
    Weight: 20%
    """
    sentences = _get_sentences(text)
    if len(sentences) < 5:
        return 0.0

    lengths = [len(_get_words(s)) for s in sentences]
    if not lengths:
        return 0.0

    mean_len = statistics.mean(lengths)
    if mean_len == 0:
        return 0.0

    stdev = statistics.stdev(lengths) if len(lengths) > 1 else 0
    cv = stdev / mean_len  # coefficient of variation

    # Low CV = uniform = AI-like. Human writing typically has CV > 0.5
    # CV < 0.25 is very uniform (AI), CV > 0.6 is varied (human)
    if cv < 0.2:
        return 1.0
    elif cv < 0.3:
        return 0.8
    elif cv < 0.4:
        return 0.5
    elif cv < 0.5:
        return 0.3
    elif cv < 0.6:
        return 0.15
    else:
        return 0.0


def _paragraph_opening_variety(text: str) -> float:
    """
    Score 0.0-1.0 based on variety of paragraph opening words.
    AI tends to repeat the same opening patterns.
    Weight: 15%
    """
    paragraphs = _get_paragraphs(text)
    if len(paragraphs) < 3:
        return 0.0

    first_words = []
    for p in paragraphs:
        words = _get_words(p)
        if words:
            first_words.append(words[0].lower())

    if not first_words:
        return 0.0

    unique_ratio = len(set(first_words)) / len(first_words)

    # Low unique ratio = repetitive = AI-like
    if unique_ratio < 0.3:
        return 1.0
    elif unique_ratio < 0.5:
        return 0.7
    elif unique_ratio < 0.7:
        return 0.3
    else:
        return 0.0


def _passive_voice_ratio(text: str) -> float:
    """
    Score 0.0-1.0 based on passive voice usage.
    AI text tends to use more passive voice.
    Weight: 15%
    """
    sentences = _get_sentences(text)
    if not sentences:
        return 0.0

    # Simple passive voice detection: "was/were/is/are/been/be + past participle"
    passive_pattern = re.compile(
        r"\b(was|were|is|are|been|be|being|has been|have been|had been|will be|would be)"
        r"\s+(\w+ed|(\w+en))\b",
        re.IGNORECASE,
    )

    passive_count = 0
    for s in sentences:
        if passive_pattern.search(s):
            passive_count += 1

    ratio = passive_count / len(sentences)

    # >30% passive is AI-like, <10% is human-like
    if ratio > 0.35:
        return 1.0
    elif ratio > 0.25:
        return 0.7
    elif ratio > 0.15:
        return 0.4
    elif ratio > 0.08:
        return 0.15
    else:
        return 0.0


def _sentence_length_variance(text: str) -> float:
    """
    Score 0.0-1.0 based on sentence length variance.
    AI text has less variance in sentence length distribution.
    Weight: 10%
    """
    sentences = _get_sentences(text)
    if len(sentences) < 5:
        return 0.0

    lengths = [len(_get_words(s)) for s in sentences]

    # Check for presence of very short (< 5 words) and very long (> 25 words) sentences
    very_short = sum(1 for l in lengths if l < 5)
    very_long = sum(1 for l in lengths if l > 25)

    total = len(lengths)
    short_pct = very_short / total
    long_pct = very_long / total

    # Human text has more variation: both very short and very long sentences
    has_variety = short_pct > 0.05 and long_pct > 0.05

    if has_variety:
        return 0.0  # good variety, human-like

    # Check standard deviation
    stdev = statistics.stdev(lengths) if len(lengths) > 1 else 0
    if stdev < 3:
        return 1.0  # very uniform
    elif stdev < 5:
        return 0.6
    elif stdev < 7:
        return 0.3
    else:
        return 0.0


def _em_dash_density(text: str) -> float:
    """
    Score 0.0-1.0 based on em-dash usage.
    AI (especially Claude) heavily uses em-dashes.
    Weight: 10%
    """
    clean = _strip_code_blocks(text)
    sentences = _get_sentences(text)
    if not sentences:
        return 0.0

    em_count = clean.count("\u2014")
    # Also count double hyphens used as em-dashes
    em_count += len(re.findall(r"(?<!\-)\-\-(?!\-)", clean))

    ratio = em_count / len(sentences)

    # > 0.3 em-dashes per sentence is AI-like
    if ratio > 0.4:
        return 1.0
    elif ratio > 0.25:
        return 0.8
    elif ratio > 0.15:
        return 0.5
    elif ratio > 0.08:
        return 0.2
    else:
        return 0.0


def _exclamation_density(text: str) -> float:
    """
    Score 0.0-1.0 based on exclamation mark usage.
    AI text tends to over-use exclamation marks.
    Weight: 5%
    """
    sentences = _get_sentences(text)
    if not sentences:
        return 0.0

    excl_count = text.count("!")
    ratio = excl_count / len(sentences)

    # > 0.15 exclamation per sentence is excessive
    if ratio > 0.2:
        return 1.0
    elif ratio > 0.1:
        return 0.6
    elif ratio > 0.05:
        return 0.3
    else:
        return 0.0


# ── Composite scorer ─────────────────────────────────────────────────────────

_WEIGHTS = {
    "banned_word_density":       0.25,
    "sentence_uniformity":       0.20,
    "paragraph_opening_variety": 0.15,
    "passive_voice_ratio":       0.15,
    "sentence_length_variance":  0.10,
    "em_dash_density":           0.10,
    "exclamation_density":       0.05,
}


def score_ai(
    content: str,
    rules=None,
) -> Dict[str, Any]:
    """
    Score content for AI-likeness.

    Args:
        content: Markdown blog post content.
        rules:   Optional HumanizerRules instance (for banned word list).

    Returns::

        {
            "ai_score": float,       # 0.0 (human) to 1.0 (AI)
            "breakdown": dict,       # {heuristic_name: {score, weight, weighted}}
            "flags": list[str],      # human-readable issues detected
        }
    """
    if rules is None:
        from .humanizer_rules import get_default_rules
        rules = get_default_rules()

    scores = {
        "banned_word_density":       _banned_word_density(content, rules),
        "sentence_uniformity":       _sentence_uniformity(content),
        "paragraph_opening_variety": _paragraph_opening_variety(content),
        "passive_voice_ratio":       _passive_voice_ratio(content),
        "sentence_length_variance":  _sentence_length_variance(content),
        "em_dash_density":           _em_dash_density(content),
        "exclamation_density":       _exclamation_density(content),
    }

    # Compute weighted total
    weighted_total = 0.0
    breakdown = {}
    for name, raw_score in scores.items():
        w = _WEIGHTS[name]
        weighted = raw_score * w
        weighted_total += weighted
        breakdown[name] = {
            "score": round(raw_score, 3),
            "weight": w,
            "weighted": round(weighted, 3),
        }

    # Generate human-readable flags
    flags: List[str] = []
    if scores["banned_word_density"] > 0.5:
        flags.append("High density of AI-tell words (corporate buzzwords)")
    if scores["sentence_uniformity"] > 0.5:
        flags.append("Sentences are too uniform in length")
    if scores["paragraph_opening_variety"] > 0.5:
        flags.append("Paragraph openings are repetitive")
    if scores["passive_voice_ratio"] > 0.5:
        flags.append("Excessive passive voice usage")
    if scores["sentence_length_variance"] > 0.5:
        flags.append("Low sentence length variety")
    if scores["em_dash_density"] > 0.5:
        flags.append("Heavy em-dash usage (AI tell)")
    if scores["exclamation_density"] > 0.5:
        flags.append("Too many exclamation marks")

    return {
        "ai_score": round(min(1.0, max(0.0, weighted_total)), 3),
        "breakdown": breakdown,
        "flags": flags,
    }
