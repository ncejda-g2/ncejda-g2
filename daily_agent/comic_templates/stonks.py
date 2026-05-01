"""Stonks — stock/valuation news meme with Meme Man iconography."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    headline = fields["headline"]
    return f"""A single-panel "Stonks" reaction meme in {BLOB_STYLE}

Layout: tall portrait 1024x1792 image, single full-bleed panel.

Background: a flat-design ROYAL-BLUE stock ticker grid pattern filling the entire panel. Rows and \
columns of small white numbers and percentages laid out in a clean tabular grid — readable values \
like "1.51%", "11,560", "0.12%", "2,344", "1.9%", "286", "0.168", "1,463", "0.9%", "4,872", scattered \
across the grid in legible white sans-serif. Between cells, sprinkle small flat-design cyan up-triangle \
and red down-triangle indicator icons. The grid sits clearly BEHIND the character and the arrow.

LEFT-CENTER of the panel: a single pastel-pink blob character shown from the chest up, wearing a \
flat-design dark navy business suit jacket with a small white shirt collar visible and a bright \
royal-blue tie. The face has a SMALL SUBTLE CONFIDENT closed-mouth smile, one corner pulled up just \
slightly, and the EYES are SLIGHTLY OFF-KILTER — one black-dot eye is positioned a touch differently \
than the other, NOT quite tracking together, giving an unmistakably mild "confused but pleased / I \
have no idea what is happening but it seems good" naive-confident expression. Calm, not surprised, \
not wide-eyed.

RIGHT-CENTER through bottom-RIGHT: a MASSIVE block-arrow pointing UP and to the RIGHT at a steep \
diagonal angle. The arrow body is solid ORANGE-AND-YELLOW (warm orange filling the arrow shape) and \
is wrapped in a thick BRIGHT YELLOW outline glow halo (rendered flat-design as a thick yellow border \
around the arrow shape — NOT a true gradient blur, just a chunky yellow rim). The arrow must NOT be \
green. Behind the arrow, a faint flat green jagged line-chart trends upward to reinforce the rise.

OVERLAID across the lower-right portion of the panel: the word "stonks" in LOWERCASE — rendered in \
chunky BOLD blocky white sans-serif letters with a thick BLACK outline around each letter. Letters \
should be slightly misaligned and uneven in size to evoke the iconic stylised meme typography. The \
"stonks" text is VERY LARGE, occupying a significant portion of the lower right of the panel. \
Important: lowercase "stonks", not uppercase, not "STONKS".

OVERLAID across the top of the panel (NOT inside a white box — directly on the blue grid background): \
the line {headline!r} in clean BOLD WHITE sans-serif with a thick BLACK outline, Impact-style overlay \
typography to match the "stonks" lettering treatment."""


TEMPLATE = MemeTemplate(
    id="stonks",
    display_name="Stonks",
    story_shape=(
        "Stock-price, valuation, market-cap, or 'number went up' news. "
        "Funding rounds, IPO pops, big-deal announcements that move "
        "valuations."
    ),
    required_fields=["headline"],
    field_descriptions={
        "headline": (
            "The news headline that explains why number went up. ≤14 words. "
            "Should sound like a real financial-news headline."
        ),
    },
    example_fields={
        "headline": "OpenAI valuation passes $500 billion",
    },
    build_prompt=_build,
)
