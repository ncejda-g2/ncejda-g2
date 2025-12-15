#!/usr/bin/env python3
"""
Autonomous README Agent using Claude Agent SDK (Single-Prompt Workflow)

This agent runs daily with a single comprehensive prompt that orchestrates the
entire workflow autonomously. Claude is provided with all tools upfront and
handles the complete task from start to finish.

Workflow:
1. Python generates random characters (adjective + animal) and picks a random XKCD comic
2. Single comprehensive prompt is sent to Claude with all tools available
3. Claude autonomously:
   - Reads README.md and extracts day count
   - Fetches the specified XKCD comic
   - Writes a funny 3-panel story combining characters + XKCD
   - Generates a 3-panel comic strip illustration using OpenAI's gpt-image-1
   - Updates README.md with all content
   - Commits and pushes to GitHub

Key Benefits:
- True autonomy: One prompt, entire workflow completed
- Simpler code: ~160 lines vs 280+ lines of manual orchestration
- Claude handles tool orchestration, error recovery, and context management
"""

import asyncio
import random
import sys
from datetime import datetime
from pathlib import Path

import aiohttp
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
    create_sdk_mcp_server,
)
from custom_tools import (
    download_image,
    fetch_xkcd_comic,
    generate_image,
    get_max_xkcd_number,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent

# Character lists
ADJECTIVES = [
    "hungry",
    "small",
    "friendly",
    "upset",
    "content",
    "sleepy",
    "excited",
    "grumpy",
    "cheerful",
    "nervous",
    "brave",
    "silly",
    "wise",
    "clumsy",
    "elegant",
    "mischievous",
    "peaceful",
    "rotund",
    "exhausted",
    "frugal",
    "enlightned",
    "apologitic",
    "arrogant",
    "cautious",
    "diligent",
    "gregarious",
    "silly",
    "nerdy",
    "geeky",
    "ugly",
    "smelly",
    "gourmet",
    "elegant",
    "beautiful",
    "hoity-toity",
    "adventurous",
    "down-to-earth",
    "hippie",
    "punk",
    "rockstar",
    "wizard",
    "ninja",
    "pirate",
    "samurai",
    "vampire",
    "zombie",
]

ANIMALS = [
    "bear",
    "moose",
    "cat",
    "armadillo",
    "giraffe",
    "penguin",
    "octopus",
    "raccoon",
    "fox",
    "owl",
    "hedgehog",
    "platypus",
    "lemur",
    "otter",
    "capybara",
    "pangolin",
    "E. coli",
    "sloth",
    "gorilla",
    "chicken",
    "horse",
    "witch",
    "dragon",
    "unicorn",
    "alien",
    "robot",
    "dinosaur",
]

SCENES = [
    "Forest",
    "Beach",
    "City",
    "Outer Space",
    "Desert",
    "Underwater",
    "Mountain",
    "Office",
    "Home",
    "Microscopic World",
    "Medieval Castle",
    "Futuristic City",
    "Clouds",
    "Dreamland",
    "Candyland",
    "Jungle",
    "Amusement Park",
    "Farm",
    "Volcano",
    "Arctic",
    "Swamp",
    "Space Station",
    "Haunted House",
    "Pirate Ship",
    "Wizard's Tower",
    "Robot Factory",
    "Dinosaur Jungle",
    "Fairy Tale Forest",
    "Underwater City",
    "Alien Planet",
]


def generate_random_characters() -> list[str]:
    """
    Generate 1-3 random characters by combining adjectives and animals.
    Uses true Python randomness - no AI involved.

    Returns:
        List of character strings like ["friendly moose", "grumpy cat"]
    """
    num_characters = random.randint(1, 3)
    characters = []

    for _ in range(num_characters):
        adjective = random.choice(ADJECTIVES)
        animal = random.choice(ANIMALS)
        characters.append(f"{adjective} {animal}")

    return characters


async def fetch_max_xkcd_number() -> int:
    """
    Fetch the latest XKCD comic number directly from the XKCD API.
    Uses direct HTTP call for Python-controlled randomness.

    Returns:
        The maximum XKCD comic number, or 3000 as fallback
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://xkcd.com/info.0.json") as response:
                if response.status == 200:
                    data = await response.json()
                    return data["num"]
    except Exception as e:
        print(f"   ⚠️  Failed to fetch max XKCD number: {e}")

    # Fallback
    return 3000


async def run_autonomous_agent() -> None:
    """
    Run the autonomous README update agent with a single comprehensive prompt.

    This version provides ALL tools upfront and lets Claude orchestrate the entire
    workflow autonomously, rather than breaking it into sequential tasks.
    """

    print("🤖 Starting Autonomous README Agent (Single-Prompt Workflow)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Working directory: {PROJECT_ROOT}\n")

    # Generate random characters using Python's random module (true randomness!)
    characters = generate_random_characters()
    characters_text = ", ".join(characters)
    print(f"🎭 Generated characters: {characters_text}")

    # Get max XKCD number and pick a random comic (true randomness!)
    print(f"📰 Fetching max XKCD number...")
    max_xkcd_number = await fetch_max_xkcd_number()
    random_comic_num = random.randint(1, max_xkcd_number)
    print(f"📰 Randomly selected XKCD comic #{random_comic_num}\n")

    timestamp = datetime.now().strftime("%Y-%m-%d")

    # Create custom tools MCP server
    tools_server = create_sdk_mcp_server(
        name="readme-tools",
        version="1.0.0",
        tools=[
            get_max_xkcd_number,
            fetch_xkcd_comic,
            generate_image,
            download_image,
        ],
    )

    # Configure agent options with ALL tools available upfront
    options = ClaudeAgentOptions(
        mcp_servers={"readme-tools": tools_server},
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "Bash",
            "mcp__readme-tools__get_max_xkcd_number",
            "mcp__readme-tools__fetch_xkcd_comic",
            "mcp__readme-tools__generate_image",
            "mcp__readme-tools__download_image",
        ],
        permission_mode="acceptEdits",
        cwd=str(PROJECT_ROOT),
        model="sonnet",
    )

    # Single comprehensive prompt - Claude handles the entire workflow!
    async with ClaudeSDKClient(options=options) as client:

        print("🚀 Launching autonomous workflow...\n")
        print("=" * 60)

        await client.query(
            f"""You are an autonomous agent that updates README.md daily with a funny comic story.

Complete this ENTIRE workflow autonomously:

## Step 1: Determine Day Count
Read README.md and extract the current day count from the line:
'Days running a fully-autonomous agent that updates my README: X'

If the line doesn't exist, use 0 as the current count.
Calculate the new day count by adding 1.

## Step 2: Fetch XKCD Comic
Use the fetch_xkcd_comic tool to get comic #{random_comic_num}.
Extract the title, alt text, and URL from the response.
Read the image of the comic, and understand it's general message for inspiration.
Print the comic's storyline and punchline to confirm your understanding.

## Step 3: Write 3-Panel Story
Create a funny, work-appropriate 3-panel comic story featuring these characters:
{characters_text}
Set in the scene: {random.choice(SCENES)}

The story should be inspired by the XKCD comic you fetched.

Requirements:
- Panel 1: Setup (1-2 sentences)
- Panel 2: Development (1-2 sentences)
- Panel 3: Punchline (1-2 sentences with unexpected, hilarious ending)
- Keep it clean and work-appropriate
- Make it very funny!

## Step 4: Update README.md
Write a new README.md file with this structure:

```markdown
# Today's Comic ({timestamp})

**Days running a fully-autonomous agent that updates my README: [NEW DAY COUNT]**

### Characters
[characters list]

In the: [SCENE]

### Inspired by XKCD
[**Comic #[NUMBER]: [TITLE]**]([URL])

*[ALT TEXT]*

### The 3-Panel Story

**Panel 1:** [panel 1 text]

**Panel 2:** [panel 2 text]

**Panel 3:** [panel 3 text]


---

*This README is autonomously updated daily by a Claude agent that:*
*1. Generates random characters (adjective + animal combinations)*
*2. Fetches a random XKCD comic*
*3. Writes a funny 3-panel story combining them*
*4. Commits and pushes to GitHub*

*Last updated: {timestamp}*
```

## Step 5: Commit and Push to GitHub
Run these git commands using the Bash tool:
1. git add .
2. git commit -m '🤖 Day [X] - Autonomous README update'
3. git push origin main
4. git log --oneline -1

Report your progress as you complete each step. Show me the comic title, the story panels, and the final commit hash."""
        )

        # Stream Claude's response and print progress
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

        print("\n" + "=" * 60)
        print("🎉 Autonomous agent completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(run_autonomous_agent())
    except KeyboardInterrupt:
        print("\n\n⚠️  Agent interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Agent failed with error: {e}")
        sys.exit(1)
