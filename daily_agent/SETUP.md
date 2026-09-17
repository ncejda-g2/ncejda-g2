# AI Newspaper Setup

The newspaper runs once per day in GitHub Actions. Python owns fetching,
deduplication, validation, state, and README rendering. Focused model calls use
strict structured outputs through the G2 LiteLLM proxy. GPT-5.6 Luna drives the
normal text pipeline; Claude is retained only for the rare article-fetch fallback.

## Prerequisites

1. Python 3.11+
2. G2 LiteLLM proxy access
3. Claude Code CLI for the rare WebFetch fallback when direct article extraction fails

## Install dependencies

```bash
pip install -r requirements.txt
```

The main dependencies are:

- `aiohttp` for asynchronous source and API requests
- `trafilatura` and `beautifulsoup4` for article extraction
- `jsonschema` for validating every direct model response
- `claude-agent-sdk` only for the quality-preserving WebFetch fallback

Direct text calls use `openai/gpt-5.6-luna` on the standard (`default`) service
tier. Reasoning effort is role-specific: low for trending enrichment, medium for
source classification, high for editorial selection/summaries and the comic
critic, and xhigh for the five comic writers. The model can be overridden for a
local experiment with `NEWSPAPER_LUNA_MODEL` and the global
`NEWSPAPER_LUNA_REASONING_EFFORT`; role-specific variables such as
`NEWSPAPER_LUNA_COMEDY_REASONING_EFFORT` take precedence.

## Configure environment variables

Create a gitignored `.env` file in the project root:

```text
LITELLM_BASE_URL=https://llmproxy.g2.com
LITELLM_API_KEY=<your G2 LiteLLM proxy key>
ANTHROPIC_BASE_URL=https://llmproxy.g2.com/anthropic
ANTHROPIC_API_KEY=<the same G2 LiteLLM proxy key>
GITHUB_TOKEN=<optional GitHub token for higher public API rate limits>
```

Normal chat and image calls use `LITELLM_BASE_URL` and `LITELLM_API_KEY`.
The Anthropic variables are needed only if direct article extraction fails and
the targeted Claude Code WebFetch fallback runs.

GitHub Actions stores `LITELLM_API_KEY` as a repository secret and both proxy
URLs as repository variables.

## Run manually

```bash
python3 daily_agent/agent.py
```

Or:

```bash
./daily_agent/run_agent.sh
```

A run performs the following work:

1. Fetch Hacker News, official AI-lab sources, and GitHub Trending.
2. Parse the prior README and remove yesterday's stories deterministically.
3. Classify candidates once with Luna, then ask Luna for the editorial selection.
4. Fetch the selected article URL and extract its main text. Use WebFetch only when
   the extracted text does not pass the quality gate; if both paths are unavailable,
   continue with a title-only comic context.
5. Generate five Luna comic candidates and select a winner with a Luna critic.
6. Render the comic with `gpt-image-2.5-flare`.
7. Render README.md deterministically from validated structured data.
8. Save phase-level model usage under `daily_agent/data/tokens/`.

## Scheduling

`.github/workflows/daily-agent.yml` is the single scheduler and commits each
successful edition. Do not add a local cron entry for the same job; duplicate
schedulers incur duplicate model spend even when one later fails to push.

## Usage accounting

Each token artifact contains:

- one record per direct model phase, including model, tokens, duration, and cost
  when the proxy reports it;
- separate usage for the exceptional WebFetch agent fallback;
- article extraction method and quality-gate result;
- image-generation usage.

## Troubleshooting

### Article extraction uses WebFetch frequently

Inspect `article_extraction` in the day's token artifact. JavaScript-only,
paywalled, blocked, or unusually short pages intentionally fail closed and use
the quality-preserving fallback.

### Claude Code fallback fails

Verify the Claude CLI is installed and `ANTHROPIC_BASE_URL` plus
`ANTHROPIC_API_KEY` are configured. A blocked or unavailable fallback is non-fatal:
the edition continues with the selected story title and the comic prompt is told not
to invent article facts.

### GitHub API rate limits

Set `GITHUB_TOKEN`. GitHub Actions supplies its built-in token automatically.
