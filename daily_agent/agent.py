#!/usr/bin/env python3
"""
Fully Autonomous README Agent using Claude Agent SDK

This agent runs daily with a single comprehensive prompt that orchestrates the
entire workflow autonomously. Claude is provided with all tools upfront and
handles content creation.

Workflow:
1. Python fetches HN front page stories via Algolia API
2. Python generates random characters (adjective + animal) and picks a random place
3. Single comprehensive prompt is sent to Claude with Read, Write, Edit tools
4. Claude autonomously:
   - Reads README.md and extracts day count
   - Filters HN stories for AI relevance (5-tier system)
   - Selects up to 10 AI stories for the digest table
   - Picks ONE story for characters to discuss
   - Curates three data files (adjectives, animals, places)
     with exactly one edit each — add, remove, or replace
   - Writes comic strip dialog: characters discuss the AI story in a random place
   - Updates README.md with news table + comic strip
5. GitHub Actions handles the git commit and push
"""

import asyncio
import json
import random
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiohttp
import feedparser
from bs4 import BeautifulSoup
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
    create_sdk_mcp_server,
)
from custom_tools import generate_image
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(__file__).parent / "data"
SCENES_DIR = DATA_DIR / "comic_text"

def build_comic_style_direction(hat_first: str, hat_second: str) -> str:
    return (
        "A 6-panel comic in a minimalist modern flat-design aesthetic. "
        "Flat solid pastel colors only - pale lavender background, "
        "soft pastel-blue and pastel-pink characters with no shading or gradients. "
        "Characters are drawn as smooth simple geometric blob shapes with rounded bodies, "
        "oversized round heads, large round black-dot eyes, and minimal facial features. "
        "Characters are completely BALD - no hair, no ponytails, no fringe, no eyebrows, no facial hair. "
        "Characters are NOT gendered - androgynous featureless blobs distinguished only by color "
        "(one pastel-blue, one pastel-pink) and slight differences in body shape. "
        "EVERY character in EVERY panel wears their distinct hat - "
        f"the first character (the one with the first adjective in the scene) wears a {hat_first}, "
        f"the second character wears a {hat_second}. "
        "Each character's hat is consistent across all 6 panels and never comes off. "
        "The hats are clearly visible and rendered with comic exaggeration - oversized, silly, "
        "instantly recognizable. "
        "No outlines on the characters, no fur texture, no detailed anatomy, no clothing details "
        "beyond simple solid color body shapes (and the hats). "
        "All facial expressions are conveyed through eye shape and mouth shape only. "
        "Backgrounds are minimal - solid pastel color blocks suggesting the setting "
        "with maybe one or two simple geometric props. "
        "Speech bubbles are clean white rectangles with thin clean black borders "
        "and a small triangular pointer, with neat sentence-case dialog inside. "
        "Composition is calm and gentle - characters mostly facing each other. "
        "Avoid: anime, manga, hair, gendered features, cross-hatching, realistic features, "
        "glossy 3D shading, saturated colors, harsh contrast, action lines."
    )

COMIC_LAYOUT_DIRECTION = (
    "Layout: a 2x3 grid of comic panels (2 columns wide, 3 rows tall) with thin white gutters between them. "
    "Panel reading order: top-left, top-right, middle-left, middle-right, bottom-left, bottom-right. "
    "Tall portrait 1024x1792 aspect ratio. Each panel must be clearly delimited. "
    "No author signature, no watermarks, no text outside speech bubbles."
)


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
                "url": hit.get("url")
                or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
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

                all_posts.append(
                    {
                        "title": title,
                        "url": full_url,
                        "date": date_str or "Unknown",
                        "date_obj": date_obj,
                        "source": "Anthropic",
                        "summary": "",
                        "category": post_category,
                    }
                )

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

        posts.append(
            {
                "title": title,
                "url": loc,
                "date": date_str or "Unknown",
                "date_obj": date_obj,
                "source": source_name,
                "summary": "",
                "category": "Blog",
            }
        )

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
        fetch_sitemap_posts(
            session, "https://x.ai/sitemap.xml", "xAI", "https://x.ai/news/"
        ),
        fetch_sitemap_posts(
            session,
            "https://mistral.ai/sitemap.xml",
            "Mistral",
            "https://mistral.ai/news/",
        ),
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


SEEN_POSTS_FILE = DATA_DIR / "seen_lab_posts.json"
SEEN_POSTS_MAX_AGE_DAYS = 30


def load_seen_posts() -> dict[str, str]:
    """Load previously seen dateless lab post URLs with their first-seen dates.

    Returns:
        Dict mapping URL → first-seen date string (YYYY-MM-DD).
    """
    if not SEEN_POSTS_FILE.exists():
        return {}
    try:
        data = json.loads(SEEN_POSTS_FILE.read_text())
        return data.get("posts", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def save_seen_posts(seen: dict[str, str]) -> None:
    """Save seen dateless lab post URLs, pruning entries older than 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=SEEN_POSTS_MAX_AGE_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    pruned = {url: date for url, date in seen.items() if date >= cutoff_str}
    SEEN_POSTS_FILE.write_text(json.dumps({"posts": pruned}, indent=2) + "\n")


def filter_seen_dateless_posts(
    posts: list[dict[str, Any]], seen: dict[str, str]
) -> list[dict[str, Any]]:
    """Remove dateless posts already included in a previous run."""
    filtered = []
    removed = 0
    for post in posts:
        if post.get("date_obj") is None and post["url"] in seen:
            removed += 1
            continue
        filtered.append(post)
    if removed:
        print(f"Filtered {removed} previously seen dateless post(s)")
    return filtered


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


def get_random_place() -> str:
    """Pick a random place/setting from the data file."""
    places = load_list_from_file("places.txt")
    return random.choice(places)


def build_digest_prompt(
    stories_text: str,
    story_count: int,
    lab_posts_text: str,
    lab_post_count: int,
    place: str,
    characters_text: str,
    readme_file: Path,
    adjectives_file: Path,
    animals_file: Path,
    places_file: Path,
    hats_file: Path,
    scene_file: Path,
    hat_pair: tuple[str, str],
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

If a post title is ambiguous, use WebFetch to skim it before deciding. Dedup against yesterday's AI Labs table to avoid repeats. (Posts without clear dates that appeared in previous days have already been filtered out.)
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
Read all three data files and make exactly ONE edit to EACH file. Each edit is either an add, a remove, or a replace — at most +1 and/or -1 lines per file.

**{adjectives_file}** — Adjectives for character generation
- These adjectives drive a comic image, so they MUST be visually depictable. An illustrator must be able to draw a character that looks "<adjective>" at a glance — through posture, expression, body language, or accessory.
- Test before adding: "If I told an illustrator to draw a [word] character with no other context, would they instantly know what to draw?" If no, REJECT.
- GOOD (instantly visualizable): 'caffeinated', 'unhinged', 'pompous', 'sleep-deprived', 'sweaty', 'shivering', 'smug', 'panicked', 'overconfident', 'feral', 'overdressed', 'soggy'
- BAD (abstract concepts that don't translate to a single image): 'fiscally-irresponsible', 'aggressively-mediocre', 'tab-hoarding', 'enshittified', 'npc-coded', 'recalcitrant', 'lugubrious'
- BAD (descriptive but not character-defining): 'blue', 'tall', 'old' — these describe appearance, not personality
- Add a fresh visually-depictable one, OR remove an abstract/non-visual one, OR replace a weak one
- Audit hint: when reading the existing list, flag any that fail the illustrator test as candidates for removal/replacement.

**{places_file}** — Settings where the comic takes place
- Should be vivid, instantly recognizable locations with comedic potential
- Good: 'a haunted castle', 'underwater', 'in a broken-down elevator'. Bad: 'a room', 'outside'
- Add a fun new setting, OR remove a dull one, OR replace a weak one

**{hats_file}** — Absurd hats worn by the blob characters in the comic
- Each line is one hat — described as a noun phrase the image model can render directly
- Must be visually distinctive and instantly recognizable, with comedic potential
- Good: 'jester hat with three drooping bells', 'foam cowboy hat', 'tinfoil pyramid hat', 'beekeeper veil-and-hat combo'
- Bad: 'a hat', 'something nice' (too vague), 'metaphorical hat of regret' (not literal/visual)
- Add a fun new absurd hat, OR remove a dull one, OR replace a weak one

Use the Edit tool for each file. Report what you changed and why.

## Step 5: Research the Story
Pick the ONE most interesting/impactful story from EITHER the HN stories or the AI Lab posts — whichever is most newsworthy today. Use WebFetch to read the article so you understand:
- What specifically happened (not just the headline)
- Key facts, numbers, or quotes
- Why it matters

This prevents the characters from making bold but wrong factual claims. You only need to research the one story you're writing about.

## Step 6: Write the Comic Scene
Characters: pick two of these — {characters_text}
Use ONLY the adjectives — the characters are people whose appearance is implied by their adjective. Drop any species words. (The visual style of the rendering comes from the style block in Step 7 — do not describe style here.)

CRITICAL: an illustrator must be able to draw "[adjective] character" at a glance. If an adjective is abstract (e.g. "fiscally-irresponsible", "tab-hoarding") and you can't picture how it would look on a character's posture/expression, PICK DIFFERENT ADJECTIVES. If both candidates in the pool fail the illustrator test, regenerate by picking two different adjectives from the {adjectives_file} file directly. Strong visual adjectives lead to good comics.

Setting: {place}

The characters are {place}, discussing the story you selected in Step 5.

Example setup: "A nervous person and a hopeful person discuss GPT-5 in a haunted castle."

Write a short 6-panel comic scene. This text serves TWO purposes:
(a) it gets persisted to disk (Step 6.5) for the historical record
(b) it's the exact dialog source the image-gen call uses verbatim (Step 7)

Format the scene EXACTLY like this (header in italics, then 6 panel blocks):

```
*[narrative intro: "A [adj] person and a [adj] person discuss [story topic] {place}."]*

Panel 1:
[setup]
ADJECTIVE PERSON: "dialog line, max 12 words, must fit a speech bubble"

Panel 2:
[build]
OTHER ADJECTIVE PERSON: "dialog line"
OTHER ADJECTIVE PERSON: "second short line, optional"

Panel 3:
[pivot]
ADJECTIVE PERSON: "the reveal or twist line"

Panel 4:
[silent reaction]
[Visual: describe what is happening in this panel - usually a wordless beat reaction shot.]

Panel 5:
[punch]
ADJECTIVE PERSON: "punchline setup"
OTHER ADJECTIVE PERSON: "the punchline"

Panel 6:
[button]
[Visual: describe the closing visual beat — a sight gag, a reveal, etc. Optionally one final dialog line.]
ADJECTIVE PERSON: "final button line, optional"
```

Hard requirements:
- EXACTLY 6 panels (Panel 1 through Panel 6)
- Each panel begins with a `[beat-label]` line: setup, build, pivot, silent reaction, punch, button (use these exact labels)
- Panel 4 MUST be a wordless beat — only a `[Visual: ...]` line, no dialog. This silent beat is essential for comedic timing.
- Other panels can mix dialog and `[Visual: ...]` action notes. Use action notes for closeups, sight gags, screen contents, etc.
- Speech bubbles are short — each dialog line ≤12 words. Hard ceiling.
- Speaker labels are UPPERCASE: "EXISTENTIAL PERSON" not "existential rhino"
- 0-2 dialog lines per panel — vary it. Don't make every panel a back-and-forth.
- Use both characters across the scene. They don't both have to speak in every panel.
- Use the adjectives to inform personality. Use the setting for atmosphere — don't overforce it.
- Have a clear comedic arc: setup → build → pivot/reveal → silent reaction → punchline → button.
- Keep it clean and work-appropriate.
- Smart, specific dialog beats > generic punchlines. Reference real facts from the story.

## Step 6.5: Persist the Scene to Disk
Use the Write tool to save the EXACT scene text from Step 6 to: {scene_file}

This file is the source of truth for the comic. The image-gen call in Step 7 uses this same text, and the file is preserved for future reference.

## Step 7: Generate the Comic Image
Now turn the scene into a 6-panel image.

Compose a SINGLE image-generation prompt with all of:

1. **Style direction (use this paragraph verbatim — the hats are pre-assigned by the system, the FIRST adjective in your scene's narrative intro corresponds to the first hat below, the SECOND adjective to the second hat):**
{build_comic_style_direction(hat_pair[0], hat_pair[1])}

2. **Layout direction (use this paragraph verbatim):**
{COMIC_LAYOUT_DIRECTION}

3. **Scene context:** the narrative intro line from your scene (without the asterisks).

4. **Render this 6-panel comic. Use the dialog EXACTLY as written - do NOT paraphrase, do NOT shorten, do NOT rewrite. Some panels are SILENT (no speech bubbles) - that is intentional pacing, do not add dialog where none is written. Visual descriptions in [brackets] tell you what to draw in that panel.**
Then list each panel block (Panel 1 through Panel 6) with the exact dialog and visual notes from your scene. Format each panel block exactly as it appears in your scene file.

5. **Character anchors (style-neutral — visual aesthetic comes from §1, do NOT add style words here):** "Both characters are human. The model designs their appearance based on the adjectives — the {{first adjective}} character should look {{first adjective}} (clothing, posture, expression all reflect that trait), and the {{second adjective}} character should look {{second adjective}}. The two characters appear with consistent appearance, costume, and colors across all 6 panels. The setting backdrop ({place}) is visible in every panel. Vary panel composition: wide establishing shots, medium two-shots, close-ups for emotional beats."

Then call the image-generation tool. The tool name is `mcp__comic__generate_image`. Pass:
- `prompt`: the full image-gen prompt you composed above
- `filename`: `"comic_{timestamp}"` (the .png suffix is added automatically)

The tool will save the image to `daily_agent/generated_images/comic_{timestamp}.png` at 1024x1792 resolution. If the call fails (returns is_error: True), retry ONCE with a slightly tightened prompt. If it fails twice, proceed to Step 8 — the README will reference a missing image and we'll fix it next run.

## Step 8: Update {readme_file}
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

## The Comic Strip

*[Narrative sentence: "A [adj] person and a [adj] person discuss [story topic] [place]..."]*

<img src="daily_agent/generated_images/comic_{timestamp}.png" width="600" alt="Today's 6-panel comic strip">

---

*The AI Newspaper is autonomously generated daily by a Claude agent. It scrapes Hacker News for AI stories, monitors blogs from OpenAI, Anthropic, Google AI, xAI, and Mistral, and has two randomly generated characters debate the most interesting story in a random setting.*

*Day [NEW DAY COUNT] | Last updated: {timestamp}*
```

IMPORTANT formatting rules:
- The narrative sentence in italics (*like this*) — this is the only text in the comic section; the rest is the image
- Image embed must use the exact <img> HTML tag shown in the template (raw HTML, not markdown image syntax) so GitHub width-constrains it to 600px
- Image path must match the filename you passed to mcp__comic__generate_image (i.e. comic_{timestamp}.png)
- In speech bubbles drawn into the image, character names in UPPERCASE (e.g. EXISTENTIAL PERSON)
- Story titles in both tables as markdown links: [Title](url)
- HN Comments column: link to HN discussion like [341](https://news.ycombinator.com/item?id=12345)
- HN Type column: short classification (e.g. "Model Release", "Palace Intrigue", "Open Source Tool", "Research Paper", "Dev Tooling", "Infrastructure", "AI Hardware")
- HN Synopsis column: 10 words or fewer describing the story
- AI Labs table: Lab column shows the source (OpenAI, Anthropic, Google AI, xAI, Mistral), Category shows the post type (e.g. "Model Release", "Research", "Engineering", "Developer Tools"), Date is short format (e.g. "Mar 24")
- If a section has no content, include the section header with an italicized note

Report your progress as you complete each step."""


def build_fallback_prompt(
    place: str,
    characters_text: str,
    readme_file: Path,
    adjectives_file: Path,
    animals_file: Path,
    places_file: Path,
    hats_file: Path,
    scene_file: Path,
    hat_pair: tuple[str, str],
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
Read all three data files and make exactly ONE edit to EACH file. Each edit is either an add, a remove, or a replace — at most +1 and/or -1 lines per file.

**{adjectives_file}** — Adjectives for character generation
- These adjectives drive a comic image, so they MUST be visually depictable. An illustrator must be able to draw a character that looks "<adjective>" at a glance — through posture, expression, body language, or accessory.
- Test before adding: "If I told an illustrator to draw a [word] character with no other context, would they instantly know what to draw?" If no, REJECT.
- GOOD (instantly visualizable): 'caffeinated', 'unhinged', 'pompous', 'sleep-deprived', 'sweaty', 'shivering', 'smug', 'panicked', 'overconfident', 'feral', 'overdressed', 'soggy'
- BAD (abstract concepts that don't translate to a single image): 'fiscally-irresponsible', 'aggressively-mediocre', 'tab-hoarding', 'enshittified', 'npc-coded', 'recalcitrant', 'lugubrious'
- BAD (descriptive but not character-defining): 'blue', 'tall', 'old' — these describe appearance, not personality
- Add a fresh visually-depictable one, OR remove an abstract/non-visual one, OR replace a weak one
- Audit hint: when reading the existing list, flag any that fail the illustrator test as candidates for removal/replacement.

**{places_file}** — Settings where the comic takes place
- Should be vivid, instantly recognizable locations with comedic potential
- Good: 'a haunted castle', 'underwater', 'in a broken-down elevator'. Bad: 'a room', 'outside'
- Add a fun new setting, OR remove a dull one, OR replace a weak one

**{hats_file}** — Absurd hats worn by the blob characters in the comic
- Each line is one hat — described as a noun phrase the image model can render directly
- Must be visually distinctive and instantly recognizable, with comedic potential
- Good: 'jester hat with three drooping bells', 'foam cowboy hat', 'tinfoil pyramid hat', 'beekeeper veil-and-hat combo'
- Bad: 'a hat', 'something nice' (too vague), 'metaphorical hat of regret' (not literal/visual)
- Add a fun new absurd hat, OR remove a dull one, OR replace a weak one

Use the Edit tool for each file. Report what you changed and why.

## Step 3: Write the Comic Scene
Characters: pick two of these — {characters_text}
Use ONLY the adjectives — the characters are people. Drop any species words.

CRITICAL: an illustrator must be able to draw "[adjective] character" at a glance. If an adjective is abstract and you can't picture how it would look on a character, PICK DIFFERENT ADJECTIVES from {adjectives_file}. Strong visual adjectives lead to good comics.

Setting: {place}

The characters are {place}, confronting the absence of AI news. Today there is NONE.

Write a 6-panel scene reacting to the void. Play up the existential comedy:
- Are they still relevant if there's nothing to discuss?
- Do they exist if there's no AI news?
- The setting adds atmosphere

Format the scene EXACTLY like this:

```
*[narrative intro: "A [adj] person and a [adj] person face the void {place}."]*

Panel 1:
[setup]
ADJECTIVE PERSON: "dialog noticing the absence of news"

Panel 2:
[build]
OTHER ADJECTIVE PERSON: "dialog escalating the crisis"

Panel 3:
[pivot]
ADJECTIVE PERSON: "the existential reveal"

Panel 4:
[silent reaction]
[Visual: describe a wordless reaction shot.]

Panel 5:
[punch]
ADJECTIVE PERSON: "punchline setup"
OTHER ADJECTIVE PERSON: "the punchline"

Panel 6:
[button]
[Visual: closing visual beat. Optional final dialog line.]
ADJECTIVE PERSON: "final button line, optional"
```

Hard requirements:
- EXACTLY 6 panels with the beat labels: setup, build, pivot, silent reaction, punch, button
- Panel 4 MUST be a wordless beat (only `[Visual: ...]`, no dialog)
- Speech bubbles ≤12 words each
- Speaker labels UPPERCASE, "ADJECTIVE PERSON" format (no animal/species)
- 0-2 dialog lines per panel
- Use both characters across the scene; not every panel needs both
- Clean and work-appropriate

## Step 3.5: Persist the Scene to Disk
Use the Write tool to save the EXACT scene text from Step 3 to: {scene_file}

This file is the source of truth and the image-gen call uses this same text.

## Step 4: Generate the Comic Image
Compose a SINGLE image-generation prompt with all of:

1. **Style direction (use this paragraph verbatim — the hats are pre-assigned by the system, the FIRST adjective in your scene's narrative intro corresponds to the first hat below, the SECOND adjective to the second hat):**
{build_comic_style_direction(hat_pair[0], hat_pair[1])}

2. **Layout direction (use this paragraph verbatim):**
{COMIC_LAYOUT_DIRECTION}

3. **Scene context:** the narrative intro line from your scene (without asterisks).

4. **Render this 6-panel comic. Use the dialog EXACTLY as written - do NOT paraphrase. Some panels are SILENT (no speech bubbles) - that is intentional pacing. Visual descriptions in [brackets] tell you what to draw.**
List each panel block (Panel 1 through Panel 6) with the exact dialog and visual notes from your scene file.

5. **Character anchors (style-neutral — visual aesthetic comes from §1, do NOT add style words here):** "Both characters are human. Their appearance reflects their adjective traits and stays consistent across all 6 panels. The setting backdrop ({place}) is visible in every panel. Vary panel composition: wide establishing shots, medium two-shots, close-ups for emotional beats."

Then call `mcp__comic__generate_image` with:
- `prompt`: the full image-gen prompt you composed above
- `filename`: `"comic_{timestamp}"`

The tool saves to `daily_agent/generated_images/comic_{timestamp}.png` at 1024x1792. If it fails twice, proceed to Step 5 anyway.

## Step 5: Update {readme_file}
Write a new file at: {readme_file}
Use this EXACT structure:

```markdown
# 📰 The AI Newspaper — Day [NEW DAY COUNT] ({timestamp})

*AI curated AI news for humans*

> *No AI news today — nothing from Hacker News, nothing from the labs. The characters are... processing this.*

---

## The Comic Strip

*[Narrative sentence describing the scene]*

<img src="daily_agent/generated_images/comic_{timestamp}.png" width="600" alt="Today's 6-panel comic strip">

---

*The AI Newspaper is autonomously generated daily by a Claude agent. It scrapes Hacker News for AI stories, monitors OpenAI/Anthropic/Google AI blogs for new posts, and has two randomly generated characters debate the most interesting story. Today there was nothing. The characters handled it... uniquely.*

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

    seen_posts = load_seen_posts()
    if lab_posts:
        lab_posts = filter_seen_dateless_posts(lab_posts, seen_posts)

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
    place = get_random_place()
    characters_text = ", ".join(characters)
    print(f"Character pool: {characters_text}")
    print(f"Setting: {place}\n")

    readme_file = PROJECT_ROOT / "README.md"
    adjectives_file = DATA_DIR / "adjectives.txt"
    animals_file = DATA_DIR / "animals.txt"
    places_file = DATA_DIR / "places.txt"
    hats_file = DATA_DIR / "hats.txt"

    all_hats = load_list_from_file("hats.txt")
    if len(all_hats) < 2:
        raise RuntimeError(f"hats.txt must contain at least 2 entries, found {len(all_hats)}")
    picked_hats = random.sample(all_hats, 2)
    hat_pair = (picked_hats[0], picked_hats[1])
    print(f"Random hats: '{hat_pair[0]}' / '{hat_pair[1]}'")

    timestamp = datetime.now().strftime("%Y-%m-%d")
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    scene_file = SCENES_DIR / f"{timestamp}.txt"

    comic_server = create_sdk_mcp_server(
        name="comic",
        tools=[generate_image],
    )

    options = ClaudeAgentOptions(
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "WebFetch",
            "mcp__comic__generate_image",
        ],
        mcp_servers={"comic": comic_server},
        permission_mode="acceptEdits",
        cwd=str(PROJECT_ROOT),
        model="claude-sonnet-4-6",
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
                model="claude-haiku-4-5",
                tools=["WebFetch"],
            ),
        },
    )

    if has_any_news:
        prompt = build_digest_prompt(
            stories_text=stories_text,
            story_count=len(stories),
            lab_posts_text=lab_posts_text,
            lab_post_count=len(lab_posts),
            place=place,
            characters_text=characters_text,
            readme_file=readme_file,
            adjectives_file=adjectives_file,
            animals_file=animals_file,
            places_file=places_file,
            hats_file=hats_file,
            scene_file=scene_file,
            hat_pair=hat_pair,
            timestamp=timestamp,
        )
    else:
        print("No news from any source — running in fallback mode")
        prompt = build_fallback_prompt(
            place=place,
            characters_text=characters_text,
            readme_file=readme_file,
            adjectives_file=adjectives_file,
            animals_file=animals_file,
            places_file=places_file,
            hats_file=hats_file,
            scene_file=scene_file,
            hat_pair=hat_pair,
            timestamp=timestamp,
        )

    max_retries = 3
    initial_backoff_secs = 30

    for attempt in range(1, max_retries + 1):
        received_content = False

        async with ClaudeSDKClient(options=options) as client:
            print("Launching autonomous workflow...\n")
            print("=" * 60)

            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text)
                            received_content = True

        readme_updated = (
            received_content
            and readme_file.exists()
            and timestamp in readme_file.read_text()
        )

        if readme_updated:
            break

        if attempt < max_retries:
            backoff = initial_backoff_secs * (2 ** (attempt - 1))
            print(f"\n{'=' * 60}")
            print(
                f"Attempt {attempt}/{max_retries} failed — "
                f"README not updated. Retrying in {backoff}s..."
            )
            print("=" * 60)
            await asyncio.sleep(backoff)
        else:
            raise RuntimeError(
                f"Agent failed after {max_retries} attempts — README not updated"
            )

    print("\n" + "=" * 60)
    print("Agent completed successfully!")
    print("=" * 60)

    if lab_posts:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for post in lab_posts:
            if post.get("date_obj") is None:
                seen_posts[post["url"]] = today_str
        save_seen_posts(seen_posts)


if __name__ == "__main__":
    try:
        asyncio.run(run_autonomous_agent())
    except KeyboardInterrupt:
        print("\n\nAgent interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nAgent failed with error: {e}")
        sys.exit(1)
