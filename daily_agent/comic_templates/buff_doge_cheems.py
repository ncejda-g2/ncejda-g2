"""Buff Doge vs Cheems — past-strong-vs-present-weak comparison meme."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    buff_caption = fields["buff_caption"]
    cheems_caption = fields["cheems_caption"]
    return f"""A single-panel "Buff Doge vs Cheems" comparison meme in {BLOB_STYLE}

Layout: square 1024x1024 image, single full-bleed panel, pale teal solid background. The \
panel is divided down the middle into LEFT half and RIGHT half by a thin vertical white gutter.

LEFT half: a TALL, MUSCULAR pastel-yellow blob character standing tall and proud, body filled out \
with cartoonishly oversized exaggerated muscles — big rounded pecs, broad bulging shoulders, thick \
biceps flexed up in a strong-man double-bicep pose, big stubby arms held up beside the head. The \
face has a confident smug closed-mouth smirk and squinted determined eyes. The character is clearly \
strong and capable. A clean white rectangular caption box pinned at the bottom of this half reads: \
{buff_caption!r}.

RIGHT half: a TINY, FRAIL pastel-yellow blob character (same color, same blob species, just \
weaker-looking) standing meekly with a tiny rounded body, narrow shoulders, thin little stubby arms \
hanging limp at its sides, slightly hunched. The face has wide watery sad-puppy eyes and a small \
trembling worried frown. The character is clearly weak and nervous. A clean white rectangular \
caption box pinned at the bottom of this half reads: {cheems_caption!r}.

The two characters are clearly the same species/color but the strong-vs-weak contrast is dramatic."""


TEMPLATE = MemeTemplate(
    id="buff_doge_cheems",
    display_name="Buff Doge vs Cheems",
    story_shape=(
        "A past-was-strong vs present-is-weak comparison. Works for "
        "'industry/tool/practice was robust then, brittle now' framings, or "
        "any X-was-X then vs X-is-Y now contrast."
    ),
    required_fields=["buff_caption", "cheems_caption"],
    field_descriptions={
        "buff_caption": (
            "Caption under the strong character — the older/better version. "
            "≤12 words. Lowercase."
        ),
        "cheems_caption": (
            "Caption under the weak character — the newer/diminished version. "
            "Should mirror buff_caption's structure for contrast. ≤12 words."
        ),
    },
    example_fields={
        "buff_caption": "writing code by hand in 2015",
        "cheems_caption": "writing code by hand in 2025",
    },
    build_prompt=_build,
)
