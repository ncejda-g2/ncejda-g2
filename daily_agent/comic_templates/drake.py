"""Drake Pointing — binary X-vs-Y reaction meme."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    caption_top = fields["caption_top"]
    caption_bottom = fields["caption_bottom"]
    return f"""A 2-panel vertical-stacked reaction meme in {BLOB_STYLE}

Layout: two equal square panels stacked vertically with a thin white gutter between them. \
Tall portrait 1024x1792 aspect ratio. Each panel is clearly delimited. \
Solid pastel beige-yellow background fills both panels.

Panel 1 (top): a single bald pastel-pink simple geometric blob character with a smooth rounded body, \
oversized round head, large round black-dot eyes, small mouth, no hair, no eyebrows, no gender features. \
The character wears an oversized MAROON / burgundy quilted cropped puffer jacket with a fur-trimmed \
hood resting behind the head and a subtle cream lining visible at the cuffs. The jacket color must be \
clearly maroon-burgundy red, NOT black, NOT brown. \
The character's body is turned three-quarters to the LEFT, head tilted away to the right with eyes squinted \
shut and mouth pinched into a clearly disgusted closed-mouth "ugh" frown. \
One stubby cartoon arm is raised in front of the body, palm flat toward the right side of the panel in a \
firm "stop / push away" rejection gesture. \
On the right half of the panel, a clean white rectangular caption box with a thin black border contains the \
text {caption_top!r} in neat black sentence-case sans-serif lettering.

Panel 2 (bottom): the SAME pastel-pink blob character in the SAME oversized maroon-burgundy quilted \
cropped puffer jacket with cream lining, now facing forward and smiling broadly with a wide curved happy \
mouth and round bright eyes. One stubby cartoon arm is raised, index finger extended, pointing \
enthusiastically toward the caption box on the right with clear approval. \
On the right half of the panel, a clean white rectangular caption box with a thin black border contains \
the text {caption_bottom!r} in neat black sentence-case sans-serif lettering.

Style notes for both panels: flat solid colors only, no gradients, no shading, no outlines on the character, \
minimal facial features, smooth simple geometric body. The two panels must depict the SAME character — \
same pastel-pink color, same maroon jacket, same body shape — with ONLY pose, expression, and arm position \
changing. This is a two-panel reaction meme in the iconic top-disgust / bottom-approval format."""


TEMPLATE = MemeTemplate(
    id="drake",
    display_name="Drake Pointing",
    story_shape=(
        "A binary X-vs-Y framing where one option is rejected and the other "
        "preferred — works when the news has a clear loser and a clear winner."
    ),
    required_fields=["caption_top", "caption_bottom"],
    field_descriptions={
        "caption_top": (
            "The thing being rejected/disliked. Short, ≤10 words. Lowercase. "
            "Should be the less-hyped or worse-received side of the news."
        ),
        "caption_bottom": (
            "The thing being preferred/approved. Short, ≤10 words. Lowercase. "
            "Should be the more-exciting or better-received side."
        ),
    },
    example_fields={
        "caption_top": "openai buys open source uv creators",
        "caption_bottom": "new Gemma open source models drop",
    },
    build_prompt=_build,
)
