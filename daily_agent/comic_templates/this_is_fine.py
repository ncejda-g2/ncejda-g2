"""This Is Fine — character calmly ignoring catastrophe."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    caption = fields["caption"]
    speech = fields.get("speech", "This is fine.")
    return f"""A single-panel "This Is Fine" reaction meme in {BLOB_STYLE}

Layout: tall portrait 1024x1792 image, single full-bleed panel.

A pastel-pink blob character sits calmly at a small wooden round table at the center of the panel, \
holding a tiny white coffee mug with one stubby cartoon arm. The blob has a serene, slightly forced \
smile and round black-dot eyes looking straight ahead at the viewer.

The ENTIRE room around the blob is engulfed in flames — flat-shaded orange, red, and yellow flames \
fill the floor, walls, ceiling, and surround the table. Visible flat-shaded smoke clouds drift across \
the upper portion of the panel. The flames are stylised in flat-design (no gradients, no realistic \
fire texture), simple curved orange and red shapes.

A clean white speech bubble with thin black border emerges from the blob's mouth containing the text: \
{speech!r}.

A clean white rectangular caption box pinned at the bottom of the panel contains: {caption!r}."""


TEMPLATE = MemeTemplate(
    id="this_is_fine",
    display_name="This Is Fine",
    story_shape=(
        "A catastrophe that someone is calmly ignoring or normalising. Works "
        "for outages, ethical disasters, runaway-AI behavior, or 'everything "
        "is on fire and we're shipping it anyway' stories."
    ),
    required_fields=["caption"],
    field_descriptions={
        "caption": (
            "Caption pinned at the bottom describing what is on fire. ≤14 "
            "words, lowercase. Should name the disaster being ignored."
        ),
        "speech": (
            "Optional. The speech bubble line. Defaults to 'This is fine.' — "
            "only override if a sharper variant fits the news exactly."
        ),
    },
    example_fields={
        "caption": "my AI coding agent in production",
    },
    build_prompt=_build,
)
