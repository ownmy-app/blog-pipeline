# blog-pipeline

Built by the [Nometria](https://nometria.com) team. We help developers take apps built with AI tools (Lovable, Bolt, Base44, Replit) to production — handling deployment to AWS, security, scaling, and giving you full code ownership. [Learn more →](https://nometria.com)

AI blog generator that doesn't sound like AI.

7-pass pipeline with multi-LLM support (Anthropic, OpenAI, LiteLLM), pluggable
storage backends (filesystem, Supabase, PostgreSQL, WordPress, Notion, Contentful),
a configurable humanizer that strips AI writing tells, SEO analysis, AI content
detection scoring, and a quality audit gate.

---

## Quick Start

```bash
pip install blog-pipeline
export ANTHROPIC_API_KEY=sk-ant-...
blog-generate --count 5 --niche "developer tooling and SaaS"
```

That's it. Five humanized, SEO-scored blog posts land in `./blogs/`.

---

## Install

```bash
pip install blog-pipeline
```

With optional providers/backends:

```bash
pip install "blog-pipeline[openai]"         # OpenAI support
pip install "blog-pipeline[litellm]"        # LiteLLM (any provider)
pip install "blog-pipeline[postgres]"       # PostgreSQL backend
pip install "blog-pipeline[all]"            # everything
```

From source (for development):

```bash
git clone https://github.com/nometria/blog-pipeline
cd blog-pipeline
pip install -e ".[dev]"
```

---

## Features

- **Multi-LLM**: Anthropic (default), OpenAI, or any provider via LiteLLM -- switch with one env var
- **Multi-backend**: Write to filesystem, Supabase, PostgreSQL, WordPress, Notion, or Contentful
- **Humanizer**: Configurable rule engine that strips 50+ banned words, enforces contractions, active voice, paragraph variety, and more -- before/after AI detection scoring
- **AI detection**: Pure-Python heuristic scorer (0.0 = human, 1.0 = AI) with weighted checks for sentence uniformity, banned word density, passive voice, em-dash usage, and more
- **SEO analysis**: Flesch-Kincaid readability, keyword density, heading structure, meta quality -- scored out of 100
- **Audit gate**: Composite scoring (quality 60% + AI detection 20% + SEO 20%) with optional auto-unpublish for weak posts
- **GitHub Action**: Scheduled weekly generation with manual trigger -- see below

---

## Pipeline Passes

| Pass | What it does |
|------|-------------|
| 0 | Fetch existing titles from backend (prevents duplicates) |
| 1 | Identify new topics (skips anything already written) |
| 2 | Plan structure per topic (comparison / deep-dive / case-study / how-to / opinion) |
| 3 | Generate full markdown content |
| 4 | Humanizer pass with AI detection scoring (before/after) |
| 5 | Add internal links across all posts |
| 6 | Push to configured backend + update local registry |
| 7 | Audit gate: score posts, reject weak ones (optional, `--audit`) |

---

## GitHub Action

Add `.github/workflows/generate.yml` to your repo for automated weekly blog generation. See the full workflow in this repo, or copy the example below.

### Minimal workflow

```yaml
name: Generate Blogs

on:
  schedule:
    - cron: "0 9 * * 1"   # Weekly Monday 9am UTC
  workflow_dispatch:
    inputs:
      count:
        description: "Number of posts"
        default: "5"
      niche:
        description: "Topic niche"
        default: "developer tooling and infrastructure"
      passes:
        description: "Pipeline passes (e.g. 1-6, 1-7)"
        default: "1-6"
      backend:
        description: "Storage backend"
        default: "filesystem"
        type: choice
        options: [filesystem, supabase, postgres, wordpress, notion, contentful]

permissions:
  contents: write

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pip install "blog-pipeline[all]"

      - name: Generate
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          BLOG_BACKEND: ${{ inputs.backend || 'filesystem' }}
          # Add other backend secrets as needed:
          # SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          # SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: |
          blog-generate \
            --passes "${{ inputs.passes || '1-6' }}" \
            --count "${{ inputs.count || '5' }}" \
            --niche "${{ inputs.niche || 'developer tooling and infrastructure' }}" \
            --audit --audit-threshold 50

      - name: Commit generated blogs
        if: ${{ inputs.backend == 'filesystem' || inputs.backend == '' }}
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add blogs/ || true
          git diff --cached --quiet || git commit -m "chore: generate blog posts [$(date -u +%Y-%m-%d)]" && git push

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: blog-generation-report
          path: blogs/_registry.json
          if-no-files-found: ignore
```

### Required secrets

| Secret | When needed |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Using Anthropic (default) |
| `OPENAI_API_KEY` | Using OpenAI (`LLM_PROVIDER=openai`) |
| `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` | Supabase backend |
| `POSTGRES_DSN` | PostgreSQL backend |
| `WP_URL` + `WP_USER` + `WP_APP_PASSWORD` | WordPress backend |
| `NOTION_API_KEY` + `NOTION_DATABASE_ID` | Notion backend |
| `CONTENTFUL_SPACE_ID` + `CONTENTFUL_MGMT_TOKEN` | Contentful backend |

### Manual trigger

Go to **Actions > Generate Blogs > Run workflow** to generate on demand with custom inputs for count, niche, passes, and backend.

---

## LLM Providers

Set `LLM_PROVIDER` and (optionally) `LLM_MODEL`:

| Provider | Env var | Default model | Package |
|----------|---------|---------------|---------|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | `claude-opus-4-5` | included |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` | `pip install "blog-pipeline[openai]"` |
| `litellm` | varies by model | `claude-opus-4-5` | `pip install "blog-pipeline[litellm]"` |

```bash
# Use OpenAI instead of Anthropic
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export LLM_MODEL=gpt-4o
blog-generate --count 3
```

Use the LLM abstraction in your own code:

```python
from blog_pipeline import ask_llm
response = ask_llm("Explain Docker in 3 sentences", system="Be concise")
```

---

## Storage Backends

Set `BLOG_BACKEND` to choose where posts are stored:

| Backend | Env var | Extra deps | Description |
|---------|---------|-----------|-------------|
| `filesystem` (default) | `BLOGS_DIR` | none | Markdown files + `_metadata.json` |
| `supabase` | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | none | PostgREST API via urllib |
| `postgres` | `POSTGRES_DSN` | `psycopg2` | Direct PostgreSQL connection |
| `wordpress` | `WP_URL`, `WP_USER`, `WP_APP_PASSWORD` | none | WP REST API via urllib |
| `notion` | `NOTION_API_KEY`, `NOTION_DATABASE_ID` | none | Notion API via urllib |
| `contentful` | `CONTENTFUL_SPACE_ID`, `CONTENTFUL_MGMT_TOKEN` | none | Contentful Management API |

```bash
# Push to WordPress
export BLOG_BACKEND=wordpress
export WP_URL=https://myblog.com
export WP_USER=admin
export WP_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
blog-generate --passes 1-6 --count 3
```

Use backends programmatically:

```python
from blog_pipeline import get_backend
backend = get_backend("filesystem")   # or "supabase", "wordpress", etc.
backend.push_post({"title": "Hello", "content": "# Hello\n\nWorld.", "published": True})
titles = backend.fetch_titles()
```

---

## The Humanizer

The humanizer enforces strict rules to remove AI writing tells. Rules are
configurable via YAML.

### Default rules include

- 50+ banned words (leverage, seamless, robust, delve, paradigm, etc.)
- 17+ banned phrases ("in conclusion", "it's worth noting", "dive deep into")
- 12+ flagged sentence starters (Furthermore, Moreover, Additionally)
- No em-dashes, no semicolons connecting sentences, no emojis
- Contractions required (it's, we're, don't)
- Active voice only
- Max 1 exclamation mark per post
- Paragraph opening variety enforcement

### Customize rules

Create a `humanizer_rules.yml` in your project root or set `HUMANIZER_RULES`:

```yaml
banned_words:
  - "leverage"
  - "synergy"
  - "my-custom-banned-word"
max_exclamations: 2
require_contractions: true
```

### Standalone usage

```python
from blog_pipeline import humanize_post, check_banned_words

clean = humanize_post(my_ai_draft)
issues = check_banned_words(clean)
```

### With AI detection scoring

```python
from blog_pipeline.humanizer import humanize_post_scored

result = humanize_post_scored(my_draft)
print(f"AI score: {result['ai_score_before']:.2f} -> {result['ai_score_after']:.2f}")
print(f"Improvement: {result['improvement']:.2f}")
print(result["content"])
```

---

## AI Detection

Heuristic-based AI content detector. Pure Python, no external API calls.

| Heuristic | Weight |
|-----------|--------|
| Banned word density | 25% |
| Sentence uniformity | 20% |
| Paragraph opening variety | 15% |
| Passive voice ratio | 15% |
| Sentence length variance | 10% |
| Em-dash density | 10% |
| Exclamation density | 5% |

```python
from blog_pipeline import score_ai

result = score_ai(content)
print(f"AI score: {result['ai_score']:.2f}")  # 0.0 = human, 1.0 = AI
for flag in result["flags"]:
    print(f"  - {flag}")
```

---

## SEO Analysis

Built-in SEO scoring with Flesch-Kincaid readability (pure Python syllable counting).

```python
from blog_pipeline import score_seo, calculate_readability

seo = score_seo(content, primary_keyword="deploy")
print(f"SEO score: {seo['seo_score']}/100")

readability = calculate_readability(content)
print(f"Grade level: {readability['flesch_kincaid_grade']}")
```

SEO factors scored: word count (20pts), heading structure (15pts),
keyword density (20pts), readability (15pts), internal links (10pts),
meta description quality (10pts), keyword in headings (10pts).

---

## Audit

Score existing blog posts and optionally unpublish weak ones.

```bash
# Score all blogs
blog-audit --dir blogs

# Include SEO scoring
blog-audit --seo

# Unpublish posts below threshold via backend
blog-audit --min-score 60 --unpublish

# Re-humanize weak posts
blog-audit --fix

# JSON output
blog-audit --json
```

Composite scoring: quality 60% + AI detection 20% + SEO 20%.

```python
from blog_pipeline.audit import score_post, run_audit
from pathlib import Path

result = score_post(content, seo=True)
print(f"Score: {result['score']}, Grade: {result['grade']}")

results = run_audit(Path("blogs"), min_score=60, seo=True)
```

---

## CLI Reference

### blog-generate

```
blog-generate [OPTIONS]

Options:
  --passes RANGE       Pipeline passes to run (default: 1-6)
  --count N            Number of blogs to generate (default: 5)
  --niche TEXT         Topic niche (default: "developer tooling and infrastructure")
  --audit              Enable Pass 7 audit gate
  --audit-threshold N  Minimum audit score to keep a post (default: 50)
```

### blog-audit

```
blog-audit [OPTIONS]

Options:
  --dir PATH           Blog directory (default: blogs)
  --min-score N        Minimum score threshold (default: 50)
  --seo                Include SEO scoring
  --unpublish          Unpublish posts below threshold via backend
  --fix                Re-humanize posts below threshold
  --json               Output as JSON
```

### blog-humanize

```
blog-humanize [FILE] [OPTIONS]

Arguments:
  FILE                 Markdown file (default: stdin)

Options:
  --check-only         Only report AI tells, don't rewrite
  --in-place           Overwrite input file
  --score              Show AI detection scores
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | no | `anthropic` | LLM provider: anthropic, openai, litellm |
| `LLM_MODEL` | no | per-provider | Model override |
| `ANTHROPIC_API_KEY` | if anthropic | | Anthropic API key |
| `OPENAI_API_KEY` | if openai | | OpenAI API key |
| `BLOG_BACKEND` | no | `filesystem` | Storage backend |
| `BLOGS_DIR` | no | `./blogs` | Local blog directory |
| `BLOG_AUTHOR` | no | `Your Team` | Default author name |
| `BLOG_AUTHOR_TITLE` | no | `Engineering & Product` | Default author title |
| `BLOG_AUTHOR_IMAGE` | no | | Author image URL |
| `HUMANIZER_RULES` | no | | Path to custom rules YAML |
| `SUPABASE_URL` | if supabase | | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | if supabase | | Supabase service key |
| `SUPABASE_BLOGS_TABLE` | no | `blogs` | Supabase table name |
| `POSTGRES_DSN` | if postgres | | PostgreSQL connection string |
| `WP_URL` | if wordpress | | WordPress site URL |
| `WP_USER` | if wordpress | | WordPress username |
| `WP_APP_PASSWORD` | if wordpress | | WordPress application password |
| `NOTION_API_KEY` | if notion | | Notion integration token |
| `NOTION_DATABASE_ID` | if notion | | Notion database ID |
| `CONTENTFUL_SPACE_ID` | if contentful | | Contentful space ID |
| `CONTENTFUL_MGMT_TOKEN` | if contentful | | Contentful management token |
| `CONTENTFUL_ENVIRONMENT` | no | `master` | Contentful environment |

---

## API Reference

### Core

```python
from blog_pipeline import (
    ask_llm,                # LLM abstraction (anthropic/openai/litellm)
    get_backend,            # Backend factory
    humanize_post,          # Humanize content
    check_banned_words,     # Check for AI tells
    check_ai_tells,         # Detailed AI tell analysis
    humanize_post_scored,   # Humanize with before/after AI scores
    score_ai,               # AI detection scoring
    score_seo,              # SEO scoring
    calculate_readability,  # Flesch-Kincaid readability
    check_keyword_density,  # Keyword density check
    load_rules,             # Load humanizer rules
    build_system_prompt,    # Build dynamic system prompt
    HumanizerRules,         # Rules dataclass
)
```

### Backends

All backends implement the `BlogBackend` interface:

```python
class BlogBackend:
    def fetch_titles(self, limit=500) -> list[str]: ...
    def push_post(self, post: dict) -> bool: ...
    def unpublish(self, title: str) -> bool: ...
    def list_posts(self, published_only=False) -> list[dict]: ...
```

Post dict shape:

```python
{
    "title":        str,
    "content":      str,       # markdown
    "author":       str,
    "author_title": str,
    "author_image": str,
    "category":     str,
    "tags":         list[str],
    "seo_keywords": list[str],
    "cover_image":  str,
    "published":    bool,
    "created_at":   str,       # ISO-8601
}
```

---

## Output Files

| File | Description |
|------|-------------|
| `blogs/<slug>.md` | Humanized markdown blog posts |
| `blogs/_metadata.json` | Filesystem backend metadata sidecar |
| `blogs/_topics.json` | Topic cache (pass 1) |
| `blogs/_plans.json` | Structure plans (pass 2) |
| `blogs/_registry.json` | Push tracking registry (pass 6) |

---

## Development

```bash
git clone https://github.com/nometria/blog-pipeline
cd blog-pipeline
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT

