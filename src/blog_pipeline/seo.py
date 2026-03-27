"""
SEO analysis module — pure-Python scoring for blog content.

No external dependencies. All heuristics work on raw markdown text.

Usage::

    from blog_pipeline.seo import score_seo
    result = score_seo(content, primary_keyword="deploy")
    print(result["seo_score"])  # 0-100
"""

import re
from typing import Dict, List, Optional


# ── Syllable counting (pure Python) ─────────────────────────────────────────

_VOWELS = set("aeiouy")
_SILENT_E = re.compile(r"[^l]e$", re.IGNORECASE)
_DOUBLE_VOWEL = re.compile(r"[aeiouy]{2}", re.IGNORECASE)


def _count_syllables(word: str) -> int:
    """Estimate syllable count for an English word."""
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1

    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in _VOWELS
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel

    # Silent e
    if word.endswith("e") and count > 1:
        count -= 1
    # -le at end is a syllable
    if word.endswith("le") and len(word) > 2 and word[-3] not in _VOWELS:
        count += 1
    # -ed at end (not creating new syllable for most words)
    if word.endswith("ed") and len(word) > 3 and word[-3] not in "dt":
        count = max(count - 1, 1) if count > 1 else count

    return max(count, 1)


# ── Readability ──────────────────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Remove markdown formatting, code blocks, and HTML comments."""
    # Code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Inline code
    text = re.sub(r"`[^`]+`", "", text)
    # HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Images / links
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # Headings markers
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Bold / italic
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    return text


def _get_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    clean = _strip_markdown(text)
    # Split on sentence-ending punctuation followed by space or newline
    raw = re.split(r"(?<=[.!?])\s+", clean)
    return [s.strip() for s in raw if s.strip() and len(s.strip()) > 5]


def _get_words(text: str) -> List[str]:
    """Extract words from text."""
    clean = _strip_markdown(text)
    return re.findall(r"\b[a-zA-Z']+\b", clean)


def calculate_readability(content: str) -> Dict:
    """
    Compute Flesch-Kincaid grade level and reading ease.

    Returns::

        {
            "flesch_reading_ease": float,   # 0-100 (higher = easier)
            "flesch_kincaid_grade": float,   # US grade level
            "total_words": int,
            "total_sentences": int,
            "total_syllables": int,
            "avg_words_per_sentence": float,
            "avg_syllables_per_word": float,
        }
    """
    sentences = _get_sentences(content)
    words = _get_words(content)

    total_words = len(words)
    total_sentences = max(len(sentences), 1)
    total_syllables = sum(_count_syllables(w) for w in words)

    avg_wps = total_words / total_sentences
    avg_spw = total_syllables / max(total_words, 1)

    # Flesch Reading Ease
    fre = 206.835 - (1.015 * avg_wps) - (84.6 * avg_spw)
    fre = max(0.0, min(100.0, fre))

    # Flesch-Kincaid Grade Level
    fk_grade = (0.39 * avg_wps) + (11.8 * avg_spw) - 15.59

    return {
        "flesch_reading_ease": round(fre, 1),
        "flesch_kincaid_grade": round(max(0, fk_grade), 1),
        "total_words": total_words,
        "total_sentences": total_sentences,
        "total_syllables": total_syllables,
        "avg_words_per_sentence": round(avg_wps, 1),
        "avg_syllables_per_word": round(avg_spw, 2),
    }


# ── Keyword density ─────────────────────────────────────────────────────────

def check_keyword_density(content: str, keyword: str) -> float:
    """
    Return keyword density as a percentage (0.0 - 100.0).

    Checks for the keyword (case-insensitive) as a whole-word match.
    """
    if not keyword:
        return 0.0
    words = _get_words(content)
    if not words:
        return 0.0
    pattern = re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE)
    clean = _strip_markdown(content)
    matches = len(pattern.findall(clean))
    return round((matches / len(words)) * 100, 2)


# ── Heading analysis ─────────────────────────────────────────────────────────

def analyze_headings(content: str) -> Dict:
    """
    Check heading hierarchy in markdown content.

    Returns::

        {
            "h1_count": int,
            "h2_count": int,
            "h3_count": int,
            "h4_count": int,
            "has_proper_hierarchy": bool,  # no skipped levels
            "headings": list[dict],         # [{level, text}]
        }
    """
    headings = []
    for line in content.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            headings.append({"level": level, "text": m.group(2).strip()})

    counts = {f"h{i}_count": 0 for i in range(1, 5)}
    for h in headings:
        key = f"h{h['level']}_count"
        if key in counts:
            counts[key] += 1

    # Check hierarchy: no skipping levels (e.g., h1 then h3 without h2)
    proper = True
    if headings:
        levels = [h["level"] for h in headings]
        for i in range(1, len(levels)):
            if levels[i] > levels[i - 1] + 1:
                proper = False
                break

    return {
        **counts,
        "has_proper_hierarchy": proper,
        "headings": headings,
    }


# ── Link analysis ────────────────────────────────────────────────────────────

def analyze_links(content: str) -> Dict:
    """
    Count and classify links in markdown content.

    Returns::

        {
            "internal_links": int,
            "external_links": int,
            "total_links": int,
            "links": list[dict],  # [{text, url, is_internal}]
        }
    """
    link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
    links = []
    for m in link_pattern.finditer(content):
        text, url = m.group(1), m.group(2)
        is_internal = url.startswith("/") or url.startswith("#")
        links.append({"text": text, "url": url, "is_internal": is_internal})

    internal = sum(1 for l in links if l["is_internal"])
    external = len(links) - internal

    return {
        "internal_links": internal,
        "external_links": external,
        "total_links": len(links),
        "links": links,
    }


# ── Meta description generator ──────────────────────────────────────────────

def generate_meta_description(content: str, keyword: str = "") -> str:
    """
    Extract or generate a meta description (120-160 chars) from content.

    Takes the first non-heading, non-empty paragraph and truncates it.
    Prefers paragraphs containing the keyword.
    """
    clean = _strip_markdown(content)
    paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]
    paragraphs = [p for p in paragraphs if not p.startswith("#") and len(p) > 30]

    if not paragraphs:
        return ""

    # Prefer a paragraph containing the keyword
    chosen = paragraphs[0]
    if keyword:
        kw_lower = keyword.lower()
        for p in paragraphs:
            if kw_lower in p.lower():
                chosen = p
                break

    # Collapse whitespace
    chosen = re.sub(r"\s+", " ", chosen).strip()

    # Truncate to 155 chars at a word boundary
    if len(chosen) > 155:
        truncated = chosen[:155]
        last_space = truncated.rfind(" ")
        if last_space > 100:
            truncated = truncated[:last_space]
        chosen = truncated.rstrip(".,;:!?") + "..."

    # Ensure at least 120 chars if possible
    if len(chosen) < 120 and len(paragraphs) > 1:
        # Try appending from next paragraph
        extra = re.sub(r"\s+", " ", paragraphs[1]).strip()
        combined = chosen.rstrip(".") + ". " + extra
        if len(combined) > 155:
            combined = combined[:155]
            last_space = combined.rfind(" ")
            if last_space > 100:
                combined = combined[:last_space]
            combined = combined.rstrip(".,;:!?") + "..."
        chosen = combined

    return chosen


# ── Composite SEO scorer ────────────────────────────────────────────────────

def score_seo(
    content: str,
    primary_keyword: str = "",
    all_keywords: Optional[List[str]] = None,
) -> Dict:
    """
    Score blog content for SEO (0-100).

    Factors:
        - Word count (target 800-2000): 20 pts
        - Heading structure: 15 pts
        - Keyword density (1-3% target): 20 pts
        - Readability (grade 6-12): 15 pts
        - Internal links present: 10 pts
        - Meta description quality: 10 pts
        - Keyword in headings: 10 pts

    Returns dict with ``seo_score`` and detailed breakdown.
    """
    keywords = all_keywords or []
    if primary_keyword and primary_keyword not in keywords:
        keywords = [primary_keyword] + keywords

    readability = calculate_readability(content)
    heading_info = analyze_headings(content)
    link_info = analyze_links(content)
    meta = generate_meta_description(content, primary_keyword)

    score = 0
    breakdown = {}

    # 1. Word count (20 pts)
    wc = readability["total_words"]
    if 800 <= wc <= 2000:
        wc_score = 20
    elif 600 <= wc < 800:
        wc_score = 14
    elif 2000 < wc <= 3000:
        wc_score = 16
    elif 400 <= wc < 600:
        wc_score = 8
    elif wc > 3000:
        wc_score = 12
    else:
        wc_score = 4
    score += wc_score
    breakdown["word_count"] = {"score": wc_score, "max": 20, "value": wc}

    # 2. Heading structure (15 pts)
    h2 = heading_info["h2_count"]
    h_score = 0
    if h2 >= 3:
        h_score += 10
    elif h2 >= 2:
        h_score += 7
    elif h2 >= 1:
        h_score += 4
    if heading_info["has_proper_hierarchy"]:
        h_score += 5
    h_score = min(h_score, 15)
    score += h_score
    breakdown["headings"] = {"score": h_score, "max": 15, "h2_count": h2}

    # 3. Keyword density (20 pts)
    kw_score = 0
    if primary_keyword:
        density = check_keyword_density(content, primary_keyword)
        if 1.0 <= density <= 3.0:
            kw_score = 20
        elif 0.5 <= density < 1.0 or 3.0 < density <= 4.0:
            kw_score = 12
        elif 0.1 <= density < 0.5:
            kw_score = 6
        elif density > 4.0:
            kw_score = 4  # keyword stuffing
        else:
            kw_score = 2
        breakdown["keyword_density"] = {"score": kw_score, "max": 20, "density": density}
    else:
        kw_score = 10  # no keyword specified, give partial credit
        breakdown["keyword_density"] = {"score": kw_score, "max": 20, "density": None}
    score += kw_score

    # 4. Readability (15 pts)
    grade = readability["flesch_kincaid_grade"]
    if 6 <= grade <= 12:
        r_score = 15
    elif 4 <= grade < 6 or 12 < grade <= 14:
        r_score = 10
    elif grade < 4:
        r_score = 5
    else:
        r_score = 5
    score += r_score
    breakdown["readability"] = {"score": r_score, "max": 15, "grade": grade}

    # 5. Internal links (10 pts)
    il = link_info["internal_links"]
    if il >= 3:
        l_score = 10
    elif il >= 1:
        l_score = 6
    else:
        l_score = 0
    score += l_score
    breakdown["internal_links"] = {"score": l_score, "max": 10, "count": il}

    # 6. Meta description (10 pts)
    m_score = 0
    if meta:
        if 120 <= len(meta) <= 160:
            m_score = 10
        elif 80 <= len(meta) < 120:
            m_score = 6
        else:
            m_score = 3
    score += m_score
    breakdown["meta_description"] = {"score": m_score, "max": 10, "length": len(meta)}

    # 7. Keyword in headings (10 pts)
    kh_score = 0
    if primary_keyword:
        kw_lower = primary_keyword.lower()
        heading_texts = [h["text"].lower() for h in heading_info["headings"]]
        if any(kw_lower in ht for ht in heading_texts):
            kh_score = 10
        # Check secondary keywords too
        elif keywords:
            for kw in keywords[1:]:
                if any(kw.lower() in ht for ht in heading_texts):
                    kh_score = 5
                    break
    else:
        kh_score = 5  # partial credit when no keyword specified
    score += kh_score
    breakdown["keyword_in_headings"] = {"score": kh_score, "max": 10}

    return {
        "seo_score": min(100, max(0, score)),
        "breakdown": breakdown,
        "readability": readability,
        "headings": heading_info,
        "links": link_info,
        "meta_description": meta,
    }
