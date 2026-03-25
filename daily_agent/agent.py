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
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
from bs4 import BeautifulSoup

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)

try:
    from claude_agent_sdk import TaskNotificationMessage, TaskStartedMessage
except ImportError:
    TaskNotificationMessage = None
    TaskStartedMessage = None
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
    Fetch Hacker News stories from the last 24 hours via Algolia API.

    Queries all stories (not just current front page) from the past 24h,
    sorted by popularity. Filters out hiring/job posts.

    Args:
        session: aiohttp ClientSession for making HTTP requests

    Returns:
        List of story dicts with keys: id, title, url, score, comments, author, created_at, updated_at, text
        Sorted by score descending. Returns empty list on error.
    """
    try:
        cutoff = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
        url = (
            f"https://hn.algolia.com/api/v1/search?tags=story"
            f"&numericFilters=created_at_i>{cutoff}"
            f"&hitsPerPage=200"
        )
        async with session.get(url) as resp:
            data = await resp.json()

        stories = []
        for hit in data.get("hits", []):
            title = hit.get("title", "")

            # Filter out hiring/job posts
            title_lower = title.lower()
            if "is hiring" in title_lower or "who is hiring" in title_lower:
                continue

            story = {
                "id": int(hit.get("objectID", 0)),
                "title": title,
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "score": hit.get("points", 0) or 0,
                "comments": hit.get("num_comments", 0) or 0,
                "author": hit.get("author", ""),
                "created_at": hit.get("created_at", ""),
                "updated_at": hit.get("updated_at", ""),
                "text": hit.get("story_text", ""),
            }
            stories.append(story)

        # Sort by score descending
        stories.sort(key=lambda s: s["score"], reverse=True)

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


# ---------------------------------------------------------------------------
# AI Lab Blog Fetching (OpenAI, Google AI, Anthropic)
# ---------------------------------------------------------------------------

_RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AINewspaper/1.0; +https://github.com/ncejda/ncejda-g2)"
}


async def fetch_rss_posts(
    session: aiohttp.ClientSession,
    feed_url: str,
    source_name: str,
    max_age_days: int = 2,
) -> list[dict[str, Any]]:
    """
    Fetch and parse an RSS/Atom feed, returning recent posts.

    Args:
        session: aiohttp ClientSession for making HTTP requests
        feed_url: URL of the RSS/Atom feed
        source_name: Human-readable label (e.g. "OpenAI", "Google AI")
        max_age_days: Only include posts published within this many days

    Returns:
        List of post dicts with keys: title, url, date, date_obj, source, summary, category
    """
    try:
        async with session.get(
            feed_url,
            headers=_RSS_HEADERS,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                print(f"WARNING: RSS feed {feed_url} returned status {resp.status}")
                return []
            text = await resp.text()

        feed = feedparser.parse(text)
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        posts: list[dict[str, Any]] = []
        for entry in feed.entries[:30]:
            # Parse published date
            published: datetime | None = None
            for attr in ("published_parsed", "updated_parsed"):
                parsed = getattr(entry, attr, None)
                if parsed:
                    published = datetime(*parsed[:6], tzinfo=timezone.utc)
                    break

            if published and published < cutoff:
                continue

            # Extract category/tag
            category = ""
            if hasattr(entry, "tags") and entry.tags:
                category = entry.tags[0].get("term", "")

            post = {
                "title": entry.get("title", "").strip(),
                "url": entry.get("link", ""),
                "date": published.strftime("%b %d, %Y") if published else "Unknown",
                "date_obj": published,
                "source": source_name,
                "summary": (entry.get("summary") or "").strip()[:200],
                "category": category,
            }
            if post["title"] and post["url"]:
                posts.append(post)

        return posts

    except Exception as e:
        print(f"WARNING: Failed to fetch RSS feed {feed_url}: {e}")
        return []


async def fetch_anthropic_posts(
    session: aiohttp.ClientSession,
    max_age_days: int = 2,
) -> list[dict[str, Any]]:
    """
    Scrape recent blog posts from Anthropic's engineering, news, and research pages.

    Anthropic does not provide an RSS feed, so we parse HTML directly.

    Args:
        session: aiohttp ClientSession
        max_age_days: Only include posts published within this many days

    Returns:
        List of post dicts (same schema as fetch_rss_posts)
    """
    pages = [
        ("https://www.anthropic.com/engineering", "Engineering"),
        ("https://www.anthropic.com/news", "News"),
        ("https://www.anthropic.com/research", "Research"),
    ]

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    all_posts: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for page_url, category in pages:
        try:
            async with session.get(
                page_url,
                headers=_RSS_HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    print(f"WARNING: Anthropic {category} page returned {resp.status}")
                    continue
                html = await resp.text()

            soup = BeautifulSoup(html, "html.parser")

            for a_tag in soup.find_all("a", href=True):
                href: str = a_tag["href"]

                # Match blog post URL patterns
                if not re.match(r"^/(engineering|news|research)/[a-z0-9]", href):
                    continue

                full_url = f"https://www.anthropic.com{href}"
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Extract title from headings inside the link
                title = ""
                heading = a_tag.find(["h2", "h3", "h4"])
                if heading:
                    title = heading.get_text(strip=True)
                if not title:
                    # Fallback: use meaningful text content
                    text = a_tag.get_text(" ", strip=True)
                    cleaned = re.sub(
                        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}",
                        "",
                        text,
                    ).strip()
                    if 10 < len(cleaned) < 200:
                        title = cleaned

                if not title:
                    continue

                # Extract date from card text
                card_text = a_tag.get_text(" ", strip=True)
                date_str = ""
                date_obj: datetime | None = None
                date_match = re.search(
                    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}",
                    card_text,
                )
                if date_match:
                    date_str = date_match.group()
                    try:
                        date_obj = datetime.strptime(
                            date_str.replace(",", ""), "%b %d %Y"
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

                if date_obj and date_obj < cutoff:
                    continue

                # Determine category from URL path
                post_category = category
                if href.startswith("/engineering/"):
                    post_category = "Engineering"
                elif href.startswith("/research/"):
                    post_category = "Research"
                elif href.startswith("/news/"):
                    post_category = "News"

                all_posts.append({
                    "title": title,
                    "url": full_url,
                    "date": date_str or "Unknown",
                    "date_obj": date_obj,
                    "source": "Anthropic",
                    "summary": "",
                    "category": post_category,
                })

        except Exception as e:
            print(f"WARNING: Failed to scrape Anthropic {category}: {e}")
            continue

    return all_posts


async def fetch_sitemap_posts(
    session: aiohttp.ClientSession,
    sitemap_url: str,
    source_name: str,
    url_prefix: str,
    max_age_days: int = 2,
) -> list[dict[str, Any]]:
    """
    Fetch recent posts from a sitemap.xml, filtering by URL prefix and lastmod date.

    Works for sites like xAI and Mistral that don't offer RSS but have well-structured
    sitemaps with <lastmod> timestamps.

    Args:
        session: aiohttp session
        sitemap_url: URL to the sitemap.xml
        source_name: Display name (e.g. "xAI", "Mistral")
        url_prefix: Only include URLs starting with this (e.g. "https://x.ai/news/")
        max_age_days: How far back to look

    Returns:
        List of post dicts with title derived from URL slug.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    posts: list[dict[str, Any]] = []

    try:
        async with session.get(
            sitemap_url,
            headers=_RSS_HEADERS,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                print(f"WARNING: {source_name} sitemap returned {resp.status}")
                return []
            xml_text = await resp.text()
    except Exception as e:
        print(f"WARNING: Failed to fetch {source_name} sitemap: {e}")
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"WARNING: Failed to parse {source_name} sitemap XML: {e}")
        return []

    # Sitemaps use the namespace: http://www.sitemaps.org/schemas/sitemap/0.9
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    for url_elem in root.findall("sm:url", ns):
        loc_elem = url_elem.find("sm:loc", ns)
        if loc_elem is None or loc_elem.text is None:
            continue

        loc = loc_elem.text.strip()
        if not loc.startswith(url_prefix):
            continue

        slug = loc.removeprefix(url_prefix).strip("/")
        if not slug:
            continue

        date_obj: datetime | None = None
        date_str = ""
        lastmod_elem = url_elem.find("sm:lastmod", ns)
        if lastmod_elem is not None and lastmod_elem.text:
            raw = lastmod_elem.text.strip()
            # Try ISO format variants: 2026-03-24T12:00:00+00:00 or 2026-03-24
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    date_obj = datetime.strptime(raw, fmt)
                    if date_obj.tzinfo is None:
                        date_obj = date_obj.replace(tzinfo=timezone.utc)
                    date_str = date_obj.strftime("%b %d, %Y")
                    break
                except ValueError:
                    continue

        if date_obj and date_obj < cutoff:
            continue

        # Derive title from slug: "my-cool-post" → "My Cool Post"
        title = slug.replace("-", " ").replace("_", " ").title()

        posts.append({
            "title": title,
            "url": loc,
            "date": date_str or "Unknown",
            "date_obj": date_obj,
            "source": source_name,
            "summary": "",
            "category": "Blog",
        })

    return posts


async def fetch_ai_lab_posts(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """
    Fetch recent blog posts from all tracked AI labs in parallel.

    Sources: OpenAI (RSS), Google AI (RSS), Anthropic (HTML scraping),
    xAI (sitemap), Mistral (sitemap).

    Returns:
        Combined list of posts sorted by date (newest first).
        Posts without a parseable date appear last.
    """
    results = await asyncio.gather(
        fetch_rss_posts(session, "https://openai.com/blog/rss.xml", "OpenAI"),
        fetch_rss_posts(session, "https://blog.google/technology/ai/rss/", "Google AI"),
        fetch_anthropic_posts(session),
        fetch_sitemap_posts(session, "https://x.ai/sitemap.xml", "xAI", "https://x.ai/news/"),
        fetch_sitemap_posts(session, "https://mistral.ai/sitemap.xml", "Mistral", "https://mistral.ai/news/"),
        return_exceptions=True,
    )

    all_posts: list[dict[str, Any]] = []
    source_names = ["OpenAI", "Google AI", "Anthropic", "xAI", "Mistral"]
    for posts, name in zip(results, source_names):
        if isinstance(posts, BaseException):
            print(f"WARNING: Failed to fetch {name} posts: {posts}")
        else:
            all_posts.extend(posts)

    # Sort newest first; posts without dates go last
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    all_posts.sort(key=lambda p: p.get("date_obj") or epoch, reverse=True)

    return all_posts


def format_lab_posts_for_prompt(posts: list[dict[str, Any]]) -> str:
    """
    Format AI lab posts as a numbered text block for Claude prompt injection.

    Args:
        posts: List of post dicts from fetch_ai_lab_posts

    Returns:
        Formatted numbered string, or empty string if no posts
    """
    if not posts:
        return ""

    lines = []
    for i, post in enumerate(posts, 1):
        line = (
            f'{i}. Title: "{post["title"]}" | URL: {post["url"]}'
            f' | Source: {post["source"]} | Category: {post.get("category", "General")}'
            f' | Date: {post["date"]}'
        )
        if post.get("summary"):
            line += f" | Summary: {post['summary'][:100]}"
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
    story_count: int,
    lab_posts_text: str,
    lab_post_count: int,
    situation: str,
    characters_text: str,
    readme_file: Path,
    situations_file: Path,
    adjectives_file: Path,
    animals_file: Path,
    relationships_file: Path,
    timestamp: str,
) -> str:
    """Build the prompt for normal mode (HN stories and/or lab posts available)."""

    hn_section = ""
    if stories_text:
        hn_section = f"""
## Step 2: Filter HN Stories
When you read the README in Step 1, also extract ALL story titles and URLs from the existing news tables (both Hacker News AND AI Labs).
**Do NOT include any story or post that appeared in yesterday's tables** — readers want fresh content.

You have a "classifier" sub-agent available — a fast, cheap Haiku model that can classify all {story_count} stories for AI relevance in one batch. Consider sending it the full numbered story list (titles, URLs, scores — it uses all signals, not just titles). Then apply the tier system and dedup against yesterday's tables yourself.

Select up to 10 that are AI-relevant AND NOT in yesterday's tables, using this priority system:

**Tier 1 (highest priority)**: New model releases or major updates from OpenAI, Anthropic, Google, X AI (Grok)
**Tier 2**: Model developments from smaller companies, open-source models, Chinese AI companies, or alternate architectures (e.g., Nvidia Mamba-based models)
**Tier 3**: AI tooling updates — new developer tools, AI workflow tools, Claude Code updates, opencode, context-mode, agent frameworks
**Tier 4**: AI infrastructure or hardware news (GPUs, inference optimization, deployment)
**Tier 5 (lowest)**: AI research papers with practical implications

**Special rule**: The FIRST story in the list (highest score) must always be included if it's AI-related in ANY way, regardless of tier.

If fewer than 10 stories are AI-relevant, include only the ones that qualify. If ZERO stories are AI-relevant, skip the HN table and write a note: "No AI news on HN today."
"""

    lab_section = ""
    if lab_posts_text:
        lab_section = f"""
## Step 3: Review AI Lab Posts
Recent blog posts from OpenAI, Google AI, Anthropic, xAI, and Mistral ({lab_post_count} posts found):
{lab_posts_text}

Filter these posts for the "From the AI Labs" table. ONLY include posts about:
- Model releases, updates, or benchmarks
- Research papers, technical deep-dives, or novel methods
- Engineering opinion pieces, design philosophy, or architecture insights
- Developer tools, APIs, or platform capabilities

EXCLUDE posts about:
- Hiring, job openings, or team announcements
- C-suite changes or leadership news
- Lawsuits, legal disputes, or regulatory filings
- Funding rounds, partnerships, or business deals
- Generic company PR, event recaps, or awards

If a post title is ambiguous, use WebFetch to skim it before deciding. Dedup against yesterday's AI Labs table to avoid repeats.
"""
    elif not stories_text:
        lab_section = """
## Step 3: AI Lab Posts
No recent posts found from AI labs. Skip the AI Labs section.
"""

    return f"""You are an autonomous agent that updates the file at {readme_file} daily as "The AI Newspaper" — a daily briefing with Hacker News AI stories, official AI lab blog posts, and a comic strip.

{"Today's HN stories from the last 24 hours (sorted by score, highest first):" if stories_text else "No HN stories were available today."}
{stories_text}

Complete this ENTIRE workflow autonomously:

## Step 1: Determine Day Count
Read the file at: {readme_file}
Extract the current day count. Look for a line containing "Day" followed by a number (e.g., "Day 96" or "Days running... 96").
If no day count found, use 1 as the current count.
Calculate the new day count by adding 1.
{hn_section}{lab_section}
## Step 4: Curate Data Files
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

## Step 5: Research the Story
Pick the ONE most interesting/impactful story from EITHER the HN stories or the AI Lab posts — whichever is most newsworthy today. Use WebFetch to read the article so you understand:
- What specifically happened (not just the headline)
- Key facts, numbers, or quotes
- Why it matters

This prevents the characters from making bold but wrong factual claims. You only need to research the one story you're writing about.

## Step 6: Write the Comic Strip
Characters (2): {characters_text}
Situation (comedic backdrop): {situation}

The characters are discussing the story you selected in Step 5, WHILE dealing with the situation above.
The situation is the BACKDROP — the AI news is the TOPIC.

Example: "A nervous raccoon and hopeful giraffe debate whether GPT-5 will replace them while simultaneously managing a retirement party where the retiree has barricaded themselves in the office."

Requirements:
- Use both characters
- Format: CHARACTER NAME: "dialog line"
- 20-30 lines maximum — short and punchy is funnier than long
- Characters discuss the story with opinions, reactions, hot takes
- The situation creates comedic pressure/interruptions throughout
- Use the characters' adjectives to inform their personality
- Have a clear beginning, middle, and punchline ending
- Keep it clean and work-appropriate

## Step 7: Update {readme_file}
Write a new file at: {readme_file}
Use this EXACT structure:

```markdown
# 📰 The AI Newspaper — Day [NEW DAY COUNT] ({timestamp})

*AI curated AI news for humans*

## 🗞️ Hacker News

| # | Story | Type | Synopsis | Points | Comments |
|---|-------|------|----------|--------|----------|
| 1 | [Story Title](url) | Palace Intrigue | uv/ruff creators acquired by OpenAI | 499 | [341](https://news.ycombinator.com/item?id=...) |
| 2 | [Story Title](url) | Open Source Tool | GPU-accelerated robot control framework | 351 | [231](https://news.ycombinator.com/item?id=...) |
[up to 10 rows — only AI-relevant stories, or "No AI news on HN today." if none]

---

## 🔬 From the AI Labs

| # | Post | Lab | Category | Date |
|---|------|-----|----------|------|
| 1 | [Post Title](url) | Anthropic | Engineering | Mar 24 |
| 2 | [Post Title](url) | OpenAI | Research | Mar 23 |
[all recent lab posts, or "No new lab posts this week." if none]

---

## 🎭 The Comic Strip

*[Narrative sentence: "A [adj] [animal] and [adj] [animal] discuss [story topic] while [situation]..."]*

[CHARACTER NAME 1]: "dialog line"

[CHARACTER NAME 2]: "dialog line"

[Continue full dialog...]

---

*The AI Newspaper is autonomously generated daily by a Claude agent. It scrapes Hacker News for AI stories, monitors blogs from OpenAI, Anthropic, Google AI, xAI, and Mistral, and has randomly generated animal characters debate the most interesting story — all while trapped in an absurd comedic situation.*

*Day [NEW DAY COUNT] | Last updated: {timestamp}*
```

IMPORTANT formatting rules:
- Character names in UPPERCASE followed by colon: NERVOUS RACCOON: "line"
- The narrative sentence in italics (*like this*)
- Story titles in both tables as markdown links: [Title](url)
- HN Comments column: link to HN discussion like [341](https://news.ycombinator.com/item?id=12345)
- HN Type column: short classification (e.g. "Model Release", "Palace Intrigue", "Open Source Tool", "Research Paper", "Dev Tooling", "Infrastructure", "AI Hardware")
- HN Synopsis column: 10 words or fewer describing the story
- AI Labs table: Lab column shows the source (OpenAI, Anthropic, Google AI, xAI, Mistral), Category shows the post type (e.g. "Model Release", "Research", "Engineering", "Developer Tools"), Date is short format (e.g. "Mar 24")
- If a section has no content, include the section header with an italicized note

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
    """Build the prompt for fallback mode (no news from any source)."""
    return f"""You are an autonomous agent that updates the file at {readme_file} daily as "The AI Newspaper."

TODAY THERE IS NO AI NEWS — nothing from Hacker News, nothing from OpenAI, Anthropic, or Google AI blogs.

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

## Step 3: Write the Comic Strip
Characters (2): {characters_text}

The characters are AI-generated beings whose sole purpose is to react to AI news. Today there is NONE.

Write a comic strip dialog where the characters CONFRONT the absence of AI news. Play up the existential comedy:
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
# 📰 The AI Newspaper — Day [NEW DAY COUNT] ({timestamp})

*AI curated AI news for humans*

> *No AI news today — nothing from Hacker News, nothing from the labs. The characters are... processing this.*

---

## 🎭 The Comic Strip

*[Narrative sentence describing the existential situation]*

[CHARACTER NAME 1]: "dialog line"

[CHARACTER NAME 2]: "dialog line"

[Continue full dialog...]

---

*The AI Newspaper is autonomously generated daily by a Claude agent. It scrapes Hacker News for AI stories, monitors OpenAI/Anthropic/Google AI blogs for new posts, and has randomly generated animal characters debate the most interesting story. Today there was nothing. The characters handled it... uniquely.*

*Day [NEW DAY COUNT] | Last updated: {timestamp}*
```

Report your progress as you complete each step."""


async def run_autonomous_agent() -> None:
    """Run the autonomous AI Newspaper agent with a single comprehensive prompt."""

    print("Starting The AI Newspaper Agent")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working directory: {PROJECT_ROOT}\n")

    async with aiohttp.ClientSession() as session:
        print("Fetching HN stories and AI lab posts in parallel...")
        hn_task = fetch_hn_stories(session)
        lab_task = fetch_ai_lab_posts(session)
        stories, lab_posts = await asyncio.gather(hn_task, lab_task)

    if stories:
        print(f"Fetched {len(stories)} stories from HN")
        stories_text = format_stories_for_prompt(stories)
    else:
        print("No HN stories available")
        stories_text = ""

    if lab_posts:
        print(f"Fetched {len(lab_posts)} posts from AI labs")
        lab_posts_text = format_lab_posts_for_prompt(lab_posts)
    else:
        print("No recent AI lab posts found")
        lab_posts_text = ""

    has_any_news = bool(stories_text or lab_posts_text)

    characters = generate_random_characters(2)
    relationship = pick_random_relationship()
    characters_text = ", ".join(characters)
    characters_text += f"\nRelationship twist: {characters[0]} is {characters[1]}'s {relationship}"
    print(f"Character pool: {characters_text}\n")

    readme_file = PROJECT_ROOT / "README.md"
    situations_file = DATA_DIR / "situations.txt"
    adjectives_file = DATA_DIR / "adjectives.txt"
    animals_file = DATA_DIR / "animals.txt"
    relationships_file = DATA_DIR / "relationships.txt"

    timestamp = datetime.now().strftime("%Y-%m-%d")

    options = ClaudeAgentOptions(
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "WebFetch",
        ],
        permission_mode="acceptEdits",
        cwd=str(PROJECT_ROOT),
        model="sonnet",
        agents={
            "classifier": AgentDefinition(
                description=(
                    "Fast, cheap AI-relevance classifier. Send it a batch of HN story titles "
                    "and it will return which ones are AI-related. Use this when you have a large "
                    "number of stories to filter — it's much faster than reviewing them yourself."
                ),
                prompt=(
                    "You are a fast binary classifier. You receive HN stories (title, URL, score, "
                    "comments) and must identify which are related to AI, machine learning, LLMs, "
                    "or AI tooling.\n\n"
                    "Use ALL available signals — titles can be misleading, so pay attention to:\n"
                    "- URL domains (arxiv.org, openai.com, anthropic.com, huggingface.co = strong AI signal)\n"
                    "- URL paths (e.g. /blog/ai-, /papers/, /models/)\n"
                    "- Score and comment count (high engagement on borderline stories = include)\n"
                    "- You have WebFetch available — if a title is ambiguous and the URL looks like it "
                    "might be AI-related, fetch the page to check. Don't fetch everything, just the "
                    "borderline cases where the title alone isn't clear.\n\n"
                    "AI-relevant includes: model releases, AI company news/acquisitions, AI tools/IDEs, "
                    "AI research papers, AI policy/regulation/lawsuits, AI infrastructure/hardware, "
                    "AI coding assistants, robotics/autonomous systems, AI ethics/safety, and "
                    "AI-adjacent stories (e.g. ArXiv platform news, facial recognition, self-driving).\n\n"
                    "NOT AI-relevant: general programming, non-AI startups, hardware without AI, "
                    "science without ML, politics without AI angle, culture/lifestyle.\n\n"
                    "When in doubt, INCLUDE the story — it's better to surface a borderline story "
                    "than miss a relevant one. The main agent will make the final call.\n\n"
                    "Respond with ONLY a JSON array of the story numbers (1-indexed) that are AI-relevant. "
                    "Example: [1, 5, 12, 37]"
                ),
                model="haiku",
                tools=["WebFetch"],
            ),
        },
    )

    if has_any_news:
        situation = get_random_situation()
        print(f"Situation: {situation}")
        prompt = build_digest_prompt(
            stories_text=stories_text,
            story_count=len(stories),
            lab_posts_text=lab_posts_text,
            lab_post_count=len(lab_posts),
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
        print("No news from any source — running in fallback mode")
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

        async for message in client.receive_response():
            if TaskStartedMessage and isinstance(message, TaskStartedMessage):
                print(f"\n🔀 Sub-agent started: {message.task_type}")
            elif TaskNotificationMessage and isinstance(message, TaskNotificationMessage):
                print(f"✅ Sub-agent completed")
            elif isinstance(message, AssistantMessage):
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
