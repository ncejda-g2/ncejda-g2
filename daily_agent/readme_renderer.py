"""Deterministic README rendering for The AI Newspaper."""

from __future__ import annotations

from typing import Any


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _link(label: Any, url: Any) -> str:
    safe_label = _cell(label).replace("]", "\\]")
    return f"[{safe_label}]({str(url).strip()})"


def render_readme(
    *,
    day_count: int,
    timestamp: str,
    hn_stories: list[dict[str, Any]],
    lab_posts: list[dict[str, Any]],
    trending_markdown: str,
    image_filename: str,
    no_news: bool,
    is_meme: bool,
    story_title: str,
    story_url: str,
) -> str:
    lines = [
        f"# 📰 The AI Newspaper — Day {day_count} ({timestamp})",
        "",
        "*AI curated AI news for humans*",
        "",
    ]
    if no_news:
        lines.extend(
            [
                "> *No AI news today — nothing from Hacker News, nothing from the labs. The characters are... processing this.*",
                "",
                "---",
                "",
            ]
        )

    lines.extend(["## 🗞️ Hacker News", ""])
    if hn_stories:
        lines.extend(
            [
                "| # | Story | Type | Synopsis | Points | Comments |",
                "|---|-------|------|----------|--------|----------|",
            ]
        )
        for index, story in enumerate(hn_stories, 1):
            comments = story.get("comments", story.get("points", 0))
            lines.append(
                f"| {index} | {_link(story['title'], story['url'])} | "
                f"{_cell(story['type'])} | {_cell(story['synopsis'])} | "
                f"{int(story['points'])} | {_link(comments, story['comments_url'])} |"
            )
    else:
        lines.append("*No AI news on HN today.*")

    lines.extend(["", "---", "", "## 🔬 From the AI Labs", ""])
    if lab_posts:
        lines.extend(
            [
                "| # | Post | Lab | Category | Date |",
                "|---|------|-----|----------|------|",
            ]
        )
        for index, post in enumerate(lab_posts, 1):
            lines.append(
                f"| {index} | {_link(post['title'], post['url'])} | "
                f"{_cell(post['source'])} | {_cell(post['category'])} | {_cell(post['date'])} |"
            )
    else:
        lines.append("*No new lab posts this week.*")

    lines.extend(["", "---", ""])
    if trending_markdown:
        lines.extend(trending_markdown.rstrip().splitlines())
        lines.append("")

    image_width = 400 if is_meme else 600
    lines.extend(
        [
            "## The Comic Strip",
            "",
            f'<img src="daily_agent/generated_images/{image_filename}" width="{image_width}" alt="Today\'s comic strip">',
        ]
    )
    if story_title and story_url:
        lines.extend(["", f"_Based on: {_link(story_title, story_url)}_"])
    lines.extend(
        [
            "",
            "---",
            "",
            "*The AI Newspaper is autonomously generated daily by a Claude agent. It scrapes Hacker News for AI stories, monitors blogs from OpenAI, Anthropic, Google AI, xAI, and Mistral, tracks AI repositories across GitHub Trending, and produces a daily comic reacting to the most interesting story.*",
            "",
            f"*Day {day_count} | Last updated: {timestamp}*",
            "",
        ]
    )
    return "\n".join(lines)
