"""Classic 6-panel comic strip — the original AI Newspaper format.

This template differs from the meme templates: the orchestrator injects extra
fields (`place`, `hat_first`, `hat_second`) into the fields dict *before*
calling `build_prompt`. The generator subagent never fills those — it only
fills the scene content (`adjective_first`, `adjective_second`,
`narrative_intro`, `panel1`..`panel6`).
"""

from ._shared import BLOB_STYLE  # noqa: F401  (kept for symmetry; classic uses its own style block)
from ._types import MemeTemplate


def build_classic_style_direction(hat_first: str, hat_second: str) -> str:
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


CLASSIC_LAYOUT_DIRECTION = (
    "Layout: a 2x3 grid of comic panels (2 columns wide, 3 rows tall) with thin white gutters between them. "
    "Panel reading order: top-left, top-right, middle-left, middle-right, bottom-left, bottom-right. "
    "Tall portrait 1024x1792 aspect ratio. Each panel must be clearly delimited. "
    "No author signature, no watermarks, no text outside speech bubbles."
)


def _build(fields: dict[str, str]) -> str:
    adj_first = fields["adjective_first"]
    adj_second = fields["adjective_second"]
    place = fields["place"]
    hat_first = fields["hat_first"]
    hat_second = fields["hat_second"]
    narrative_intro = fields["narrative_intro"]
    panels = [fields[f"panel{i}"] for i in range(1, 7)]

    style = build_classic_style_direction(hat_first, hat_second)

    return f"""{style}

{CLASSIC_LAYOUT_DIRECTION}

Scene context: {narrative_intro}

Render this 6-panel comic. Use the dialog EXACTLY as written - do NOT paraphrase, do NOT shorten, \
do NOT rewrite. Some panels are SILENT (no speech bubbles) - that is intentional pacing, do not \
add dialog where none is written. Visual descriptions in [brackets] tell you what to draw in that \
panel.

Panel 1:
{panels[0]}

Panel 2:
{panels[1]}

Panel 3:
{panels[2]}

Panel 4:
{panels[3]}

Panel 5:
{panels[4]}

Panel 6:
{panels[5]}

Character anchors (style-neutral — visual aesthetic comes from the style block above, do NOT add \
style words here): Both characters are human. The model designs their appearance based on the \
adjectives — the {adj_first} character should look {adj_first} (clothing, posture, expression all \
reflect that trait), and the {adj_second} character should look {adj_second}. The two characters \
appear with consistent appearance, costume, and colors across all 6 panels. The setting backdrop \
({place}) is visible in every panel. Vary panel composition: wide establishing shots, medium \
two-shots, close-ups for emotional beats."""


TEMPLATE = MemeTemplate(
    id="classic_6_panel",
    display_name="Classic 6-Panel Comic Strip",
    story_shape=(
        "Stories with a setup → build → pivot → silent reaction → punch → "
        "button arc. Works for nuanced, character-driven jokes that need "
        "comedic timing and specific dialog rather than a single iconic "
        "image. The orchestrator injects place, hat_first, hat_second."
    ),
    required_fields=[
        "adjective_first",
        "adjective_second",
        "narrative_intro",
        "panel1",
        "panel2",
        "panel3",
        "panel4",
        "panel5",
        "panel6",
    ],
    field_descriptions={
        "adjective_first": (
            "Pick ONE adjective for the first character from the character "
            "pool the orchestrator provides. Must be visually depictable at "
            "a glance (e.g. 'caffeinated', 'unhinged', 'smug'). Drop any "
            "species/animal word — the character is a person."
        ),
        "adjective_second": (
            "Same rules as adjective_first; pick a different adjective from "
            "the pool that creates contrast or chemistry with the first."
        ),
        "narrative_intro": (
            "One italicised line summarising the scene, in the form: "
            "'A [adjective_first] person and a [adjective_second] person "
            "discuss [story topic] [place].' Include the wrapping asterisks."
        ),
        "panel1": (
            "Full panel block. First line is the beat label '[setup]'. "
            "Then 0–2 dialog lines like 'ADJECTIVE PERSON: \"line, ≤12 "
            "words\"'. Optional '[Visual: ...]' line."
        ),
        "panel2": "Beat label '[build]'. Same format as panel1.",
        "panel3": "Beat label '[pivot]'. The reveal/twist. Same format.",
        "panel4": (
            "Beat label '[silent reaction]'. MUST be wordless — only a "
            "'[Visual: ...]' line. NO dialog. This silent beat is essential "
            "for comedic timing."
        ),
        "panel5": "Beat label '[punch]'. The punchline lands here.",
        "panel6": (
            "Beat label '[button]'. Closing visual beat — sight gag, reveal. "
            "Optional one final dialog line."
        ),
    },
    example_fields={
        "adjective_first": "nervous",
        "adjective_second": "hopeful",
        "narrative_intro": (
            "*A nervous person and a hopeful person discuss GPT-5 in a "
            "haunted castle.*"
        ),
        "panel1": (
            "[setup]\n"
            "NERVOUS PERSON: \"They benchmarked it on every test we have.\""
        ),
        "panel2": (
            "[build]\n"
            "HOPEFUL PERSON: \"And the scores are incredible!\""
        ),
        "panel3": (
            "[pivot]\n"
            "NERVOUS PERSON: \"They trained on the test sets.\""
        ),
        "panel4": (
            "[silent reaction]\n"
            "[Visual: The hopeful person's smile freezes; the nervous person "
            "stares dead-ahead. A single bat flits past behind them.]"
        ),
        "panel5": (
            "[punch]\n"
            "HOPEFUL PERSON: \"...all of them?\"\n"
            "NERVOUS PERSON: \"All of them.\""
        ),
        "panel6": (
            "[button]\n"
            "[Visual: A wall portrait of OpenAI's eval team is visibly "
            "weeping.]"
        ),
    },
    build_prompt=_build,
)
