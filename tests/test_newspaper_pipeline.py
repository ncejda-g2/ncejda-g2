import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch


DAILY_AGENT_DIR = Path(__file__).parents[1] / "daily_agent"
if str(DAILY_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(DAILY_AGENT_DIR))

from article_extraction import extract_article_text  # noqa: E402
from editorial import (  # noqa: E402
    classify_candidates,
    parse_previous_edition,
    remove_previous_items,
    select_editorial,
)
from llm_client import llm_usage_log, reset_llm_usage_log, summarize_llm_usage  # noqa: E402
from readme_renderer import render_readme  # noqa: E402
from scene_pipeline import _allowed_templates, _generator_schema  # noqa: E402


class PreviousEditionTests(unittest.TestCase):
    def test_parses_day_and_only_news_table_links(self) -> None:
        readme = """# 📰 The AI Newspaper — Day 41 (2026-08-26)

## 🗞️ Hacker News

| 1 | [Story One](https://example.com/story/) | Dev Tooling | A thing | 10 | [4](https://news.ycombinator.com/item?id=1) |

---

## 🔬 From the AI Labs

| 1 | [Lab Post](https://lab.example/post) | Lab | Research | Aug 26 |

---

## 🔥 Trending AI Repositories
[Unrelated](https://github.com/example/repo)
"""
        previous = parse_previous_edition(readme)

        self.assertEqual(previous.day_count, 41)
        self.assertEqual(previous.titles, {"story one", "lab post"})
        self.assertEqual(
            previous.urls,
            {"https://example.com/story", "https://lab.example/post"},
        )

    def test_removes_previous_title_or_normalized_url(self) -> None:
        previous = parse_previous_edition(
            "# The AI Newspaper — Day 1\n## 🗞️ Hacker News\n[Old](https://e.test/a/)\n---"
        )
        items = [
            {"title": "Old", "url": "https://different.test"},
            {"title": "Renamed", "url": "https://e.test/a"},
            {"title": "New", "url": "https://e.test/new"},
        ]
        self.assertEqual(remove_previous_items(items, previous), [items[2]])


class ArticleExtractionTests(unittest.TestCase):
    def test_extracts_main_article_and_excludes_navigation(self) -> None:
        html = (Path(__file__).parent / "fixtures" / "article.html").read_text()
        result = extract_article_text(html, "https://example.com/article")

        self.assertTrue(result.quality_ok, result.quality_reason)
        self.assertIn("ten trillion tokens", result.text)
        self.assertNotIn("Home Products Pricing Careers", result.text)
        self.assertNotIn("Privacy Terms Careers", result.text)

    def test_rejects_thin_extraction(self) -> None:
        result = extract_article_text("<article><p>Too short.</p></article>", "https://e.test")
        self.assertFalse(result.quality_ok)


class ReadmeRendererTests(unittest.TestCase):
    def test_renders_structured_rows_without_a_model(self) -> None:
        rendered = render_readme(
            day_count=42,
            timestamp="2026-08-27",
            hn_stories=[
                {
                    "title": "A | B",
                    "url": "https://example.com/story",
                    "type": "Dev Tooling",
                    "synopsis": "Useful agent tool",
                    "points": 123,
                    "comments": 45,
                    "comments_url": "https://news.ycombinator.com/item?id=1",
                }
            ],
            lab_posts=[],
            trending_markdown="",
            image_filename="comic.png",
            no_news=False,
            is_meme=False,
            story_title="A | B",
            story_url="https://example.com/story",
        )

        self.assertIn("Day 42 (2026-08-27)", rendered)
        self.assertIn("[A \\| B](https://example.com/story)", rendered)
        self.assertIn("[45](https://news.ycombinator.com/item?id=1)", rendered)
        self.assertIn('width="600"', rendered)


class EditorialSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_classifier_deduplicates_model_ids_in_python(self) -> None:
        stories = [
            {"id": 7, "title": "AI story", "url": "https://e.test", "score": 1, "comments": 2}
        ]
        model_result = {"hn_relevant_ids": [7, 7], "lab_relevant_urls": []}
        with patch("editorial.call_structured_llm", new=AsyncMock(return_value=model_result)):
            selected, labs = await classify_candidates(object(), stories, [])

        self.assertEqual(selected, stories)
        self.assertEqual(labs, [])

    async def test_model_selects_ids_but_source_data_remains_authoritative(self) -> None:
        story = {
            "id": 7,
            "title": "Real title",
            "url": "https://example.com/real",
            "score": 99,
            "comments": 12,
        }
        post = {
            "title": "Lab title",
            "url": "https://lab.example/post",
            "source": "Example Lab",
            "category": "Original",
            "summary": "",
            "date": "Aug 27, 2026",
            "date_obj": datetime(2026, 8, 27, tzinfo=timezone.utc),
        }
        model_result = {
            "hn_selections": [
                {"id": 7, "type": "Dev Tooling", "synopsis": "A concise synopsis"}
            ],
            "lab_selections": [
                {"url": "https://lab.example/post", "category": "Research"}
            ],
            "top_story": {"source": "hn", "identifier": "7"},
        }
        with patch("editorial.call_structured_llm", new=AsyncMock(return_value=model_result)):
            result = await select_editorial(object(), [story], [post])

        self.assertEqual(result.hn_stories[0]["title"], "Real title")
        self.assertEqual(result.hn_stories[0]["points"], 99)
        self.assertEqual(result.hn_stories[0]["comments"], 12)
        self.assertEqual(result.lab_posts[0]["source"], "Example Lab")
        self.assertEqual(result.top_story["url"], "https://example.com/real")


class UsageAccountingTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_llm_usage_log()

    def test_summarizes_every_recorded_phase_and_cost(self) -> None:
        llm_usage_log.extend(
            [
                {
                    "phase": "classification",
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "total_tokens": 110,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "reasoning_tokens": 0,
                    "duration_ms": 50,
                    "cost_usd": 0.01,
                },
                {
                    "phase": "comic_generator",
                    "input_tokens": 200,
                    "output_tokens": 20,
                    "total_tokens": 220,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "reasoning_tokens": 0,
                    "duration_ms": 75,
                    "cost_usd": 0.02,
                },
            ]
        )

        totals = summarize_llm_usage()

        self.assertEqual(totals["call_count"], 2)
        self.assertEqual(totals["total_tokens"], 330)
        self.assertEqual(totals["duration_ms"], 125)
        self.assertAlmostEqual(totals["cost_usd"], 0.03)


class ComicSchemaTests(unittest.TestCase):
    def test_classic_schema_requires_every_template_field(self) -> None:
        allowed = _allowed_templates("classic")
        schema = _generator_schema(allowed)
        template = next(iter(allowed.values()))

        self.assertEqual(schema["properties"]["template_id"]["enum"], [template.id])
        self.assertEqual(
            schema["properties"]["fields"]["required"],
            template.required_fields,
        )
        self.assertFalse(schema["properties"]["fields"]["additionalProperties"])

    def test_meme_schema_has_one_explicit_variant_per_template(self) -> None:
        allowed = _allowed_templates("meme")
        variants = _generator_schema(allowed)["oneOf"]

        self.assertEqual(len(variants), len(allowed))
        for variant in variants:
            template_id = variant["properties"]["template_id"]["enum"][0]
            self.assertEqual(
                variant["properties"]["fields"]["required"],
                allowed[template_id].required_fields,
            )


if __name__ == "__main__":
    unittest.main()
