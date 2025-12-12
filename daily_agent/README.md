# Daily Autonomous Agent (Claude Agent SDK)

This directory contains an autonomous agent built with the **Claude Agent SDK** that updates the main README.md daily.

## What It Does

Every day at midnight EST, this agent autonomously:

1. **Generates Characters**: Creates 1-3 random characters by combining adjectives and animals
   - Uses Python's `random` module for true randomness (not AI-generated)
   - Examples: "friendly moose", "grumpy cat and wise octopus"

2. **Fetches Random XKCD**:
   - Gets max XKCD comic number (via Claude tool)
   - Picks a truly random comic number (Python's `random` module)
   - Fetches comic details (via Claude tool)

3. **Writes a 3-Panel Story**:
   - Claude acts as a creative comedy writer
   - Combines characters + XKCD comic (title + alt text)
   - Creates a funny 3-panel comic structure:
     - Panel 1: Setup
     - Panel 2: Development
     - Panel 3: Punchline

4. **Generates Comic Strip**:
   - Calls OpenAI's gpt-image-1 model to generate a complete 3-panel comic strip
   - All panels in a single horizontal image
   - Comic book style with clear panel divisions

5. **Updates README**:
   - Writes everything to the main README.md
   - Includes clickable XKCD link
   - Shows XKCD alt text for context
   - Displays 3-panel comic strip (width-constrained at 800px)
   - Tracks day count

6. **Commits & Pushes**:
   - Commits all changes including generated image
   - Automatically pushes to GitHub
   - Image displays correctly on GitHub profile

## Architecture: Claude Agent SDK

This project uses the **Claude Agent SDK framework**, not just API calls. Key differences:

### Traditional Approach (NOT what we're doing)
```python
# Procedural code making API calls
xkcd_data = requests.get("https://xkcd.com/...")
story = claude_api.generate(prompt=...)
image = openai_api.images.generate(...)
```

### Agent SDK Approach (What we ARE doing)
```python
# Claude orchestrates and decides how to use tools
async with ClaudeSDKClient(options=options) as client:
    await client.query(
        "Fetch a random XKCD comic and generate a creative story"
    )
    # Claude figures out:
    # 1. Call get_max_xkcd_number tool
    # 2. Call generate_random_int tool
    # 3. Call fetch_xkcd_comic tool
    # 4. Write a story using its language model
    # 5. etc.
```

**Benefits:**
- Claude makes intelligent decisions about tool usage
- Context preserved across multiple tasks
- More truly "autonomous" - Claude reasons about how to accomplish goals
- Great for learning the Agent SDK patterns

## Files

- **`agent.py`** - Main autonomous agent using Claude Agent SDK
- **`custom_tools.py`** - Custom tool definitions:
  - `get_max_xkcd_number` - XKCD API integration
  - `fetch_xkcd_comic` - Get specific comic (with alt text)
  - `generate_dalle_image` - OpenAI gpt-image-1 integration (generates and saves directly from base64)
  - `download_image` - Download and save images from URLs
- **`run_agent.sh`** - Wrapper script for cron (handles env vars)
- **`SETUP.md`** - Complete setup and installation guide
- **`generated_images/`** - Directory where daily comic strips are stored
  - **Note:** Images are committed to git (not in .gitignore) so they display on GitHub
  - Filenames: `day_0001.png`, `day_0002.png`, etc.

## Quick Start

See [SETUP.md](SETUP.md) for complete instructions.

**Prerequisites:**
```bash
# Install Claude Code CLI (required for Agent SDK)
curl -fsSL https://claude.ai/install.sh | bash

# Install Python dependencies
pip install -r requirements.txt

# Configure API keys in .env file
cp ../.env.example ../.env
# Then edit .env with your keys
```

**Manual test run:**
```bash
cd /Users/ncejda/github/ncejda-g2
python3 daily_agent/agent.py
```

## Agent SDK Configuration

From `agent.py`:

```python
options = ClaudeAgentOptions(
    # Custom tools via MCP server
    mcp_servers={"readme-tools": tools_server},

    # Allowed tools (built-in + custom)
    allowed_tools=[
        "Read", "Write", "Edit", "Bash",  # Built-in
        "mcp__readme-tools__generate_dalle_image",  # Custom
        # ... etc
    ],

    # Auto-accept edits (for autonomous operation)
    permission_mode="acceptEdits",

    # Working directory
    cwd=str(PROJECT_ROOT),

    # Use Sonnet (good balance of speed/capability)
    model="sonnet",
)
```

## Technologies

- **Claude Agent SDK**: Framework for building autonomous agents
- **Claude API**: Story generation and orchestration
- **OpenAI API**: gpt-image-1 for image generation
- **XKCD API**: Random comic inspiration
- **aiohttp**: Async HTTP requests
- **Git**: Automated version control

## Learning the Agent SDK

This project is a great way to learn the Agent SDK because it demonstrates:

1. **Custom Tool Creation**: Using `@tool` decorator to wrap external APIs (XKCD, OpenAI gpt-image-1)
2. **MCP Server Setup**: Creating a server with `create_sdk_mcp_server`
3. **Agent Client Usage**: Using `ClaudeSDKClient` for orchestration
4. **Multi-Step Workflows**: Sequential tasks with context preservation
5. **Complex Prompt Engineering**: Creating detailed prompts for multi-panel image generation
6. **Tool Permissions**: Managing what tools the agent can use
7. **Autonomous Operation**: Running unattended with `permission_mode="acceptEdits"`
8. **Smart Division of Labor**: Python for randomness, Claude for creativity

## Agent Workflow Visualization

```
┌─────────────────┐
│  Cron Job       │
│  (Midnight EST) │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  agent.py                   │
│  (ClaudeSDKClient)          │
└────────┬────────────────────┘
         │
         ├──► Task 1: Read README (day count)
         │         Uses: Read tool
         │
         ├──► Task 2: Generate characters
         │         Uses: Python random module
         │         (No Claude - true randomness!)
         │
         ├──► Task 3: Fetch XKCD
         │         Uses: get_max_xkcd_number tool
         │                Python random module (pick comic #)
         │                fetch_xkcd_comic tool
         │
         ├──► Task 4: Write 3-panel story
         │         Claude's language model
         │         (creative writing - setup, development, punchline)
         │
         ├──► Task 5: Generate comic strip
         │         Uses: generate_dalle_image (1x)
         │         Generates and saves 3-panel comic strip
         │         (handles base64 decoding internally)
         │
         ├──► Task 6: Update README
         │         Uses: Write tool
         │
         └──► Task 7: Git commit & push
                  Uses: Bash tool
```

## Why This Beats a Regular Script

**Regular Python Script:**
- Procedural: Do A, then B, then C
- No intelligence in task execution
- Brittle (API changes break everything)
- Hard to extend with new capabilities

**Agent SDK Approach:**
- Declarative: "Accomplish this goal"
- Claude figures out the steps
- Resilient (Claude adapts to tool responses)
- Easy to add new tools and capabilities
- **You get to practice the Agent SDK framework!**
