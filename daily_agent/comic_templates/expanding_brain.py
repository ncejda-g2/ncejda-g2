"""Expanding Brain — 4-panel escalating-enlightenment meme."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    p1 = fields["panel1_caption"]
    p2 = fields["panel2_caption"]
    p3 = fields["panel3_caption"]
    p4 = fields["panel4_caption"]
    return f"""A 4-panel vertical "Expanding Brain / Galaxy Brain" meme in {BLOB_STYLE}

Layout: tall portrait 1024x1792 image divided into FOUR equal-height horizontal panels stacked \
vertically with thin white gutters between them. Each panel shows the SAME pastel-blue blob \
character on the LEFT, head shown in profile facing right so the brain inside is visible, paired \
with a clean white rectangular caption box on the RIGHT.

Panel 1 (top): Blob in profile, normal small pink brain faintly visible inside head, \
neutral expression. Caption: {p1!r}.

Panel 2: SAME blob in profile, brain noticeably larger and gently glowing pale-blue. \
Mildly impressed expression. Caption: {p2!r}.

Panel 3: SAME blob in profile, brain very large, glowing bright with several radiating light rays \
escaping the head. Smug enlightened expression. Caption: {p3!r}.

Panel 4 (bottom): SAME blob in profile, head replaced by an enormous swirling cosmic galaxy of \
stars, nebulae, and cosmic energy. Caption: {p4!r}.

The four backgrounds progress from pale beige (top) to pale lavender to pale teal to deep navy with \
tiny stars (bottom) to underline the escalating cosmic enlightenment."""


TEMPLATE = MemeTemplate(
    id="expanding_brain",
    display_name="Expanding Brain / Galaxy Brain",
    story_shape=(
        "A 4-step escalation from mundane to absurdly cosmic — works when "
        "the joke is that successive 'improvements' or takes are getting "
        "ridiculously over-engineered or pretentious."
    ),
    required_fields=[
        "panel1_caption",
        "panel2_caption",
        "panel3_caption",
        "panel4_caption",
    ],
    field_descriptions={
        "panel1_caption": (
            "Smallest brain. The mundane / sensible / boring baseline. "
            "Each caption ≤12 words."
        ),
        "panel2_caption": "Slightly bigger brain. A modest step up.",
        "panel3_caption": "Glowing brain. Smug, over-engineered, getting ridiculous.",
        "panel4_caption": (
            "Galaxy brain. Maximum absurd cosmic take. Should land as the "
            "punchline of the escalation."
        ),
    },
    example_fields={
        "panel1_caption": "writing if/else statements",
        "panel2_caption": "training a small neural net",
        "panel3_caption": "deploying an LLM agent in production",
        "panel4_caption": "spawning recursive AI agents to debate themselves",
    },
    build_prompt=_build,
)
