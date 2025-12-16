#!/usr/bin/env python3
"""
Fully Autonomous README Agent using Claude Agent SDK

This agent runs daily with a single comprehensive prompt that orchestrates the
entire workflow autonomously. Claude is provided with all tools upfront and
handles everything from content creation to git operations.

Workflow:
1. Python generates random characters (adjective + animal), picks a random place and situation
2. Single comprehensive prompt is sent to Claude with Read, Write, Edit, and Bash tools
3. Claude autonomously:
   - Reads README.md and extracts day count
   - Invents a NEW creative scenario and adds it to the situations file
   - Writes a hilarious improv dialog between characters in the given situation/place
   - Updates README.md with the dialog
   - Commits and pushes changes to GitHub

Key Benefits:
- True autonomy: One prompt, entire workflow including git operations
- Simpler code: Minimal orchestration needed
- Claude handles dialog creation, context management, formatting, AND deployment
- Growing scenario library: Claude adds one new creative scenario each day
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
DATA_DIR = Path(__file__).parent / "data"


def load_list_from_file(filename: str) -> list[str]:
    """
    Load a list of items from a text file (one item per line).

    Args:
        filename: Name of the file in the data directory

    Returns:
        List of non-empty, stripped lines from the file
    """
    filepath = DATA_DIR / filename
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip()]


def generate_random_characters() -> list[str]:
    """
    Generate 1-3 random characters by combining adjectives and animals.
    Uses true Python randomness - no AI involved.

    Returns:
        List of character strings like ["friendly moose", "grumpy cat"]
    """
    adjectives = load_list_from_file("adjectives.txt")
    animals = load_list_from_file("animals.txt")

    num_characters = random.randint(1, 3)
    characters = []

    for _ in range(num_characters):
        adjective = random.choice(adjectives)
        animal = random.choice(animals)
        characters.append(f"{adjective} {animal}")

    return characters


def get_random_situation_and_scene() -> tuple[str, str]:
    """
    Pick a random situation and scene from the data files.

    Returns:
        Tuple of (situation, scene)
    """
    situations = load_list_from_file("situations.txt")
    scenes = load_list_from_file("scenes.txt")

    return random.choice(situations), random.choice(scenes)


async def run_autonomous_agent() -> None:
    """
    Run the autonomous README update agent with a single comprehensive prompt.

    This version provides ALL tools upfront and lets Claude orchestrate the entire
    workflow autonomously, rather than breaking it into sequential tasks.
    """

    print("Starting Autonomous README Agent (Single-Prompt Workflow)")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working directory: {PROJECT_ROOT}\n")

    # Generate random characters using Python's random module (true randomness!)
    characters = generate_random_characters()
    characters_text = ", ".join(characters)
    print(f"Generated characters: {characters_text}")

    # Pick random situation and place
    situation, place = get_random_situation_and_scene()
    print(f"Place: {place}")
    print(f"Situation: {situation}\n")

    # Get the path to situations file for Claude to edit
    situations_file = DATA_DIR / "situations.txt"

    timestamp = datetime.now().strftime("%Y-%m-%d")

    # Configure agent options
    options = ClaudeAgentOptions(
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "Bash",
        ],
        permission_mode="acceptEdits",
        cwd=str(PROJECT_ROOT),
        model="sonnet",
    )

    # Single comprehensive prompt - Claude handles the entire workflow!
    async with ClaudeSDKClient(options=options) as client:

        print("Launching autonomous workflow...\n")
        print("=" * 60)

        await client.query(
            f"""You are an autonomous agent that updates README.md daily with a hilarious improv dialog.

Complete this ENTIRE workflow autonomously:

## Step 1: Determine Day Count
Read README.md and extract the current day count from the line:
'Days running a fully-autonomous agent that updates my README: X'

If the line doesn't exist, use 0 as the current count.
Calculate the new day count by adding 1.

## Step 2: Invent a NEW Scenario
Your creative task: Invent ONE new, original, funny scenario for future improv dialogs.

Read the existing scenarios from: {situations_file}

Then create a NEW scenario that:
- Is different from all existing ones (be creative!)
- Is absurd, funny, or has comedic potential
- Sets up an interesting situation for characters to improvise
- Is one sentence, similar in style to existing scenarios

Examples of good scenarios:
- "Two rival magicians must share an Uber."
- "A time-traveling food critic reviews prehistoric cuisine."
- "Tech support for magical artifacts."

Add your new scenario as a NEW LINE at the END of the file: {situations_file}
Use the Edit tool to append your new scenario.

## Step 3: Create Narrative Title
Create a narrative title that combines the elements into a flowing sentence.

Characters: {characters_text}
Place: {place}
Situation: {situation}

Create a narrative sentence that flows naturally, like:
"An exhausted capybara, an elegant capybara, and a gourmet bear are superheroes dealing with everyday problems and find themselves in the microscopic world"

Use proper articles (a/an), make it read naturally, and incorporate all three elements.

## Step 4: Write Improv Dialog
Create a hilarious, work-appropriate improv dialog featuring these characters in the given situation and place.

Requirements:
- Write a dialog between the characters (formatted as "CHARACTER NAME: \"dialog line\"")
- Each character should have at least 3-5 lines of dialog
- The dialog should be funny, witty, and capture the absurdity of the situation
- Use the characters' adjectives to inform their personality and how they speak
- Keep it clean and work-appropriate
- Make it very funny and unexpected!
- The dialog should have a clear beginning, middle, and punchline ending

## Step 5: Update README.md
Write a new README.md file with this EXACT structure:

```markdown
# Today's Improv ({timestamp})

**Days running a fully-autonomous agent that updates my README: [NEW DAY COUNT]**

[Your narrative title here - the sentence you created in Step 3]

---

[CHARACTER NAME 1]: "dialog line"

[CHARACTER NAME 2]: "dialog line"

[CHARACTER NAME 1]: "dialog line"

[Continue the full dialog here with all lines...]

---

*This README is autonomously updated daily by a Claude agent that:*
*1. Generates random characters (adjective + animal combinations)*
*2. Picks a random place and improv situation*
*3. Invents a NEW scenario and adds it to the collection*
*4. Writes a hilarious dialog between the characters*
*5. Automatically commits and pushes via GitHub Actions*

*Last updated: {timestamp}*
```

IMPORTANT:
- Format character names in UPPERCASE followed by a colon, then their dialog in quotes.
- Example: HUNGRY BEAR: "I can't focus on this meeting, I'm starving!"
- The narrative title should be in regular text (not bold, not italicized)

## Step 6: Commit and Push to GitHub
After updating all files, commit and push your changes:

1. Stage all changes: `git add .`
2. Commit with message: `git commit -m "Day [DAY_NUMBER] - Autonomous README update"`
   (Use the day number you calculated in Step 1)
3. Push to origin: `git push`

Report your progress as you complete each step. Show me:
1. The new scenario you invented
2. The narrative title
3. The dialog
4. Git commit result"""
        )

        # Stream Claude's response and print progress
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

        print("\n" + "=" * 60)
        print("Autonomous agent completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(run_autonomous_agent())
    except KeyboardInterrupt:
        print("\n\nAgent interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nAgent failed with error: {e}")
        sys.exit(1)
