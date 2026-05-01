"""They're the Same Picture (Pam) — 'new' thing is just the old thing."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    paper_left = fields["paper_left"]
    paper_right = fields["paper_right"]
    speech = fields.get("speech", "they're the same picture")
    return f"""A single-panel "They're the Same Picture" reaction meme in {BLOB_STYLE}

Layout: tall portrait 1024x1792 image, single full-bleed panel, pale beige solid background \
suggesting an office wall.

A single pastel-pink blob character stands at the center of the panel, shown from the waist up, \
facing forward with a deadpan flat expression — straight horizontal mouth line, half-lidded \
unimpressed eyes. Both stubby cartoon arms are raised, each one holding up a large white sheet \
of paper toward the viewer.

Both sheets are identical in size and shape, each rendered as a clean white rectangle with a thin \
black border. They contain text in neat black sans-serif:

LEFT sheet: {paper_left!r}.

RIGHT sheet: {paper_right!r}.

Below the character at the bottom of the panel, a clean white speech bubble with thin black border \
contains: {speech!r}."""


TEMPLATE = MemeTemplate(
    id="same_picture",
    display_name="They're the Same Picture",
    story_shape=(
        "A 'new' thing that's transparently the same as an old thing — "
        "rebrandings, repackaged research, marketing-driven repackaging."
    ),
    required_fields=["paper_left", "paper_right"],
    field_descriptions={
        "paper_left": (
            "Text on the left sheet — the supposedly 'new' or hyped thing. "
            "≤14 words. Should sound impressive on its own."
        ),
        "paper_right": (
            "Text on the right sheet — the underwhelming reality. ≤14 words. "
            "The deadpan deflation of paper_left."
        ),
        "speech": (
            "Optional. Speech bubble line. Default 'they're the same picture' "
            "— only override for a specific variant."
        ),
    },
    example_fields={
        "paper_left": "GPT-5: emergent multi-step reasoning",
        "paper_right": "GPT-4 with a longer system prompt",
    },
    build_prompt=_build,
)
