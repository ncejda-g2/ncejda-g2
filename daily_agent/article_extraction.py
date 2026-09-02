"""Fetch and extract the main text from an already-selected article URL."""

from __future__ import annotations

import re
import json
from dataclasses import dataclass

import aiohttp
import trafilatura
from bs4 import BeautifulSoup


MAX_DOWNLOAD_BYTES = 3_000_000
MAX_ARTICLE_CHARS = 60_000
MIN_ARTICLE_CHARS = 700
MIN_ARTICLE_WORDS = 110

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AINewspaper/1.0; +https://github.com/ncejda/ncejda-g2)",
    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
}


@dataclass(frozen=True)
class ArticleExtraction:
    url: str
    text: str
    method: str
    quality_ok: bool
    quality_reason: str
    http_status: int | None = None


def _normalize(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n\n".join(line for line in lines if line)[:MAX_ARTICLE_CHARS]


def assess_article_text(text: str) -> tuple[bool, str]:
    words = re.findall(r"\b[\w'-]+\b", text)
    if len(text) < MIN_ARTICLE_CHARS:
        return False, f"only {len(text)} characters"
    if len(words) < MIN_ARTICLE_WORDS:
        return False, f"only {len(words)} words"
    alpha_ratio = sum(character.isalpha() for character in text) / max(len(text), 1)
    if alpha_ratio < 0.45:
        return False, f"low alphabetic-content ratio ({alpha_ratio:.2f})"
    sentence_marks = sum(text.count(mark) for mark in (".", "?", "!"))
    if sentence_marks < 4:
        return False, "too few complete sentences"
    return True, f"{len(words)} words of main text"


def _json_ld_article_bodies(soup: BeautifulSoup) -> list[str]:
    bodies: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            body = value.get("articleBody")
            if isinstance(body, str):
                bodies.append(BeautifulSoup(body, "html.parser").get_text("\n", strip=True))
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            visit(json.loads(script.string or script.get_text() or ""))
        except (json.JSONDecodeError, TypeError):
            continue
    return bodies


def _largest_visible_content(soup: BeautifulSoup) -> str:
    selectors = (
        "[itemprop='articleBody']",
        ".article-body",
        ".article-content",
        ".entry-content",
        ".post-content",
        ".story-content",
        ".rich-text",
        ".markdown-body",
        "article",
        "main",
    )
    candidates = []
    for selector in selectors:
        for node in soup.select(selector):
            candidates.append(node.get_text("\n", strip=True))
    return max(candidates, key=len, default="")


def extract_article_text(html: str, url: str) -> ArticleExtraction:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header", "aside"]):
        if node.name != "script" or node.get("type") != "application/ld+json":
            node.decompose()

    candidates: list[tuple[str, str]] = []
    for body in _json_ld_article_bodies(soup):
        candidates.append(("json-ld-articleBody", body))

    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        include_links=False,
        output_format="txt",
        favor_precision=True,
    )
    if extracted:
        candidates.append(("trafilatura", extracted))
    largest = _largest_visible_content(soup)
    if largest:
        candidates.append(("beautifulsoup-content-block", largest))
    if not candidates:
        root = soup.body or soup
        candidates.append(("beautifulsoup-body", root.get_text("\n", strip=True)))

    best_failure = ("none", "", False, "no content extracted")
    for method, raw_text in candidates:
        text = _normalize(raw_text)
        quality_ok, reason = assess_article_text(text)
        if quality_ok:
            return ArticleExtraction(
                url=url,
                text=text,
                method=method,
                quality_ok=True,
                quality_reason=reason,
            )
        if len(text) > len(best_failure[1]):
            best_failure = (method, text, quality_ok, reason)

    method, text, quality_ok, reason = best_failure
    return ArticleExtraction(
        url=url,
        text=text,
        method=method,
        quality_ok=quality_ok,
        quality_reason=reason,
    )


async def fetch_article_text(
    session: aiohttp.ClientSession, url: str
) -> ArticleExtraction:
    try:
        async with session.get(
            url,
            headers=_HEADERS,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=25),
        ) as response:
            if response.status != 200:
                return ArticleExtraction(
                    url=url,
                    text="",
                    method="http",
                    quality_ok=False,
                    quality_reason=f"HTTP {response.status}",
                    http_status=response.status,
                )
            content = await response.content.read(MAX_DOWNLOAD_BYTES + 1)
            if len(content) > MAX_DOWNLOAD_BYTES:
                return ArticleExtraction(
                    url=url,
                    text="",
                    method="http",
                    quality_ok=False,
                    quality_reason=f"response exceeded {MAX_DOWNLOAD_BYTES} bytes",
                    http_status=response.status,
                )
            charset = response.charset or "utf-8"
            html = content.decode(charset, errors="replace")
            result = extract_article_text(html, str(response.url))
            return ArticleExtraction(
                url=result.url,
                text=result.text,
                method=result.method,
                quality_ok=result.quality_ok,
                quality_reason=result.quality_reason,
                http_status=response.status,
            )
    except Exception as exc:
        return ArticleExtraction(
            url=url,
            text="",
            method="http",
            quality_ok=False,
            quality_reason=f"fetch failed: {exc}",
        )
