"""Trade Offer — absurdly lopsided value-exchange meme."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    i_receive = fields["i_receive"]
    you_receive = fields["you_receive"]
    return f"""A single-panel "Trade Offer" reaction meme in {BLOB_STYLE}

Layout: square 1024x1024 image, single full-bleed panel. Background: a flat solid deep-purple \
moody indoor scene with a few brighter purple horizontal LED light strip accents along the upper \
walls (flat-design, no gradients, no glow blur — just dark purple with a couple of brighter purple \
strip rectangles to evoke an influencer-style room).

TOP of the panel: a horizontal rounded-rectangle BRIGHT RED banner spans most of the panel width. \
The banner contains the bold WHITE block-lettered text "⚠ TRADE OFFER ⚠" with a small flat-design \
yellow-and-black warning triangle icon flanking the words on each side. The banner is centered \
horizontally near the top.

DIRECTLY BELOW the banner, two short white text labels side by side, no boxes, just plain white \
text on the dark purple background:
- LEFT label: "i receive:"
- RIGHT label: "you receive:"

DIRECTLY BELOW the labels, the actual content for each side, in plain white text:
- LEFT (under "i receive:"): {i_receive!r}
- RIGHT (under "you receive:"): {you_receive!r}

CENTER-LOWER portion of the panel: a single pastel-pink blob character shown from the chest up, \
centered, facing the viewer DEAD-ON with a deadpan dead-serious expression — straight horizontal \
mouth line, half-lidded steady eyes, NO smile, slight raised brow line indicating gravitas. \
BOTH stubby cartoon arms are raised in front of the chest and the FINGERTIPS of the two hands meet, \
pressing together to form a sharp pointed downward-pointing PYRAMID / STEEPLE / fingertip-prayer \
gesture between the hands. This finger-steeple pose is the load-bearing visual signature of the \
meme: hands meet at the fingertips in front of the chest forming a clear V or pyramid shape \
pointing down. Both palms face inward toward each other, fingers extended."""


TEMPLATE = MemeTemplate(
    id="trade_offer",
    display_name="Trade Offer",
    story_shape=(
        "An absurdly lopsided value exchange — perfect for AI deal news, "
        "data-for-access framings, or comically bad bargains being offered."
    ),
    required_fields=["i_receive", "you_receive"],
    field_descriptions={
        "i_receive": (
            "What the offering side gets. Should be the better/cheaper side "
            "of the trade. ≤12 words. Lowercase."
        ),
        "you_receive": (
            "What the recipient gets — should be transparently lopsided, "
            "playing on the absurdity of the deal. ≤12 words. Lowercase."
        ),
    },
    example_fields={
        "i_receive": "free GPU credits forever",
        "you_receive": "your entire codebase for training",
    },
    build_prompt=_build,
)
