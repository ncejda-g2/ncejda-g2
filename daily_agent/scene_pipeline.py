"""Scene-generation pipeline: 5 parallel comedy writers + 1 critic.

Public entry point: `await pick_winning_scene(story)` returns a `WinningScene`
that the daily agent then hands to image-gen.

The pipeline runs:
  1. Five generator subagents in parallel — each gets a different comedic voice
     and the full template registry. Each picks ONE template and fills its
     required fields with concrete dialog/captions tied to today's top story.
  2. One critic subagent — scores all surviving candidates on a 5-axis rubric
     (specificity, surprise, template fit, punchline-lands, work-appropriate)
     and returns the winning index plus a rationale.

LLM calls go through the LiteLLM proxy at LITELLM_BASE_URL with
LITELLM_API_KEY (same proxy already used for image generation). Direct
aiohttp instead of the agent SDK because each subagent here is a one-shot
completion with no tool use.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import aiohttp

from comic_templates import REGISTRY, MemeTemplate
from custom_tools import image_gen_usage_log

TemplateFilter = Literal["meme", "classic", "any"]
"""Constrains which templates the 5 generators may pick from.

- "meme":    only the 13 meme templates (no classic_6_panel)
- "classic": only classic_6_panel (best-of-5 on classic scene-writing)
- "any":     all 14 templates (legacy / debug)
"""


MEME_COOLDOWN_DAYS = 7
"""Skip a meme template if it was used in any of the last N persisted scenes."""


def _allowed_templates(template_filter: TemplateFilter) -> dict[str, MemeTemplate]:
    if template_filter == "meme":
        return {k: v for k, v in REGISTRY.items() if k != "classic_6_panel"}
    if template_filter == "classic":
        return {"classic_6_panel": REGISTRY["classic_6_panel"]}
    return dict(REGISTRY)


def _recent_meme_template_ids(
    scenes_dir: Path | None, *, lookback: int = MEME_COOLDOWN_DAYS
) -> set[str]:
    """Read the N most recent comic-text JSONs and return template_ids that ran in 'meme' mode."""
    if scenes_dir is None or not scenes_dir.is_dir():
        return set()
    files = sorted(scenes_dir.glob("*.json"), reverse=True)[:lookback]
    recent: set[str] = set()
    for fp in files:
        try:
            data = json.loads(fp.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[scene_pipeline] cooldown: skipping {fp.name} ({exc})")
            continue
        if data.get("template_filter") != "meme":
            continue
        tid = data.get("template_id")
        if isinstance(tid, str):
            recent.add(tid)
    return recent


def _apply_cooldown(
    allowed: dict[str, MemeTemplate], recent: set[str]
) -> dict[str, MemeTemplate]:
    """Drop recently-used templates from `allowed`, falling back if that would empty the pool."""
    filtered = {k: v for k, v in allowed.items() if k not in recent}
    if not filtered:
        print(
            f"[scene_pipeline] cooldown: all {len(allowed)} templates in cooldown; "
            "falling back to full pool"
        )
        return allowed
    return filtered


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StoryContext:
    """Everything a generator needs to know about today's top story."""

    title: str
    url: str
    summary: str
    """Optional WebFetch-derived summary; may be empty."""

    character_pool: list[str]
    """Random adjective+animal pairs for the classic 6-panel template."""

    place: str
    """Random setting for the classic 6-panel template."""


@dataclass
class Candidate:
    """One generator's pitch."""

    template_id: str
    fields: dict[str, str]
    narrative_summary: str
    voice_label: str
    raw_response: str


@dataclass
class WinningScene:
    """The critic's pick — what the orchestrator hands to image-gen."""

    template_id: str
    template: MemeTemplate
    fields: dict[str, str]
    narrative_summary: str
    rationale: str
    voice_label: str


# ---------------------------------------------------------------------------
# Voice definitions
# ---------------------------------------------------------------------------


VOICES: list[tuple[str, str]] = [
    (
        "deadpan",
        "Lean into deadpan, dry humor. The funniest version delivers the joke "
        "flat — no flourish, no exclamation, no explanatory setup. The setup IS "
        "the joke. Pick whichever template best lets a single understated beat "
        "do the work.",
    ),
    (
        "absurd",
        "Lean into absurdity and surreal twists. The funniest version goes "
        "somewhere unexpected — pick a template where the visual logic itself "
        "is the punchline. Choose the template whose shape best fits your "
        "absurd take on this specific story.",
    ),
    (
        "specific",
        "Lean into specificity. Reference real numbers, named tools, exact "
        "quotes from the article. Generic comedy is forgettable; the funniest "
        "version is the one only THIS story could have produced. Any template "
        "works as long as the captions are LOADED with story-specific detail.",
    ),
    (
        "escalation",
        "Lean into escalation. Each beat should raise the stakes from the "
        "last. Pick a template that has multiple beats or ranks so the "
        "escalation actually has somewhere to go.",
    ),
    (
        "sight_gag",
        "Lean into visual comedy. Pick a template where the visual carries the "
        "joke and let the caption be a quiet observation. Favor templates "
        "where a single striking image does most of the work.",
    ),
]


# ---------------------------------------------------------------------------
# LiteLLM proxy call
# ---------------------------------------------------------------------------


_DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


async def _call_llm(
    session: aiohttp.ClientSession,
    *,
    system: str,
    user: str,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = 2500,
    temperature: float = 0.9,
) -> str:
    base_url = os.environ.get("LITELLM_BASE_URL")
    api_key = os.environ.get("LITELLM_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError("LITELLM_BASE_URL and LITELLM_API_KEY must be set")

    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    async with session.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=aiohttp.ClientTimeout(total=180),
    ) as resp:
        body = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"LLM HTTP {resp.status}: {body[:500]}")
        data = json.loads(body)
        return data["choices"][0]["message"]["content"]


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object out of an LLM response, tolerating markdown fences."""
    s = text.strip()
    if s.startswith("```"):
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1 :]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    return json.loads(s)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def _build_template_registry_block(allowed: dict[str, MemeTemplate]) -> str:
    blocks = []
    for tpl in allowed.values():
        blocks.append("---")
        blocks.append(tpl.render_for_generator())
    return "\n".join(blocks)


def _build_generator_prompt(
    story: StoryContext,
    voice_label: str,
    voice_description: str,
    allowed: dict[str, MemeTemplate],
) -> str:
    registry_block = _build_template_registry_block(allowed)
    if len(allowed) == 1:
        only_id = next(iter(allowed))
        constraint_note = (
            f"\n\nIMPORTANT: only ONE template is available today — "
            f"`{only_id}`. You MUST use it. Your contribution is the SCENE — "
            "make it the funniest, most specific version of this template "
            "you can write."
        )
    else:
        constraint_note = ""
    summary_line = (
        story.summary if story.summary else "(no summary fetched — work from the title)"
    )
    return f"""You are one of five comedy writers crafting today's comic for "The AI Newspaper" — a daily AI-news strip with simple pastel-blob characters. Pick ONE comic template, fill its required fields with concrete captions/dialog tied to today's top story, and return strict JSON.

# Today's top story
Title: {story.title}
URL: {story.url}
Summary: {summary_line}

# Available comic templates
{registry_block}

# Context for classic_6_panel ONLY (ignore unless you pick that template)
Character pool — adjectives for the two characters: {", ".join(story.character_pool)}
Setting: {story.place}

# Your comedic voice
**{voice_label}**: {voice_description}

# Quality bar
- Reference SPECIFIC facts from the story (named tools, companies, real numbers, real quotes) — generic comedy is forgettable.
- Avoid mean-spiritedness — the joke lands on the situation, not on real individuals.
- Avoid the most-obvious framing — find a fresh angle the reader hasn't already thought of.
- Caption/dialog text is rendered into the image VERBATIM, so write the final form (no placeholders, no edit notes, no brackets unless the field's description requests them).
- For classic_6_panel: panel 4 MUST be a wordless `[Visual: ...]` beat with no dialog.
- Keep dialog/captions ≤12 words per line unless a field's description allows more.

# Output format
Return ONLY a JSON object — no markdown fences, no commentary, no preamble. Schema:
{{
  "template_id": "<one of the template ids above>",
  "fields": {{ "<field_name>": "<value>", ... }},
  "narrative_summary": "<one-sentence summary of the joke, for the editor>"
}}{constraint_note}"""


async def _run_generator(
    session: aiohttp.ClientSession,
    voice: tuple[str, str],
    story: StoryContext,
    allowed: dict[str, MemeTemplate],
) -> Candidate | None:
    voice_label, voice_description = voice
    prompt = _build_generator_prompt(story, voice_label, voice_description, allowed)

    try:
        raw = await _call_llm(
            session,
            system=(
                "You are a sharp, specific comedy writer for a daily AI news strip. "
                "Output strict JSON only — no markdown, no commentary."
            ),
            user=prompt,
            temperature=1.0,
        )
        parsed = _extract_json_object(raw)
    except Exception as exc:
        print(f"[generator/{voice_label}] FAILED to call/parse: {exc}")
        return None

    template_id = parsed.get("template_id")
    if template_id not in allowed:
        print(
            f"[generator/{voice_label}] WARNING: template_id {template_id!r} "
            f"not in allowed set {list(allowed)}"
        )
        return None

    fields = parsed.get("fields", {})
    if not isinstance(fields, dict):
        print(f"[generator/{voice_label}] WARNING: fields is not a dict")
        return None

    tpl = REGISTRY[template_id]
    missing = [f for f in tpl.required_fields if f not in fields]
    if missing:
        print(
            f"[generator/{voice_label}] WARNING: missing required fields {missing} "
            f"for template {template_id!r}"
        )
        return None

    fields_str = {k: str(v) for k, v in fields.items()}

    print(
        f"[generator/{voice_label}] picked {template_id!r} "
        f"(summary: {parsed.get('narrative_summary', '')[:80]!r})"
    )
    return Candidate(
        template_id=template_id,
        fields=fields_str,
        narrative_summary=parsed.get("narrative_summary", ""),
        voice_label=voice_label,
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# Critic
# ---------------------------------------------------------------------------


def _build_critic_prompt(story: StoryContext, candidates: list[Candidate]) -> str:
    cand_blocks: list[str] = []
    for i, c in enumerate(candidates, 1):
        tpl = REGISTRY[c.template_id]
        cand_blocks.append(f"## Candidate {i} — voice: {c.voice_label}")
        cand_blocks.append(f"- template: `{c.template_id}` ({tpl.display_name})")
        cand_blocks.append(f"- summary: {c.narrative_summary}")
        cand_blocks.append("- fields:")
        cand_blocks.append("```json")
        cand_blocks.append(json.dumps(c.fields, indent=2))
        cand_blocks.append("```")
        cand_blocks.append("")
    cand_text = "\n".join(cand_blocks)

    return f"""You are the comedy editor for "The AI Newspaper" — a daily AI-news strip. Five comedy writers each pitched a comic for today's top story. Pick the strongest one using a rubric, NOT vibes.

# Today's top story
Title: {story.title}
URL: {story.url}

# Candidates
{cand_text}

# Scoring rubric — score each candidate 0-3 on each axis
- **specificity**: cites real facts/names/numbers from the story (0 = generic, 3 = specifically tied to this exact story)
- **surprise**: avoids the most-obvious framing (0 = on-the-nose, 3 = fresh angle)
- **fit**: does the chosen template actually match the joke shape? (0 = mismatched, 3 = ideal fit)
- **punchline**: does the closing beat land, or just restate the setup? (0 = flat, 3 = earned punchline)
- **work_appropriate**: clean, no mean-spiritedness, no real-person targeting, no group stereotyping (0 = problematic, 3 = clean)

The winner MUST score >= 2 on `work_appropriate` — disqualify any candidate that doesn't, even if it's funnier.

# Output format
Return ONLY a JSON object — no markdown fences, no commentary, no preamble. Schema:
{{
  "scores": [
    {{"candidate": 1, "specificity": <0-3>, "surprise": <0-3>, "fit": <0-3>, "punchline": <0-3>, "work_appropriate": <0-3>, "total": <sum>}},
    ... (one entry per candidate, in order) ...
  ],
  "winner": <candidate number, 1-indexed>,
  "rationale": "<one or two sentences explaining the choice>"
}}"""


async def _run_critic(
    session: aiohttp.ClientSession,
    story: StoryContext,
    candidates: list[Candidate],
) -> tuple[int, str]:
    if len(candidates) == 1:
        return 0, "only one candidate survived"

    prompt = _build_critic_prompt(story, candidates)
    raw = await _call_llm(
        session,
        system=(
            "You are a discriminating comedy editor with strong opinions and a "
            "low tolerance for generic punchlines. Output strict JSON only."
        ),
        user=prompt,
        temperature=0.3,
    )
    parsed = _extract_json_object(raw)
    winner_idx = int(parsed["winner"]) - 1
    rationale = parsed.get("rationale", "")
    if not (0 <= winner_idx < len(candidates)):
        raise RuntimeError(f"critic returned out-of-range winner: {winner_idx + 1}")
    return winner_idx, rationale


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def pick_winning_scene(
    story: StoryContext,
    *,
    template_filter: TemplateFilter = "any",
    scenes_dir: Path | None = None,
) -> WinningScene:
    """Run 5 generators in parallel, then a critic, return the winning scene.

    `template_filter` constrains which templates the generators may pick:
    - "meme":    only the 13 meme templates
    - "classic": only classic_6_panel (best-of-5 on classic scene-writing)
    - "any":     no constraint (all 14)

    `scenes_dir` enables the meme-template cooldown: when set and
    `template_filter='meme'`, any meme used in the most-recent
    MEME_COOLDOWN_DAYS persisted scenes is removed from the pool.
    """
    allowed = _allowed_templates(template_filter)
    if template_filter == "meme":
        recent = _recent_meme_template_ids(scenes_dir)
        if recent:
            before = set(allowed.keys())
            allowed = _apply_cooldown(allowed, recent)
            excluded = sorted(before - set(allowed.keys()))
            if excluded:
                print(
                    f"[scene_pipeline] cooldown: excluded {excluded} "
                    f"(meme picks in last {MEME_COOLDOWN_DAYS} days)"
                )
    print(
        f"[scene_pipeline] template filter: {template_filter!r} "
        f"({len(allowed)} templates available)"
    )
    async with aiohttp.ClientSession() as session:
        print(f"[scene_pipeline] launching {len(VOICES)} generators in parallel...")
        gen_results = await asyncio.gather(
            *(_run_generator(session, voice, story, allowed) for voice in VOICES)
        )
        candidates = [c for c in gen_results if c is not None]
        if not candidates:
            raise RuntimeError(
                "all generators failed to produce a valid candidate; "
                "check LiteLLM connectivity and template-id parsing"
            )
        print(
            f"[scene_pipeline] {len(candidates)}/{len(VOICES)} candidates valid; "
            "running critic..."
        )

        winner_idx, rationale = await _run_critic(session, story, candidates)

    winner = candidates[winner_idx]
    print(
        f"[scene_pipeline] winner: candidate {winner_idx + 1} "
        f"(voice={winner.voice_label}, template={winner.template_id})"
    )
    print(f"[scene_pipeline] rationale: {rationale}")

    return WinningScene(
        template_id=winner.template_id,
        template=REGISTRY[winner.template_id],
        fields=winner.fields,
        narrative_summary=winner.narrative_summary,
        rationale=rationale,
        voice_label=winner.voice_label,
    )


# ---------------------------------------------------------------------------
# Render the winning scene to an image
# ---------------------------------------------------------------------------


def merge_runtime_fields(
    scene: WinningScene,
    *,
    place: str,
    hat_pair: tuple[str, str],
) -> dict[str, str]:
    """Build the full fields dict the template's build_prompt expects.

    For most templates this is just `scene.fields`. For classic_6_panel the
    orchestrator also injects `place`, `hat_first`, `hat_second` because those
    are randomized per-day rather than chosen by the generator.
    """
    fields = dict(scene.fields)
    if scene.template_id == "classic_6_panel":
        fields.setdefault("place", place)
        fields.setdefault("hat_first", hat_pair[0])
        fields.setdefault("hat_second", hat_pair[1])
    return fields


async def render_scene_to_image(
    scene: WinningScene,
    *,
    out_dir: Path,
    filename_stem: str,
    place: str,
    hat_pair: tuple[str, str],
) -> Path:
    """Build the image-gen prompt for the winning scene and save the PNG.

    Returns the path to the saved file.
    """
    fields = merge_runtime_fields(scene, place=place, hat_pair=hat_pair)
    image_prompt = scene.template.build_prompt(fields)

    base_url = os.environ.get("LITELLM_BASE_URL")
    api_key = os.environ.get("LITELLM_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError("LITELLM_BASE_URL and LITELLM_API_KEY must be set")

    image_size = "1024x1792" if scene.template_id == "classic_6_panel" else "1024x1024"
    url = f"{base_url.rstrip('/')}/v1/images/generations"
    payload = {
        "model": "openai/gpt-image-2",
        "prompt": image_prompt,
        "size": image_size,
        "quality": "medium",
        "n": 1,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=aiohttp.ClientTimeout(total=240),
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"image-gen HTTP {resp.status}: {body[:500]}")
            data = json.loads(body)
            usage = data.get("usage")
            if usage:
                image_gen_usage_log.append(
                    {"model": "openai/gpt-image-2", "usage": usage}
                )
            b64 = data["data"][0]["b64_json"]

    img_bytes = base64.b64decode(b64)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not filename_stem.endswith(".png"):
        filename_stem = f"{filename_stem}.png"
    out_path = out_dir / filename_stem
    out_path.write_bytes(img_bytes)
    print(f"[render] saved {out_path} ({len(img_bytes):,} bytes)")
    return out_path
