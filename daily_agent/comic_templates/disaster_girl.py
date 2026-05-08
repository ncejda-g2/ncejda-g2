"""Disaster Girl — self-inflicted catastrophe meme."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    caption = fields["caption"]
    return f"""A single-panel "Disaster Girl" reaction meme in {BLOB_STYLE}

Layout: square 1024x1024 image, single full-bleed panel.

FOREGROUND (lower-right portion of the panel): a single pastel-pink blob character shown from the \
shoulders up, slightly off-center to the right, looking directly toward the viewer with a tiny \
mischievous closed-mouth smirk and dot eyes glinting with self-satisfaction. The character is clearly \
unbothered, almost proud, of what is happening behind them.

BACKGROUND: a server room or office building engulfed in flat-design flames — flat orange, red, and \
yellow stylised flames consume rows of server racks and office desks visible behind the character. \
Flat-shaded grey smoke drifts upward. A few sparks float in the air. The chaos is clearly the \
character's doing, and they are entirely unbothered.

A clean white rectangular caption box pinned at the bottom of the panel contains: {caption!r}."""


TEMPLATE = MemeTemplate(
    id="disaster_girl",
    display_name="Disaster Girl",
    story_shape=(
        "A self-inflicted catastrophe the perpetrator is unbothered by — "
        "perfect for 'someone deployed/shipped/approved X and is now smug "
        "about the resulting chaos' news."
    ),
    required_fields=["caption"],
    field_descriptions={
        "caption": (
            "First-person caption describing what the character did to cause "
            "the disaster. ≤14 words. Lowercase. Should sound proud."
        ),
    },
    example_fields={
        "caption": "i gave my AI agent sudo access on the prod server",
    },
    build_prompt=_build,
)
