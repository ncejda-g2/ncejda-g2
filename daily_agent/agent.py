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


def generate_random_characters(count: int) -> list[str]:
    """
    Generate a specific number of random characters by combining adjectives and animals.
    Uses true Python randomness - no AI involved.

    Args:
        count: Number of characters to generate

    Returns:
        List of character strings like ["friendly moose", "grumpy cat"]
    """
    adjectives = load_list_from_file("adjectives.txt")
    animals = load_list_from_file("animals.txt")

    characters = []
    for _ in range(count):
        adjective = random.choice(adjectives)
        animal = random.choice(animals)
        characters.append(f"{adjective} {animal}")

    return characters


def roll_for_monologue() -> bool:
    """
    Roll a weighted dice to determine if this should be a monologue.
    20% chance of monologue, 80% chance of dialogue.

    Returns:
        True if monologue mode, False for dialogue mode
    """
    return random.random() < 0.2


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

    # Pick random situation and place first (Claude will use this to decide character count)
    situation, place = get_random_situation_and_scene()
    print(f"Place: {place}")
    print(f"Situation: {situation}")

    # Roll for monologue mode (20% chance)
    is_monologue = roll_for_monologue()

    if is_monologue:
        # Monologue mode: exactly 1 character
        characters = generate_random_characters(1)
        characters_text = characters[0]
        mode_instruction = """MODE: MONOLOGUE (forced by dice roll)
You MUST write a monologue featuring exactly this one character. No other main characters.
Side characters may briefly appear for comedic effect, but the focus is on this character's solo performance."""
        print(f"Mode: MONOLOGUE (20% dice roll)")
        print(f"Character: {characters_text}\n")
    else:
        # Dialogue mode: generate pool of 3, Claude picks how many to use
        characters = generate_random_characters(3)
        characters_text = ", ".join(characters)
        mode_instruction = """MODE: DIALOGUE (Claude chooses character count)
You have a pool of 3 characters. Based on the situation, decide how many main characters to use:
- Use 2 characters if the situation is best as a back-and-forth exchange
- Use 3 characters if the situation benefits from more chaos or perspectives
- You MAY use just 1 character from the pool if the situation genuinely calls for a monologue
In general, favor dialogues (2-3 characters). Side characters may appear for comedic effect."""
        print(f"Mode: DIALOGUE (Claude chooses from pool)")
        print(f"Character pool: {characters_text}\n")

    # Get the paths to data files for Claude to edit
    situations_file = DATA_DIR / "situations.txt"
    adjectives_file = DATA_DIR / "adjectives.txt"

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

## Step 3: Add a NEW Adjective
Your creative task: Invent ONE new, funny adjective for future character generation.

Read the existing adjectives from: {adjectives_file}

Then create a NEW adjective that:
- Is different from all existing ones
- Is funny, exciting, or has comedic potential (NOT boring like colors)
- Think: 'cursed', 'delusional', 'ruffian', 'chaotic', 'melodramatic', 'paranoid', 'pretentious'
- Single word only

Add your new adjective as a NEW LINE at the END of the file: {adjectives_file}
Use the Edit tool to append your new adjective.

## Step 4: Create Narrative Title
Create a narrative title that combines the elements into a flowing sentence.

{mode_instruction}

Characters: {characters_text}
Place: {place}
Situation: {situation}

First, decide which character(s) you will use based on the mode above.
Then create a narrative sentence that flows naturally, featuring only the characters you chose.

Example: "An exhausted capybara and a gourmet bear are superheroes dealing with everyday problems in the microscopic world"

Use proper articles (a/an), make it read naturally, and incorporate the place and situation.

## Step 5: Write the Improv
Create a hilarious, work-appropriate improv featuring the character(s) you chose in Step 4.

Requirements:
- Format lines as "CHARACTER NAME: \"dialog line\""
- Keep it somewhat concise: 30 total lines maximum. Quality over quantity!
- If MONOLOGUE mode: Write a solo performance. The character talks to themselves, the audience, or narrates their situation. Side characters may briefly appear for comedic effect.
- If DIALOGUE mode: Write exchanges between your chosen main characters (2-3 from the pool).
- Side characters can randomly enter the scene for comedic effect (e.g., a waiter, a passerby, an announcer)
- Use the characters' adjectives to inform their personality and speech patterns
- The piece should be funny, witty, and capture the absurdity of the situation
- Keep it clean and work-appropriate
- Make it very funny and unexpected!
- Have a clear beginning, middle, and punchline ending
- Remember: short and punchy is funnier than long and rambling!

## Step 6: Update README.md
Write a new README.md file with this EXACT structure:

```markdown
# Today's Improv ({timestamp})

**Days running a fully-autonomous agent that updates my README: [NEW DAY COUNT]**

[Your narrative title here - the sentence you created in Step 4]

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
*4. Adds a NEW funny adjective to the character pool*
*5. Writes a hilarious dialog between the characters*
*6. Automatically commits and pushes via GitHub Actions*

*Last updated: {timestamp}*
```

IMPORTANT:
- Format character names in UPPERCASE followed by a colon, then their dialog in quotes.
- Example: HUNGRY BEAR: "I can't focus on this meeting, I'm starving!"
- The narrative title should be in regular text (not bold, not italicized)

## Step 7: Commit and Push to GitHub
After updating all files, commit and push your changes:

1. Stage all changes: `git add .`
2. Commit with message: `git commit -m "Day [DAY_NUMBER] - Autonomous README update"`
   (Use the day number you calculated in Step 1)
3. Push to origin: `git push`

Report your progress as you complete each step. Show me:
1. The new scenario you invented
2. The new adjective you added
3. The narrative title
4. The dialog
5. Git commit result"""
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
