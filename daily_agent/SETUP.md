# Autonomous README Agent - Setup Guide (Claude Agent SDK)

This agent uses the **Claude Agent SDK** framework to autonomously update your README daily.

## Prerequisites

1. **Claude Code CLI** (required - the SDK uses it as a runtime)
2. **Python 3.8+**
3. **Anthropic API Key**
4. **OpenAI API Key**

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

## 3. Configure API Keys

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here
```

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
2. **Generate Characters** - Create 1-3 random characters using Python's random module (true randomness!)
3. **Fetch XKCD** - Get max comic number via tool, pick random comic with Python, fetch comic details including alt text
4. **Write 3-Panel Story** - Claude writes a funny 3-panel story (setup, development, punchline) combining characters and XKCD
5. **Generate 3 Images** - Call DALL-E 3 three times to create a 3-panel comic strip
6. **Update README** - Write new README.md with XKCD link, alt text, and all 3 comic panels
7. **Commit & Push** - Automatically commit and push all changes including images to GitHub

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
- **Custom tools** defined in `custom_tools.py`:
  - `get_max_xkcd_number` - Get latest XKCD number
  - `fetch_xkcd_comic` - Fetch specific XKCD comic
  - `generate_dalle_image` - Generate image with DALL-E 3
  - `download_image` - Download and save images

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
- Verify `.env` file exists and has valid keys
- Check API quotas:
  - Anthropic Console: https://console.anthropic.com
  - OpenAI Dashboard: https://platform.openai.com/usage

### Agent SDK import errors?
Make sure you installed: `pip install claude-agent-sdk`

### Permission errors?
The agent runs with `permission_mode="acceptEdits"` to auto-accept file changes.
For testing, you can change this to `"default"` in `agent.py` to manually approve changes.
