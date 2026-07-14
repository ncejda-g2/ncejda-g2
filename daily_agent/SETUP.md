# Autonomous README Agent - Setup Guide (Claude Agent SDK)

This agent uses the **Claude Agent SDK** framework to autonomously update your README daily.

## Prerequisites

1. **Claude Code CLI** (required - the SDK uses it as a runtime)
2. **Python 3.8+**
3. **G2 LiteLLM proxy access** (provides Anthropic and OpenAI models via `https://llmproxy.g2.com`)

## 1. Install Claude Code CLI

The Claude Agent SDK requires Claude Code CLI to be installed:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Verify installation:
```bash
claude --version
```

## 2. Install Python Dependencies

```bash
cd /Users/ncejda/github/ncejda-g2
pip install -r requirements.txt
```

This installs:
- `claude-agent-sdk` - The Agent SDK framework
- `aiohttp` - For async HTTP requests (DALL-E, XKCD)
- `python-dotenv` - For environment variable management

## 3. Configure Environment Variables

Create a `.env` file in the project root (it is gitignored — never commit it):

```
LITELLM_BASE_URL=https://llmproxy.g2.com
LITELLM_API_KEY=<your G2 LiteLLM proxy key>
ANTHROPIC_BASE_URL=https://llmproxy.g2.com/anthropic
ANTHROPIC_API_KEY=<your G2 LiteLLM proxy key — same value as LITELLM_API_KEY>
GITHUB_TOKEN=<optional GitHub token for higher public API rate limits>
```

Both keys hold the same value. `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL`
are read by the Claude Code CLI subprocess (it only knows those names);
`LITELLM_API_KEY` and `LITELLM_BASE_URL` are read by `custom_tools.py`
for image generation. All API traffic — Anthropic chat and OpenAI image
generation — routes through the G2 LiteLLM proxy.

`GITHUB_TOKEN` is optional for local runs because public repository metadata is
available without authentication, but setting it avoids GitHub's low anonymous
API rate limit when the agent must inspect many Trending candidates. GitHub
Actions supplies its built-in token automatically.

For CI (GitHub Actions), the values are stored in repo settings:
- `LITELLM_API_KEY` → Secrets and variables → Actions → Repository secrets
- `LITELLM_BASE_URL` → Secrets and variables → Actions → Repository variables
- `ANTHROPIC_BASE_URL` → Secrets and variables → Actions → Repository variables

The workflow reads `LITELLM_API_KEY` once and exposes it under both
`ANTHROPIC_API_KEY` and `LITELLM_API_KEY` to the agent process.

## 4. Test the Agent Manually

Run the agent once to make sure everything works:

```bash
cd /Users/ncejda/github/ncejda-g2
python3 daily_agent/agent.py
```

Or use the wrapper script:
```bash
./daily_agent/run_agent.sh
```

### What the Agent Does

When you run it, you'll see the agent:

1. **Read README** - Check current day count
2. **Fetch News Sources** - Fetch recent Hacker News stories and official AI lab posts
3. **Track GitHub Trending** - Scrape daily, weekly, and monthly Trending, preserve observed streaks, and select broad AI-related repositories
4. **Research Community Reaction** - Search Hacker News for substantive independent reactions to selected repositories
5. **Generate Characters and Scene** - Choose random characters and a setting, then generate and critique candidate comic scenes
6. **Generate Comic Strip** - Render the winning scene with the configured image model
7. **Update README** - Write the news, lab, Trending, and comic sections
8. **Commit & Push** - GitHub Actions commits the README, state snapshots, and generated image

## 5. Set Up Cron Job (macOS)

### Understanding macOS Cron with Locked Screen

**Good news**: Cron jobs **DO run when your Mac is locked/closed** (lid closed on laptop), as long as:
- Your Mac is **powered on** (not shut down)
- Your Mac is **not in sleep mode**

### Steps to Set Up Cron

1. **Open crontab editor:**
   ```bash
   crontab -e
   ```

2. **Add this line to run at midnight EST:**

   During EST (Standard Time - Nov to Mar):
   ```bash
   0 5 * * * cd /Users/ncejda/github/ncejda-g2 && /Users/ncejda/github/ncejda-g2/daily_agent/run_agent.sh >> /Users/ncejda/github/ncejda-g2/daily_agent/cron.log 2>&1
   ```

   During EDT (Daylight Time - Mar to Nov):
   ```bash
   0 4 * * * cd /Users/ncejda/github/ncejda-g2 && /Users/ncejda/github/ncejda-g2/daily_agent/run_agent.sh >> /Users/ncejda/github/ncejda-g2/daily_agent/cron.log 2>&1
   ```

3. **Save and exit** (`:wq` in vim)

4. **Verify cron job is scheduled:**
   ```bash
   crontab -l
   ```

## 6. Prevent Sleep (If Needed)

If your Mac sleeps at night and prevents cron from running:

### Option A: System Settings
- Go to System Settings → Battery (or Energy Saver)
- Adjust sleep settings or enable "Prevent automatic sleeping when the display is off"

### Option B: Use `caffeinate` in cron
```bash
0 5 * * * /usr/bin/caffeinate -s /Users/ncejda/github/ncejda-g2/daily_agent/run_agent.sh >> /Users/ncejda/github/ncejda-g2/daily_agent/cron.log 2>&1
```

## 7. Monitor Logs

Check if the cron job ran successfully:

```bash
tail -f /Users/ncejda/github/ncejda-g2/daily_agent/cron.log
```

## Agent SDK Architecture

This agent uses the Claude Agent SDK, which means:

- **Claude is the orchestrator** - It decides how to use tools to accomplish tasks
- **Python owns Trending order and state** - GitHub rank, seven-day cooldowns, and observed streaks are deterministic
- **Repository text is capability-limited** - README excerpts are bounded and classified by a no-tools model call
- **Custom tools** defined in `custom_tools.py`:
  - `get_max_xkcd_number` - Get latest XKCD number
  - `fetch_xkcd_comic` - Fetch specific XKCD comic
  - `generate_image` - Generate image with gpt-image-1 (handles base64 decoding and saving)
  - `download_image` - Download and save images from URLs

- **Built-in tools** from Claude SDK:
  - `Read` - Read files
  - `Write` - Create new files
  - `Edit` - Edit existing files
  - `Bash` - Run terminal commands (git, etc.)

- **Autonomous execution** - Agent runs tasks sequentially with context preserved between steps
- **Smart division of labor** - Python handles true randomness (character/comic selection), Claude handles creative tasks (story writing)

## Troubleshooting

### "Claude Code CLI not installed"
Run: `curl -fsSL https://claude.ai/install.sh | bash`

### Cron job not running?
1. Check cron logs: `grep CRON /var/log/system.log`
2. Verify Full Disk Access for cron (System Preferences → Security → Privacy)
3. Check the `cron.log` file for error messages

### Git push failing?
- Ensure SSH keys are loaded: `ssh-add -l`
- Test manually: `git push origin main`
- Add to shell profile if needed: `ssh-add --apple-use-keychain ~/.ssh/id_rsa`

### API errors?
- Verify `.env` file exists and has valid `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY` + `LITELLM_API_KEY`
- Confirm the LiteLLM proxy is reachable: `curl https://llmproxy.g2.com/v1/models | head`

### Agent SDK import errors?
Make sure you installed: `pip install claude-agent-sdk`

### Permission errors?
The agent runs with `permission_mode="acceptEdits"` to auto-accept file changes.
For testing, you can change this to `"default"` in `agent.py` to manually approve changes.
