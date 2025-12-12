#!/usr/bin/env python3
"""
Autonomous README Agent using Claude Agent SDK

This agent runs daily and:
1. Generates 1-3 random characters (adjective + animal)
2. Fetches a random XKCD comic
3. Uses Claude to write a funny short story combining them
4. Generates an illustration with DALL-E
5. Updates README.md
6. Commits and pushes to GitHub
"""

import asyncio
import os
import random
import sys
from datetime import datetime
from pathlib import Path

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
    generate_dalle_image,
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
    "crying",
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
    """Run the autonomous README update agent."""

    print("🤖 Starting Autonomous README Agent")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Working directory: {PROJECT_ROOT}\n")

    # Create custom tools MCP server
    tools_server = create_sdk_mcp_server(
        name="readme-tools",
        version="1.0.0",
        tools=[
            get_max_xkcd_number,
            fetch_xkcd_comic,
            generate_dalle_image,
            download_image,
        ],
    )

    # Configure agent options
    options = ClaudeAgentOptions(
        # Make custom tools available
        mcp_servers={"readme-tools": tools_server},
        # Allow both built-in and custom tools
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "Bash",
            "mcp__readme-tools__get_max_xkcd_number",
            "mcp__readme-tools__fetch_xkcd_comic",
            "mcp__readme-tools__generate_dalle_image",
            "mcp__readme-tools__download_image",
        ],
        # Auto-accept edits for autonomous operation
        permission_mode="acceptEdits",
        # Set working directory
        cwd=str(PROJECT_ROOT),
        # Use Sonnet for good balance of speed/capability
        model="sonnet",
    )

    # Create the agent client
    async with ClaudeSDKClient(options=options) as client:

        # ===== TASK 1: Read current README and get day count =====
        print("📖 [Task 1] Reading current README to get day count...\n")

        await client.query(
            "Read the README.md file and extract the current day count from the line "
            "'Days running a fully-autonomous agent that updates my README: X'. "
            "If the line doesn't exist, the day count is 0. "
            "Print just the number."
        )

        day_count = None
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"   {block.text}")
                        # Try to extract the day count
                        try:
                            day_count = int(
                                "".join(filter(str.isdigit, block.text)) or "0"
                            )
                        except:
                            pass

        new_day = (day_count or 0) + 1
        print(f"\n✅ Current day: {new_day}\n")

        # ===== TASK 2: Generate random characters (Pure Python - no AI) =====
        print("🎭 [Task 2] Generating random characters...\n")

        characters = generate_random_characters()
        characters_text = ", ".join(characters)
        print(f"   Generated: {characters_text}")
        print(f"\n✅ Characters: {characters_text}\n")

        # ===== TASK 3: Get random XKCD comic =====
        print("📰 [Task 3] Fetching random XKCD comic...\n")

        # First, get the max XKCD number
        await client.query(
            "Use get_max_xkcd_number tool to find the latest XKCD comic number. Print just the number."
        )

        max_xkcd = None
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"   {block.text}")
                        # Extract the number
                        try:
                            max_xkcd = int("".join(filter(str.isdigit, block.text)))
                        except:
                            pass

        if not max_xkcd:
            print("   ⚠️  Failed to get max XKCD number, using 3000 as fallback")
            max_xkcd = 3000

        # Use Python's random to pick a comic number (true randomness!)
        random_comic_num = random.randint(1, max_xkcd)
        print(f"   Randomly selected comic #{random_comic_num} (using Python random)")

        # Now fetch that specific comic
        await client.query(
            f"Use fetch_xkcd_comic tool with comic_number={random_comic_num} to get the comic details. "
            f"Parse the JSON response and print:\n"
            f"Title: TITLE\n"
            f"Alt: ALT_TEXT\n"
            f"URL: URL"
        )

        xkcd_title = ""
        xkcd_alt = ""
        xkcd_url = ""
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"   {block.text}")
                        # Extract title, alt, and URL
                        for line in block.text.split('\n'):
                            if line.startswith("Title:"):
                                xkcd_title = line.replace("Title:", "").strip()
                            elif line.startswith("Alt:"):
                                xkcd_alt = line.replace("Alt:", "").strip()
                            elif line.startswith("URL:"):
                                xkcd_url = line.replace("URL:", "").strip()

        print(f"\n✅ XKCD selected: {xkcd_title}\n")

        # ===== TASK 4: Create funny 3-panel story =====
        print(
            "✍️  [Task 4] Claude, write a funny 3-panel comic story...\n"
        )

        await client.query(
            f"You are a creative comedy writer. Create a funny, work-appropriate 3-panel comic story "
            f"featuring these characters: {characters_text}\n\n"
            f"The story should be inspired by the XKCD comic:\n"
            f"Title: {xkcd_title}\n"
            f"Context: {xkcd_alt}\n\n"
            f"Requirements:\n"
            f"- Split the story into exactly 3 panels\n"
            f"- Panel 1: Setup (1-2 sentences)\n"
            f"- Panel 2: Development (1-2 sentences)\n"
            f"- Panel 3: Punchline (1-2 sentences with unexpected, hilarious ending)\n"
            f"- Keep it clean and work-appropriate\n"
            f"- Make it absurd and silly\n\n"
            f"Format your response exactly like this:\n"
            f"PANEL 1: [text]\n"
            f"PANEL 2: [text]\n"
            f"PANEL 3: [text]"
        )

        panel1_text = ""
        panel2_text = ""
        panel3_text = ""
        full_story_text = ""

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"   {block.text}")
                        full_story_text += block.text + "\n"

                        # Parse panels
                        for line in block.text.split('\n'):
                            if line.startswith("PANEL 1:"):
                                panel1_text = line.replace("PANEL 1:", "").strip()
                            elif line.startswith("PANEL 2:"):
                                panel2_text = line.replace("PANEL 2:", "").strip()
                            elif line.startswith("PANEL 3:"):
                                panel3_text = line.replace("PANEL 3:", "").strip()

        print(f"\n✅ 3-panel story created\n")

        # ===== TASK 5: Generate single 3-panel comic strip image =====
        print("🎨 [Task 5] Generating 3-panel comic strip...\n")

        await client.query(
            f"Generate a single 3-panel comic strip image.\n\n"
            f"Use generate_dalle_image tool with this prompt:\n"
            f"'A horizontal 3-panel comic strip in cartoon style. Three panels arranged left to right, clearly divided. "
            f"Panel 1 (left): {panel1_text}. "
            f"Panel 2 (middle): {panel2_text}. "
            f"Panel 3 (right): {panel3_text}. "
            f"Comic book style with bold outlines, bright colors, and clear panel divisions. "
            f"Whimsical and fun illustration.'\n\n"
            f"Then extract the image URL and use download_image to save as 'day_{new_day:04d}.png'\n"
            f"Print the saved path."
        )

        comic_image_path = ""
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"   {block.text}")
                        if "daily_agent/generated_images" in block.text:
                            for line in block.text.split("\n"):
                                if "daily_agent/generated_images" in line:
                                    comic_image_path = line.strip().replace("Image saved successfully to:", "").strip()

        print(f"\n✅ Comic strip generated and saved: {comic_image_path}\n")

        # ===== TASK 6: Update README =====
        print("📝 [Task 6] Updating README.md...\n")

        timestamp = datetime.now().strftime("%Y-%m-%d")

        await client.query(
            f"Write a new README.md file with this exact content:\n\n"
            f"---BEGIN README---\n"
            f"# Autonomous README Project 🤖\n\n"
            f"**Days running a fully-autonomous agent that updates my README: {new_day}**\n\n"
            f"## Today's Comic ({timestamp})\n\n"
            f"### Characters\n"
            f"{characters_text}\n\n"
            f"### Inspired by XKCD\n"
            f"[**Comic #{random_comic_num}: {xkcd_title}**]({xkcd_url})\n\n"
            f"*{xkcd_alt}*\n\n"
            f"### The 3-Panel Story\n\n"
            f"**Panel 1:** {panel1_text}\n\n"
            f"**Panel 2:** {panel2_text}\n\n"
            f"**Panel 3:** {panel3_text}\n\n"
            f"<img src=\"{comic_image_path}\" width=\"800\" alt=\"3-panel comic strip\">\n\n"
            f"---\n\n"
            f"*This README is autonomously updated daily by a Claude agent that:*\n"
            f"*1. Generates random characters (adjective + animal combinations)*\n"
            f"*2. Fetches a random XKCD comic*\n"
            f"*3. Writes a funny 3-panel story combining them*\n"
            f"*4. Generates a 3-panel comic strip illustration with OpenAI's gpt-image-1*\n"
            f"*5. Commits and pushes to GitHub*\n\n"
            f"*Last updated: {timestamp}*\n"
            f"---END README---\n\n"
            f"Use the Write tool to create this file."
        )

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"   {block.text}")

        print(f"\n✅ README updated\n")

        # ===== TASK 7: Commit and push to GitHub =====
        print("🚀 [Task 7] Committing and pushing to GitHub...\n")

        await client.query(
            f"Run these git commands using the Bash tool:\n"
            f"1. git add .\n"
            f"2. git commit -m '🤖 Day {new_day} - Autonomous README update'\n"
            f"3. git push origin main\n"
            f"4. git log --oneline -1\n\n"
            f"Print the output of each command."
        )

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"   {block.text}")

        print(f"\n✅ Changes committed and pushed!\n")
        print("=" * 60)
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
