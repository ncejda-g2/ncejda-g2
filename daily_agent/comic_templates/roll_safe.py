"""Roll Safe — self-defeating-logic meme."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    caption = fields["caption"]
    return f"""A single-panel "Roll Safe / Smart Guy Tapping Head" reaction meme in {BLOB_STYLE}

Layout: square 1024x1024 image, single full-bleed panel, flat solid pale beige background.

A single pastel-pink blob character is shown from the shoulders up, centered. The head is turned \
slightly to one side so the viewer sees it at a THREE-QUARTER angle, NOT facing dead-on.

THE FACE — this is the most important part:
- The mouth is a VERY SUBTLE sly smirk: ONE corner of the mouth pulled up just a tiny bit, the rest \
of the mouth is a small straight horizontal line. The mouth must be SMALL and TIGHT — NOT a wide \
smile, NOT cheerful, NOT a half-grin. The vibe is "I just outsmarted you and I am thinking about it" \
rather than "I am happy".
- The EYES are looking SIDEWAYS toward the corner of the panel — clearly glancing away from the \
viewer, NOT making direct eye contact. Half-lidded, slightly downward-tilted lids, with a knowing \
condescending air.
- The overall expression should read as SLY, KNOWING, AND DEVIOUS — like the character has just \
realised something cunning. NOT happy, NOT cute, NOT cheerful.

ONE stubby cartoon arm is raised, with the index finger extended and TAPPING THE SIDE OF THE \
CHARACTER'S OWN HEAD at the temple — the finger is clearly pressed against the side of the bald \
head, the elbow bent at roughly a right angle. The other arm hangs loose by the side.

A clean white rectangular caption box pinned at the bottom of the panel contains: {caption!r}."""


TEMPLATE = MemeTemplate(
    id="roll_safe",
    display_name="Roll Safe / Smart Guy Tapping Head",
    story_shape=(
        "Self-defeating tautological logic — 'you can't have X if you don't "
        "Y' framings where the punchline is the absurd preventative."
    ),
    required_fields=["caption"],
    field_descriptions={
        "caption": (
            "The smug self-defeating-logic caption. Often takes the form "
            "'you can't [bad thing] if you never [necessary precondition]'. "
            "Use a forward slash ' / ' to break the line if it runs long. "
            "≤22 words total."
        ),
    },
    example_fields={
        "caption": "you can't have AI hallucinations / if you never trust the AI in the first place",
    },
    build_prompt=_build,
)
