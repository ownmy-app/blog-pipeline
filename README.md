# blog-pipeline

> AI blog generator that doesn't sound like AI.

6-pass Claude API pipeline with a built-in humanizer, topic deduplication,
internal linking, and Supabase sync. The humanizer is the key differentiator —
it enforces a strict writing ruleset that removes every common AI tell.

---

## Quick start

```bash
# Clone and install
git clone https://github.com/ownmy-app/blog-pipeline
cd blog-pipeline
pip install -e .

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Generate 5 blog posts
blog-generate --count 5 --niche "developer tooling and SaaS"

# Re-humanize existing drafts only
blog-generate --passes 4

# Run tests
pytest tests/ -v
```

Required environment variables:
```bash
ANTHROPIC_API_KEY=sk-ant-...          # required

# Optional (for Supabase sync in pass 0 and 6)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
BLOG_SITE_URL=https://yourblog.com
```

---

## Passes

| Pass | What it does |
|------|-------------|
| 0 | Fetches existing titles from Supabase (prevents duplicates) |
| 1 | Identifies new topics (skips anything already written) |
| 2 | Plans structure per topic (comparison / deep-dive / case-study / how-to / opinion) |
| 3 | Generates full markdown content |
| 4 | **Humanizer** — strips AI tells (see below) |
| 5 | Adds internal links across all posts |
| 6 | Pushes to Supabase + updates local registry |

---

## The Humanizer

Pass 4 enforces these rules on every post:

- **Banned words**: leverage, seamless, robust, cutting-edge, game-changer,
  revolutionize, synergy, paradigm, transformative, unlock, delve, streamline,
  elevate, empower, holistic, utilize, facilitate, innovative
- **No em-dashes** (—) — replaced with commas or full stops
- **No semicolons** connecting sentences
- **No emojis**
- **Contractions required**: it's, we're, you'll, don't
- **Active voice only**
- **Max 1 exclamation mark** per post
- No "In conclusion / In summary" section openers

Use the humanizer standalone:

```python
from blog_pipeline.humanizer import humanize_post
clean = humanize_post(my_ai_draft)
```

---

## Setup

```bash
git clone https://github.com/ownmy-app/blog-pipeline
cd blog-pipeline
pip install -e .
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
```

---

## Run

```bash
# Full pipeline: generate 5 blogs
blog-generate --passes 1-6 --count 5 --niche "developer tooling and SaaS"

# Re-humanize existing drafts only
blog-generate --passes 4

# Push already-written files to Supabase
blog-generate --passes 6

# Generate content without pushing
blog-generate --passes 1-5 --count 3
```

---

## Output

- `blogs/<slug>.md` — humanized markdown files
- `blogs/_topics.json` — topic cache
- `blogs/_plans.json` — structure plans
- `blogs/_registry.json` — pushed blog tracking

---

## Immediate next steps
1. Make the humanizer prompt configurable via `HUMANIZER_RULES` env / YAML
2. Add `--audit` flag: re-score all pushed blogs and unpublish weak ones
3. Add SEO scoring pass (keyword density check, meta description generation)
4. Package as a GitHub Action: auto-generate blogs on schedule

---

## Commercial viability
- Package the humanizer as a standalone API: `POST /humanize` → clean post
- Charge per post ($0.10–0.50) or monthly flat ($49–149)
- Differentiator: "the only AI blog writer that bans its own clichés by design"
- Add AI-detector score before/after to prove improvement

---

## Example output

Running `pytest tests/ -v`:

```
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-9.0.2, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: /tmp/ownmy-releases/blog-pipeline
configfile: pyproject.toml
plugins: anyio-4.12.1, cov-7.1.0
collecting ... collected 4 items

tests/test_pipeline.py::test_check_banned_words_flags_corporate_speak PASSED [ 25%]
tests/test_pipeline.py::test_check_banned_words_passes_clean_text PASSED [ 50%]
tests/test_pipeline.py::test_check_banned_words_flags_em_dash_clusters FAILED [ 75%]
tests/test_pipeline.py::test_humanize_post_returns_string PASSED         [100%]

============================= short test summary info ==========================
FAILED tests/test_pipeline.py::test_check_banned_words_flags_em_dash_clusters
========================= 1 failed, 3 passed in 0.43s ==========================
```

See `examples/sample-post.md` for a realistic humanized blog post produced by the pipeline.
