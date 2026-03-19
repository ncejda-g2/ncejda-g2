#!/usr/bin/env python3
"""
Fully Autonomous README Agent using Claude Agent SDK

This agent runs daily with a single comprehensive prompt that orchestrates the
entire workflow autonomously. Claude is provided with all tools upfront and
handles content creation.

Workflow:
1. Python fetches HN front page stories via Algolia API
2. Python generates random characters (adjective + animal) and picks a random situation
3. Single comprehensive prompt is sent to Claude with Read, Write, Edit tools
4. Claude autonomously:
   - Reads README.md and extracts day count
   - Filters HN stories for AI relevance (5-tier system)
   - Selects up to 10 AI stories for the digest table
   - Picks ONE story for characters to discuss
   - Curates four data files (adjectives, animals, situations, relationships)
     with exactly one edit each — add, remove, or replace
   - Writes improv dialog: characters discuss the AI story while in the random situation
   - Updates README.md with news table + improv dialog
5. GitHub Actions handles the git commit and push
"""

import asyncio
import aiohttp
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


async def fetch_hn_stories(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """
    Fetch Hacker News front page stories via Algolia API.

    Args:
        session: aiohttp ClientSession for making HTTP requests

    Returns:
        List of story dicts with keys: id, title, url, score, comments, author, created_at, updated_at, text
        Sorted by score descending. Returns empty list on error or stale data.
    """
    try:
        url = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=90"
        async with session.get(url) as resp:
            data = await resp.json()

        stories = []
        for hit in data.get("hits", []):
            story = {
                "id": int(hit.get("objectID", 0)),
                "title": hit.get("title", ""),
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "score": hit.get("points", 0),
                "comments": hit.get("num_comments", 0),
                "author": hit.get("author", ""),
                "created_at": hit.get("created_at", ""),
                "updated_at": hit.get("updated_at", ""),
                "text": hit.get("story_text", ""),
            }
            stories.append(story)

        # Sort by score descending
        stories.sort(key=lambda s: s["score"], reverse=True)

        # Check staleness: if most recent update is >2 hours old, return empty
        if stories:
            from datetime import datetime as dt
            most_recent = max(stories, key=lambda s: s["updated_at"])
            if most_recent["updated_at"]:
                try:
                    updated_time = dt.fromisoformat(most_recent["updated_at"].replace("Z", "+00:00"))
                    now = dt.now(timezone.utc)
                    age = (now - updated_time).total_seconds()
                    if age > 7200:  # 2 hours in seconds
                        print("WARNING: Algolia data appears stale (>2h old) — triggering fallback")
                        return []
                except (ValueError, TypeError):
                    pass

        return stories

    except Exception as e:
        print(f"WARNING: Failed to fetch HN stories: {e}")
        return []


def format_stories_for_prompt(stories: list[dict[str, Any]]) -> str:
    """
    Format story list as numbered text block for Claude prompt injection.

    Args:
        stories: List of story dicts from fetch_hn_stories

    Returns:
        Formatted numbered string with story details, or empty string if no stories
    """
    if not stories:
        return ""

    lines = []
    for i, story in enumerate(stories, 1):
        hn_link = f'https://news.ycombinator.com/item?id={story["id"]}'
        line = f'{i}. Title: "{story["title"]}" | URL: {story["url"]} | Score: {story["score"]} | Comments: {story["comments"]} | HN Discussion: {hn_link}'
        lines.append(line)

    return "\n".join(lines)


def pick_random_relationship() -> str:
    """Pick a random relationship from the data file."""
    relationships = load_list_from_file("relationships.txt")
    return random.choice(relationships)


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


def get_random_situation() -> str:
    """
    Pick a random situation from the data file.

    Returns:
        A random situation string
    """
    situations = load_list_from_file("situations.txt")
    return random.choice(situations)


def build_digest_prompt(
    stories_text: str,
    situation: str,
    characters_text: str,
    readme_file: Path,
    situations_file: Path,
    adjectives_file: Path,
    animals_file: Path,
    relationships_file: Path,
    timestamp: str,
) -> str:
    """Build the prompt for normal mode (HN stories available)."""
    return f"""You are an autonomous agent that updates the file at {readme_file} daily with an AI news digest and a hilarious improv dialog.

Today's HN front page stories (sorted by score, highest first):
{stories_text}

Complete this ENTIRE workflow autonomously:

## Step 1: Determine Day Count
Read the file at: {readme_file}
Extract the current day count. Look for a line containing "Day" followed by a number (e.g., "Day 96" or "Days running... 96").
If no day count found, use 1 as the current count.
Calculate the new day count by adding 1.

## Step 2: Filter AI Stories
Review the HN stories above and select up to 10 that are AI-relevant, using this priority system:

**Tier 1 (highest priority)**: New model releases or major updates from OpenAI, Anthropic, Google, X AI (Grok)
**Tier 2**: Model developments from smaller companies, open-source models, Chinese AI companies, or alternate architectures (e.g., Nvidia Mamba-based models)
**Tier 3**: AI tooling updates — new developer tools, AI workflow tools, Claude Code updates, opencode, context-mode, agent frameworks
**Tier 4**: AI infrastructure or hardware news (GPUs, inference optimization, deployment)
**Tier 5 (lowest)**: AI research papers with practical implications

**Special rule**: The FIRST story in the list (highest score) must always be included if it's AI-related in ANY way, regardless of tier.

If fewer than 10 stories are AI-relevant, include only the ones that qualify. If ZERO stories are AI-relevant, skip the news table and write a note: "No AI news on HN today."

Select the ONE most interesting/impactful AI story for the characters to discuss in the improv.

## Step 3: Curate Data Files
Read ALL four data files and make exactly ONE edit to EACH file. Each edit is either an add, a remove, or a replace — at most +1 and/or -1 lines per file.

**{adjectives_file}** — Adjectives for character generation
- Must be funny, vivid, instantly recognizable (NOT colors, NOT SAT words)
- Good: 'caffeinated', 'unhinged', 'pompous'. Bad: 'recalcitrant', 'lugubrious', 'blue'
- Add a fresh funny one, OR remove a stale/unfunny one, OR replace a weak one

**{animals_file}** — Animals for character names
- Must be common, recognizable animals everyone knows
- Good: 'zebra', 'penguin', 'raccoon'. Bad: 'aye-aye', 'pangolin', 'dugong'
- Add a fun common animal, OR remove an obscure one, OR replace one

**{situations_file}** — Comedic backdrops for improv scenes
- Format: starts with "they" or "one of them" to anchor to the animal characters
- Should be ongoing activities/predicaments, not single moments
- Prefer ADDING new situations over removing — there are always funny new ones to devise
- Only remove or replace if one is genuinely trite, stale, or unfunny

**{relationships_file}** — Relationship between the two characters
- Must be instantly recognizable with comedic potential
- Good: 'ex', 'landlord', 'parole officer'. Bad: 'acquaintance', 'pen pal'
- Add a fun relationship, OR remove a weak one, OR replace one

Use the Edit tool for each file. Report what you changed and why.

## Step 5: Write the Improv Dialog
Characters (2): {characters_text}
Situation (comedic backdrop): {situation}

The characters are discussing the AI story you selected in Step 2, WHILE dealing with the situation above.
The situation is the BACKDROP — the AI news is the TOPIC.

Example: "A nervous raccoon and hopeful giraffe debate whether GPT-5 will replace them while simultaneously managing a retirement party where the retiree has barricaded themselves in the office."

Requirements:
- Use both characters
- Format: CHARACTER NAME: "dialog line"
- 20-30 lines maximum — short and punchy is funnier than long
- Characters discuss the AI story with opinions, reactions, hot takes
- The situation creates comedic pressure/interruptions throughout
- Use the characters' adjectives to inform their personality
- Have a clear beginning, middle, and punchline ending
- Keep it clean and work-appropriate

## Step 6: Update {readme_file}
Write a new file at: {readme_file}
Use this EXACT structure:

```markdown
# 🤖 AI Digest & Improv — Day [NEW DAY COUNT] ({timestamp})

## 🗞️ Today's AI News

| # | Story | Type | Synopsis | Points | Comments |
|---|-------|------|----------|--------|----------|
| 1 | [Story Title](url) | Palace Intrigue | uv/ruff creators acquired by OpenAI | 499 | [341](https://news.ycombinator.com/item?id=...) |
| 2 | [Story Title](url) | Open Source Tool | GPU-accelerated robot control framework | 351 | [231](https://news.ycombinator.com/item?id=...) |
[up to 10 rows — only AI-relevant stories]

---

## 🎭 The Characters Weigh In

*[Narrative sentence: "A [adj] [animal] and [adj] [animal] discuss [story topic] while [situation]..."]*

[CHARACTER NAME 1]: "dialog line"

[CHARACTER NAME 2]: "dialog line"

[Continue full dialog...]

---

*This README is autonomously updated daily by a Claude agent that fetches top AI stories from Hacker News, filters them through a 5-tier relevance system, and has randomly generated characters discuss the most interesting one — all while trapped in an absurd comedic situation. No human intervention required.*

*Day [NEW DAY COUNT] | Last updated: {timestamp}*
```

IMPORTANT formatting rules:
- Character names in UPPERCASE followed by colon: NERVOUS RACCOON: "line"
- The narrative sentence in italics (*like this*)
- Story titles in the table as markdown links: [Title](url)
- Comments column: link to HN discussion page like [341](https://news.ycombinator.com/item?id=12345) — use the HN Discussion URL provided in the story data
- Type column: short classification of the story (e.g. "Model Release", "Palace Intrigue", "Open Source Tool", "Research Paper", "Dev Tooling", "Infrastructure", "AI Hardware")
- Synopsis column: 10 words or fewer describing what the story is about

Report your progress as you complete each step."""


def build_fallback_prompt(
    characters_text: str,
    readme_file: Path,
    situations_file: Path,
    adjectives_file: Path,
    animals_file: Path,
    relationships_file: Path,
    timestamp: str,
) -> str:
    """Build the prompt for fallback mode (no HN stories available)."""
    return f"""You are an autonomous agent that updates the file at {readme_file} daily with a hilarious improv dialog.

TODAY THERE ARE NO AI STORIES ON HACKER NEWS.

The characters exist to discuss AI news. But there is none. This is an existential crisis.

Complete this ENTIRE workflow autonomously:

## Step 1: Determine Day Count
Read the file at: {readme_file}
Extract the current day count. Look for a line containing "Day" followed by a number.
If no day count found, use 1 as the current count.
Calculate the new day count by adding 1.

## Step 2: Curate Data Files
Read ALL four data files and make exactly ONE edit to EACH file. Each edit is either an add, a remove, or a replace — at most +1 and/or -1 lines per file.

**{adjectives_file}** — Adjectives for character generation
- Must be funny, vivid, instantly recognizable (NOT colors, NOT SAT words)
- Good: 'caffeinated', 'unhinged', 'pompous'. Bad: 'recalcitrant', 'lugubrious', 'blue'
- Add a fresh funny one, OR remove a stale/unfunny one, OR replace a weak one

**{animals_file}** — Animals for character names
- Must be common, recognizable animals everyone knows
- Good: 'zebra', 'penguin', 'raccoon'. Bad: 'aye-aye', 'pangolin', 'dugong'
- Add a fun common animal, OR remove an obscure one, OR replace one

**{situations_file}** — Comedic backdrops for improv scenes
- Format: starts with "they" or "one of them" to anchor to the animal characters
- Should be ongoing activities/predicaments, not single moments
- Prefer ADDING new situations over removing — there are always funny new ones to devise
- Only remove or replace if one is genuinely trite, stale, or unfunny

**{relationships_file}** — Relationship between the two characters
- Must be instantly recognizable with comedic potential
- Good: 'ex', 'landlord', 'parole officer'. Bad: 'acquaintance', 'pen pal'
- Add a fun relationship, OR remove a weak one, OR replace one

Use the Edit tool for each file. Report what you changed and why.

## Step 3: Write the Improv Dialog
Characters (2): {characters_text}

The characters are AI-generated beings whose sole purpose is to react to AI news. Today there is NONE.

Write an improv dialog where the characters CONFRONT the absence of AI news. Play up the existential comedy:
- Are they still relevant if there's nothing to discuss?
- Do they exist if there's no AI news?
- Can they discuss the absence itself?
- Is this meta? Are they becoming self-aware?

Requirements:
- Use both characters
- Format: CHARACTER NAME: "dialog line"
- 20-30 lines maximum — short and punchy is funnier than long
- Use characters' adjectives to inform their personality
- Have a clear beginning, middle, and punchline ending
- Keep it clean and work-appropriate

## Step 4: Update {readme_file}
Write a new file at: {readme_file}
Use this EXACT structure:

```markdown
# 🤖 AI Digest & Improv — Day [NEW DAY COUNT] ({timestamp})

> *No AI news on HN today. The characters are... processing this.*

---

## 🎭 The Characters Process the Void

*[Narrative sentence describing the existential situation]*

[CHARACTER NAME 1]: "dialog line"

[CHARACTER NAME 2]: "dialog line"

[Continue full dialog...]

---

*This README is autonomously updated daily by a Claude agent. When AI news is available, it fetches top stories from Hacker News and has characters discuss them. Today there was nothing. The characters handled it... uniquely.*

*Day [NEW DAY COUNT] | Last updated: {timestamp}*
```

Report your progress as you complete each step."""


async def run_autonomous_agent() -> None:
    """
    Run the autonomous HN AI digest + improv agent with a single comprehensive prompt.
    """

    print("Starting HN AI Digest + Improv Agent")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working directory: {PROJECT_ROOT}\n")

    # Step 1: Fetch HN stories
    print("Fetching HN front page stories...")
    async with aiohttp.ClientSession() as session:
        stories = await fetch_hn_stories(session)

    if stories:
        print(f"Fetched {len(stories)} stories from HN")
        stories_text = format_stories_for_prompt(stories)
        fallback_mode = False
    else:
        print("No HN stories available — running in fallback (classic improv) mode")
        stories_text = ""
        fallback_mode = True

    # Step 2: Generate character pool (always 3, always dialogue)
    characters = generate_random_characters(2)
    relationship = pick_random_relationship()
    characters_text = ", ".join(characters)
    characters_text += f"\nRelationship twist: {characters[0]} is {characters[1]}'s {relationship}"
    print(f"Character pool: {characters_text}\n")

    # Get the paths to data files for Claude to edit
    readme_file = PROJECT_ROOT / "README.md"
    situations_file = DATA_DIR / "situations.txt"
    adjectives_file = DATA_DIR / "adjectives.txt"
    animals_file = DATA_DIR / "animals.txt"
    relationships_file = DATA_DIR / "relationships.txt"

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

    # Build the prompt based on mode
    if not fallback_mode:
        # Pick random situation only in normal mode
        situation = get_random_situation()
        print(f"Situation: {situation}")
        prompt = build_digest_prompt(
            stories_text=stories_text,
            situation=situation,
            characters_text=characters_text,
            readme_file=readme_file,
            situations_file=situations_file,
            adjectives_file=adjectives_file,
            animals_file=animals_file,
            relationships_file=relationships_file,
            timestamp=timestamp,
        )
    else:
        prompt = build_fallback_prompt(
            characters_text=characters_text,
            readme_file=readme_file,
            situations_file=situations_file,
            adjectives_file=adjectives_file,
            animals_file=animals_file,
            relationships_file=relationships_file,
            timestamp=timestamp,
        )

    async with ClaudeSDKClient(options=options) as client:
        print("Launching autonomous workflow...\n")
        print("=" * 60)

        await client.query(prompt)

        # Stream Claude's response and print progress
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

        print("\n" + "=" * 60)
        print("Agent completed successfully!")
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
