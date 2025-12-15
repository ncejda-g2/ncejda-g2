#!/usr/bin/env python3
"""
Autonomous README Agent using Claude Agent SDK (Single-Prompt Workflow)

This agent runs daily with a single comprehensive prompt that orchestrates the
entire workflow autonomously. Claude is provided with all tools upfront and
handles the complete task from start to finish.

Workflow:
1. Python generates random characters (adjective + animal), picks a random place and situation
2. Single comprehensive prompt is sent to Claude with all tools available
3. Claude autonomously:
   - Reads README.md and extracts day count
   - Writes a hilarious improv dialog between characters in the given situation/place
   - Updates README.md with the dialog
   - Git operations handled by wrapper script or GitHub Actions

Key Benefits:
- True autonomy: One prompt, entire workflow completed
- Simpler code: Minimal orchestration needed
- Claude handles dialog creation, context management, and formatting
"""

import asyncio
import random
import sys
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
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

SITUATIONS = [
    "A support group for fictional phobias.",
    "A job interview for absurd positions.",
    "Superheroes dealing with everyday problems.",
    "A family dinner where everyone speaks in rhyme.",
    "News anchors reporting on bizarre events.",
    "therapy session for inanimate objects.",
    "Time travelers trying to fit into different eras.",
    "Animals navigating the challenges of human life.",
    "Aliens attempting to understand Earth customs.",
    "Historical figures attending a modern-day party.",
    "A courtroom drama with ridiculous charges.",
    "Fairy tale characters in a group therapy session.",
    "Sports commentators for unusual competitions.",
    "Job candidates with peculiar skills.",
    "Insects navigating human-sized obstacles.",
    "Teachers dealing with bizarre student excuses.",
    "Characters in a musical where every line is a song.",
    "Ghosts haunting a comedy club.",
    "Characters trapped in a never-ending meeting.",
    "Unusual superheroes with bizarre powers.",
    "An insane flight attendant is caught in a lab accident in Miami.",
    "A scientist comes to an uncomfortable realization in Washington D.C..",
    "Passengers must return money stolen from the mob.",
    "Rival pilots battle zombies on the way to a friend's house.",
    "A cursed woman is trapped by a hurricane ",
    "An inventor receives a mysterious phone call ",
    "A ghost learns the truth in the astral plane.",
    "A psychic adopts a baby but gets more than he bargained for.",
    "Children discover a shocking secret in a prep school.",
    "An aging butler fights for her inheritance.",
    "A bad chef comes to town.",
    "A prankster meets someone he thought had died in Brazil.",
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

    # Pick random situation and place
    situation = random.choice(SITUATIONS)
    place = random.choice(SCENES)
    print(f"📍 Place: {place}")
    print(f"🎬 Situation: {situation}\n")

    timestamp = datetime.now().strftime("%Y-%m-%d")

    # Configure agent options
    options = ClaudeAgentOptions(
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
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
            f"""You are an autonomous agent that updates README.md daily with a hilarious improv dialog.

Complete this ENTIRE workflow autonomously:

## Step 1: Determine Day Count
Read README.md and extract the current day count from the line:
'Days running a fully-autonomous agent that updates my README: X'

If the line doesn't exist, use 0 as the current count.
Calculate the new day count by adding 1.

## Step 2: Write Improv Dialog
Create a hilarious, work-appropriate improv dialog featuring these characters:
{characters_text}

Place: {place}
Situation: {situation}

Requirements:
- Write a dialog between the characters (formatted as "CHARACTER NAME: \"dialog line\"")
- Each character should have at least 3-5 lines of dialog
- The dialog should be funny, witty, and capture the absurdity of the situation
- Use the characters' adjectives to inform their personality and how they speak
- Keep it clean and work-appropriate
- Make it very funny and unexpected!
- The dialog should have a clear beginning, middle, and punchline ending

## Step 3: Update README.md
Write a new README.md file with this EXACT structure:

```markdown
# Today's Improv ({timestamp})

**Days running a fully-autonomous agent that updates my README: [NEW DAY COUNT]**

**CHARACTERS:** {characters_text}
**PLACE:** {place}
**SITUATION:** {situation}

---

[CHARACTER NAME 1]: "dialog line"

[CHARACTER NAME 2]: "dialog line"

[CHARACTER NAME 1]: "dialog line"

[Continue the full dialog here with all lines...]

---

*This README is autonomously updated daily by a Claude agent that:*
*1. Generates random characters (adjective + animal combinations)*
*2. Picks a random place and improv situation*
*3. Writes a hilarious dialog between the characters*
*4. Automatically commits and pushes via GitHub Actions*

*Last updated: {timestamp}*
```

IMPORTANT: Format character names in UPPERCASE followed by a colon, then their dialog in quotes.
Example: HUNGRY BEAR: "I can't focus on this meeting, I'm starving!"

Report your progress as you complete each step. Show me the dialog."""
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
