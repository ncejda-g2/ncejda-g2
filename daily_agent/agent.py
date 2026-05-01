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
from typing import Any, Literal

import aiohttp
import feedparser
from bs4 import BeautifulSoup
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)
from custom_tools import image_gen_usage_log
from dotenv import load_dotenv

from scene_pipeline import (
    StoryContext,
    WinningScene,
    pick_winning_scene,
    render_scene_to_image,
)

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(__file__).parent / "data"
SCENES_DIR = DATA_DIR / "comic_text"
TOKENS_DIR = DATA_DIR / "tokens"
IMAGES_DIR = Path(__file__).parent / "generated_images"

# Note: the 6-panel style/layout constants that used to live here moved to
# comic_templates/classic_6_panel.py — that template is now one of 14 the
# scene_pipeline can pick from. Image generation is handled in scene_pipeline,
# not by an MCP tool the agent calls.


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


_HAT_CURATION_RULES = """**{hats_file}** — Absurd hats worn by the blob characters in the comic
- Each line is one hat — described as a noun phrase the image model can render directly
- Must be visually distinctive and instantly recognizable, with comedic potential
- Good: 'jester hat with three drooping bells', 'foam cowboy hat', 'tinfoil pyramid hat', 'beekeeper veil-and-hat combo'
- Bad: 'a hat', 'something nice' (too vague), 'metaphorical hat of regret' (not literal/visual)
- ALLOWED categories (totally fine — pick from these or invent within them):
  - Generic everyday/sport: baseball cap, foam cowboy hat, bucket hat, trucker cap, beanie, visor, bike helmet
  - Holiday/secular festive: santa hat, party cone hat, birthday crown, new-year's-eve top hat
  - Occupational: chef's toque, welder's mask, construction hard hat, nurse's cap, firefighter helmet, hairnet
  - Fantasy/fictional: wizard hat, jester hat, knight's plume helmet, viking helmet with horns, dragon-scale helm
  - Absurd novelty props: propeller beanie, tinfoil pyramid hat, rubber-duck helmet, hat made of taped-together pencils, helmet with a goldfish bowl on top
- HARD RULE — never add culturally, religiously, or ethnically loaded headwear. Examples of what to NEVER add: turbans, fezzes, sombreros, conical Asian straw hats / "rice hats", keffiyehs, kippot/yarmulkes, tagelmusts, papal/bishop's mitres, nun's habits, Native American war bonnets / feathered headdresses, pith helmets, dreadlock-tams, hijabs/niqabs, or any hat that signals a specific real-world ethnic, national, or religious group. If you see one in the existing list, REMOVE it as your edit.
- Add a fun new absurd hat from the allowed categories, OR remove a dull or culturally-loaded one, OR replace a weak one"""


def build_picker_prompt(
    stories_text: str,
    story_count: int,
    lab_posts_text: str,
    lab_post_count: int,
    readme_file: Path,
    adjectives_file: Path,
    places_file: Path,
    hats_file: Path,
) -> str:
    """First agent call: read README day count, classify HN, filter labs,
    curate data files, pick today's top story, output structured JSON.

    The agent does NOT write the comic scene or generate the image — those
    happen in scene_pipeline (Python). A second agent call writes the README.
    """

    hn_section = ""
    if stories_text:
        hn_section = f"""
## Step 2: Filter HN Stories for AI Relevance
When you read the README in Step 1, also extract ALL story titles and URLs from the existing news tables (both Hacker News AND AI Labs). **Do NOT include any story or post that appeared in yesterday's tables.**

Use the "classifier" sub-agent to classify all {story_count} stories for AI relevance in one batch. Then apply the tier system and dedup yourself.

Tier priority (use this when picking up to 10 stories for the table):
- Tier 1: New model releases or major updates from OpenAI, Anthropic, Google, xAI
- Tier 2: Model developments from smaller / open-source / Chinese AI labs, or alternate architectures
- Tier 3: AI tooling updates — dev tools, agent frameworks, Claude Code / opencode updates
- Tier 4: AI infrastructure or hardware (GPUs, inference, deployment)
- Tier 5: AI research papers with practical implications

Special rule: the FIRST story in the list (highest score) must always be included if it's AI-related in any way, regardless of tier.
"""

    lab_section = ""
    if lab_posts_text:
        lab_section = f"""
## Step 3: Filter AI Lab Posts
Recent blog posts from OpenAI, Google AI, Anthropic, xAI, and Mistral ({lab_post_count} posts found):
{lab_posts_text}

ONLY include posts about: model releases/updates/benchmarks, research papers, engineering deep-dives, developer tools, platform capabilities.

EXCLUDE posts about: hiring, leadership/C-suite changes, lawsuits/regulation, funding/partnerships, generic PR / awards / event recaps.

If a post title is ambiguous, use WebFetch to skim it before deciding. Dedup against yesterday's AI Labs table.
"""
    elif not stories_text:
        lab_section = """
## Step 3: AI Lab Posts
No recent posts found from AI labs. Output an empty `lab_posts` array.
"""

    return f"""You are the editorial-prep agent for "The AI Newspaper" — a daily briefing with Hacker News AI stories, official AI lab blog posts, and a comic strip. This is the FIRST of two agent calls. In this call you read the day count, filter stories, curate data files, and pick today's top story for the comic. The comic itself and the README are produced separately.

{"Today's HN stories from the last 24 hours (sorted by score, highest first):" if stories_text else "No HN stories were available today."}
{stories_text}

## Step 1: Determine Day Count
Read the file at: {readme_file}
Extract the current day count (line containing "Day" + number). Calculate the new day count by adding 1. If no day count found, use 1.
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

{_HAT_CURATION_RULES.format(hats_file=hats_file)}

Use the Edit tool for each file. Report what you changed and why.

## Step 5: Pick & Research the Top Story
Pick THE single most interesting/impactful story from EITHER the AI-relevant HN stories OR the lab posts (whichever is most newsworthy today). Use WebFetch to read the article and extract a CONCRETE summary suitable as input to a comedy writer:
- 2-3 specific facts (real numbers, named tools/companies, exact quotes)
- Why it matters in 1 sentence

Generic summaries produce generic comics. Be specific.

## Step 6: Output Structured JSON
After completing Steps 1-5, output a SINGLE fenced JSON block at the end of your response. Do NOT write the comic scene. Do NOT generate any image. Do NOT write the README. Those happen separately. After the JSON block, stop.

```json
{{
  "day_count": <new day count, integer>,
  "hn_stories": [
    {{"title": "...", "url": "...", "points": <int>, "comments_url": "https://news.ycombinator.com/item?id=...", "type": "Model Release | Palace Intrigue | Open Source Tool | Research Paper | Dev Tooling | Infrastructure | AI Hardware", "synopsis": "≤10 word description"}}
  ],
  "lab_posts": [
    {{"title": "...", "url": "...", "source": "OpenAI | Anthropic | Google AI | xAI | Mistral", "category": "Engineering | Research | News | Developer Tools | Model Release", "date": "Mar 24"}}
  ],
  "top_story": {{
    "title": "...",
    "url": "...",
    "summary": "2-3 sentence concrete summary with specific facts (real numbers, named tools, exact quotes) — fed to a comedy writer.",
    "source": "hn"
  }}
}}
```

Notes:
- `hn_stories`: up to 10 entries, sorted by HN points descending. Empty array `[]` if no AI-relevant stories.
- `lab_posts`: all relevant lab posts after filtering. Empty array `[]` if none.
- `top_story`: the single most newsworthy story from EITHER list — null if there's truly nothing to write a comic about.
- `top_story.source`: `"hn"` or `"lab"` depending on where it came from.
- All HN stories shown to you have an HN discussion URL of the form `https://news.ycombinator.com/item?id=<ID>` — use that for `comments_url`.

Report your progress on each step in plain text BEFORE the final JSON block. The JSON block must be the last thing in your response."""


def build_readme_prompt(
    readme_file: Path,
    day_count: int,
    hn_stories: list[dict],
    lab_posts: list[dict],
    image_filename: str,
    comic_narrative: str,
    timestamp: str,
    no_news: bool,
) -> str:
    """Second agent call: write the README using pre-computed inputs.

    Everything is decided before this call: stories are filtered, the comic
    image is generated and saved, the narrative caption is written. The agent
    only formats the README.
    """
    hn_block = json.dumps(hn_stories, indent=2)
    lab_block = json.dumps(lab_posts, indent=2)

    if no_news:
        no_news_note = (
            "> *No AI news today — nothing from Hacker News, nothing from the labs. "
            "The characters are... processing this.*\n\n---\n\n"
        )
        sections_template = no_news_note
    else:
        sections_template = """## 🗞️ Hacker News

| # | Story | Type | Synopsis | Points | Comments |
|---|-------|------|----------|--------|----------|
[one row per `hn_stories` entry; if empty, replace this table with the line: *No AI news on HN today.*]

---

## 🔬 From the AI Labs

| # | Post | Lab | Category | Date |
|---|------|-----|----------|------|
[one row per `lab_posts` entry; if empty, replace this table with the line: *No new lab posts this week.*]

---

"""

    return f"""You are writing the new README.md for "The AI Newspaper" — Day {day_count}. The orchestrator has pre-computed everything: stories are filtered, the comic image is generated, the narrative caption is decided. Your only job is to format the README cleanly.

# Inputs

## Day count
{day_count}

## Timestamp (for the header)
{timestamp}

## HN stories (already filtered for AI relevance, JSON)
```json
{hn_block}
```

## AI Lab posts (already filtered, JSON)
```json
{lab_block}
```

## Comic
- Image: `daily_agent/generated_images/{image_filename}` (already generated and saved)
- Narrative caption (use VERBATIM in the comic section, in italics): {comic_narrative!r}

# Task
Use the Write tool to save the new README to {readme_file} with this EXACT structure:

```markdown
# 📰 The AI Newspaper — Day {day_count} ({timestamp})

*AI curated AI news for humans*

{sections_template}## The Comic Strip

*{{COMIC_NARRATIVE}}*

<img src="daily_agent/generated_images/{image_filename}" width="600" alt="Today's comic strip">

---

*The AI Newspaper is autonomously generated daily by a Claude agent. It scrapes Hacker News for AI stories, monitors blogs from OpenAI, Anthropic, Google AI, xAI, and Mistral, and produces a daily comic reacting to the most interesting story.*

*Day {day_count} | Last updated: {timestamp}*
```

Replace `{{COMIC_NARRATIVE}}` with the narrative caption from the inputs (without the surrounding quotes). Replace the bracketed table-row instructions with actual filled rows from the JSON inputs.

Formatting rules:
- Story titles in both tables: markdown links `[Title](url)` — use the JSON-provided URLs verbatim
- HN Comments column: link to HN discussion `[<points>](<comments_url>)` — wait, no — Comments column shows the discussion link as `[<num_comments_or_points>](comments_url)` where the visible number is the comments count. (For these inputs we just have points, so use the points number as the link text.)
- Use the raw `<img>` HTML tag shown above (not markdown image syntax) so GitHub width-constrains the image to 600px
- If `hn_stories` is empty, put `*No AI news on HN today.*` in place of the HN table
- If `lab_posts` is empty, put `*No new lab posts this week.*` in place of the lab table

Use the Write tool. No commentary outside the file write."""




_CLASSIFIER_AGENT = AgentDefinition(
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
)


def _extract_last_json_block(text: str) -> dict[str, Any] | None:
    """Pull the last fenced JSON block out of an agent response."""
    fence_re = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)
    matches = fence_re.findall(text)
    if matches:
        try:
            return json.loads(matches[-1])
        except json.JSONDecodeError:
            return None
    # Fallback: try to find a top-level { ... } at the end of the text
    s = text.rstrip()
    if s.endswith("}"):
        depth = 0
        for i in range(len(s) - 1, -1, -1):
            if s[i] == "}":
                depth += 1
            elif s[i] == "{":
                depth -= 1
                if depth == 0:
                    candidate = s[i:]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        return None
    return None


async def _run_agent_call(
    prompt: str, options: ClaudeAgentOptions
) -> tuple[str, ResultMessage | None]:
    """Run one ClaudeSDKClient session; return (joined text, result message).

    The ResultMessage carries session-level cost/usage/turn/duration totals
    (already including subagent calls). Callers accumulate it into the daily
    token-usage report.
    """
    chunks: list[str] = []
    result: ResultMessage | None = None
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                        chunks.append(block.text)
            elif isinstance(message, ResultMessage):
                result = message
    return "".join(chunks), result


def _build_no_news_story_context(
    *, character_pool: list[str], place: str
) -> StoryContext:
    """Synthesize a 'no AI news today' story so the scene_pipeline has something
    to react to in fallback mode. Generators will produce existential-comedy
    takes on the absence of news."""
    return StoryContext(
        title="No AI news today",
        url="",
        summary=(
            "There were zero AI-relevant stories on Hacker News today and zero new "
            "blog posts from OpenAI, Anthropic, Google AI, xAI, or Mistral. The "
            "characters that exist to discuss AI news now have nothing to discuss. "
            "Lean into existential comedy — are they still relevant if there's "
            "nothing to react to? Do they still exist?"
        ),
        character_pool=character_pool,
        place=place,
    )


async def run_autonomous_agent() -> None:
    """Daily AI Newspaper pipeline.

    Flow:
      1. Fetch HN + AI lab posts.
      2. Generate random character pool, place, and hat pair (orchestrator-side).
      3. Coin-flip the comic mode: 50% meme, 50% classic 6-panel.
      4. Picker agent call: read README day count, classify HN, filter labs,
         curate data files, pick top story, output structured JSON.
      5. Run scene_pipeline.pick_winning_scene → 5 generators + critic.
      6. Render the winning scene to a PNG via gpt-image-2.
      7. Persist the scene metadata as JSON under data/comic_text/.
      8. Readme agent call: write README using the structured inputs.
    """

    print("Starting The AI Newspaper Agent")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working directory: {PROJECT_ROOT}\n")

    # 1. Fetch news
    async with aiohttp.ClientSession() as session:
        print("Fetching HN stories and AI lab posts in parallel...")
        hn_task = fetch_hn_stories(session)
        lab_task = fetch_ai_lab_posts(session)
        stories, lab_posts = await asyncio.gather(hn_task, lab_task)

    seen_posts = load_seen_posts()
    if lab_posts:
        lab_posts = filter_seen_dateless_posts(lab_posts, seen_posts)

    stories_text = format_stories_for_prompt(stories) if stories else ""
    lab_posts_text = format_lab_posts_for_prompt(lab_posts) if lab_posts else ""
    print(
        f"  HN stories: {len(stories)}   "
        f"AI lab posts: {len(lab_posts)}"
    )

    # 2. Random orchestrator-side context
    character_pool = generate_random_characters(4)
    place = get_random_place()
    print(f"Character pool: {character_pool}")
    print(f"Setting: {place}")

    all_hats = load_list_from_file("hats.txt")
    if len(all_hats) < 2:
        raise RuntimeError(
            f"hats.txt must contain at least 2 entries, found {len(all_hats)}"
        )
    picked_hats = random.sample(all_hats, 2)
    hat_pair: tuple[str, str] = (picked_hats[0], picked_hats[1])
    print(f"Random hats: {hat_pair[0]!r} / {hat_pair[1]!r}")

    # 3. Coin flip — 50% meme, 50% classic 6-panel
    template_filter: Literal["meme", "classic"] = (
        "meme" if random.random() < 0.5 else "classic"
    )
    print(f"Template mode (coin flip): {template_filter}")

    timestamp = datetime.now().strftime("%Y-%m-%d")
    readme_file = PROJECT_ROOT / "README.md"
    adjectives_file = DATA_DIR / "adjectives.txt"
    places_file = DATA_DIR / "places.txt"
    hats_file = DATA_DIR / "hats.txt"
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    scene_metadata_file = SCENES_DIR / f"{timestamp}.json"
    image_filename = f"comic_{timestamp}.png"

    # SDK options for both agent calls (Read/Write/Edit/WebFetch only — no MCP
    # image tool; image generation is handled in scene_pipeline)
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "WebFetch"],
        permission_mode="acceptEdits",
        cwd=str(PROJECT_ROOT),
        model="claude-sonnet-4-6",
        agents={"classifier": _CLASSIFIER_AGENT},
    )

    # Accumulators for the daily token-usage artifact (rolled up across both
    # agent calls + the gpt-image-2 calls scene_pipeline makes).
    total_cost_usd = 0.0
    total_usage: dict[str, int] = {}
    total_turns = 0
    total_duration_ms = 0

    def _accumulate(rm: ResultMessage | None) -> None:
        nonlocal total_cost_usd, total_turns, total_duration_ms
        if rm is None:
            return
        if rm.total_cost_usd:
            total_cost_usd += rm.total_cost_usd
        if rm.usage:
            for k, v in rm.usage.items():
                if isinstance(v, (int, float)):
                    total_usage[k] = total_usage.get(k, 0) + int(v)
        total_turns += rm.num_turns
        total_duration_ms += rm.duration_ms

    try:
        # 4. Picker agent call
        print("\n" + "=" * 60)
        print("PHASE 1: picker agent (filter + curate + pick top story)")
        print("=" * 60)
        picker_prompt = build_picker_prompt(
            stories_text=stories_text,
            story_count=len(stories),
            lab_posts_text=lab_posts_text,
            lab_post_count=len(lab_posts),
            readme_file=readme_file,
            adjectives_file=adjectives_file,
            places_file=places_file,
            hats_file=hats_file,
        )
        picker_text, picker_result = await _run_agent_call(picker_prompt, options)
        _accumulate(picker_result)
        picker_data = _extract_last_json_block(picker_text)
        if picker_data is None:
            raise RuntimeError(
                "Picker agent did not produce a parseable JSON block. Check the "
                "agent transcript above."
            )
        day_count = int(picker_data.get("day_count") or 1)
        hn_table = picker_data.get("hn_stories") or []
        lab_table = picker_data.get("lab_posts") or []
        top_story = picker_data.get("top_story")  # may be None
        print(
            f"\nPicker output: day {day_count}, "
            f"{len(hn_table)} HN rows, {len(lab_table)} lab rows, "
            f"top_story={(top_story or {}).get('title', '<none>')!r}"
        )

        # 5. Scene pipeline (5 generators + critic) — uses real story or
        # synthesizes a 'no news' context as fallback
        print("\n" + "=" * 60)
        print("PHASE 2: scene pipeline (5 generators + critic)")
        print("=" * 60)
        if top_story:
            story_ctx = StoryContext(
                title=str(top_story.get("title", "")),
                url=str(top_story.get("url", "")),
                summary=str(top_story.get("summary", "")),
                character_pool=character_pool,
                place=place,
            )
            no_news_mode = False
        else:
            print("No top story from picker — running scene_pipeline in no-news mode")
            story_ctx = _build_no_news_story_context(
                character_pool=character_pool, place=place
            )
            no_news_mode = True

        winning_scene = await pick_winning_scene(
            story_ctx, template_filter=template_filter
        )

        # 6. Render image
        print("\n" + "=" * 60)
        print("PHASE 3: render winning scene to image")
        print("=" * 60)
        image_path = await render_scene_to_image(
            winning_scene,
            out_dir=IMAGES_DIR,
            filename_stem=image_filename.removesuffix(".png"),
            place=place,
            hat_pair=hat_pair,
        )
        print(f"Image saved: {image_path}")

        # 7. Persist scene metadata
        scene_metadata = {
            "timestamp": timestamp,
            "template_id": winning_scene.template_id,
            "template_filter": template_filter,
            "voice_label": winning_scene.voice_label,
            "fields": winning_scene.fields,
            "narrative_summary": winning_scene.narrative_summary,
            "rationale": winning_scene.rationale,
            "image_filename": image_filename,
            "story_title": story_ctx.title,
            "story_url": story_ctx.url,
            "place": place,
            "hat_pair": list(hat_pair),
            "no_news_mode": no_news_mode,
        }
        scene_metadata_file.write_text(json.dumps(scene_metadata, indent=2) + "\n")
        print(f"Scene metadata: {scene_metadata_file}")

        # Build the comic narrative caption used in the README
        if winning_scene.template_id == "classic_6_panel":
            # Classic uses the generator-written narrative_intro (already wrapped
            # in asterisks). Strip them — README adds its own italics.
            comic_narrative = winning_scene.fields.get(
                "narrative_intro", winning_scene.narrative_summary
            ).strip("* ")
        else:
            comic_narrative = winning_scene.narrative_summary

        # 8. Readme agent call
        print("\n" + "=" * 60)
        print("PHASE 4: README agent (format the daily page)")
        print("=" * 60)
        readme_prompt = build_readme_prompt(
            readme_file=readme_file,
            day_count=day_count,
            hn_stories=hn_table,
            lab_posts=lab_table,
            image_filename=image_filename,
            comic_narrative=comic_narrative,
            timestamp=timestamp,
            no_news=no_news_mode,
        )
        _, readme_result = await _run_agent_call(readme_prompt, options)
        _accumulate(readme_result)

        # Sanity check
        if not (readme_file.exists() and timestamp in readme_file.read_text()):
            raise RuntimeError(
                "README agent finished but the README does not contain today's timestamp"
            )

        print("\n" + "=" * 60)
        print("Agent completed successfully!")
        print("=" * 60)

        # Existing seen-posts bookkeeping
        if lab_posts:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for post in lab_posts:
                if post.get("date_obj") is None:
                    seen_posts[post["url"]] = today_str
            save_seen_posts(seen_posts)
    finally:
        TOKENS_DIR.mkdir(parents=True, exist_ok=True)
        tokens_file = TOKENS_DIR / f"{timestamp}.json"
        anthropic_total_tokens = (
            total_usage.get("input_tokens", 0)
            + total_usage.get("output_tokens", 0)
            + total_usage.get("cache_creation_input_tokens", 0)
            + total_usage.get("cache_read_input_tokens", 0)
        )
        image_gen_total_tokens = sum(
            int(entry.get("usage", {}).get("total_tokens", 0))
            for entry in image_gen_usage_log
        )
        tokens_data = {
            "date": timestamp,
            "model": "claude-sonnet-4-6",
            "attempts": 1,
            "total_cost_usd": round(total_cost_usd, 6),
            "total_duration_ms": total_duration_ms,
            "total_turns": total_turns,
            "anthropic_usage": total_usage,
            "anthropic_total_tokens": anthropic_total_tokens,
            "image_gen_usage": image_gen_usage_log,
            "image_gen_total_tokens": image_gen_total_tokens,
            "grand_total_tokens": anthropic_total_tokens + image_gen_total_tokens,
        }
        tokens_file.write_text(json.dumps(tokens_data, indent=2) + "\n")
        print(f"Token usage report written to {tokens_file}")


if __name__ == "__main__":
    try:
        asyncio.run(run_autonomous_agent())
    except KeyboardInterrupt:
        print("\n\nAgent interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nAgent failed with error: {e}")
        sys.exit(1)
