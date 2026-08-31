# AI Newspaper Setup

The newspaper runs once per day in GitHub Actions. Python owns fetching,
deduplication, validation, state, and README rendering. Focused model calls use
strict structured outputs through the G2 LiteLLM proxy. Sonnet remains responsible
for editorial judgment and the five-writer-plus-critic comic pipeline.

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
3. Classify candidates once with Haiku, then ask Sonnet for the editorial selection.
4. Fetch the selected article URL and extract its main text. Use WebFetch only when
   the extracted text does not pass the quality gate.
5. Generate five Sonnet comic candidates and select a winner with a Sonnet critic.
6. Render the comic with `gpt-image-2`.
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
`ANTHROPIC_API_KEY` are configured.

### GitHub API rate limits

Set `GITHUB_TOKEN`. GitHub Actions supplies its built-in token automatically.
