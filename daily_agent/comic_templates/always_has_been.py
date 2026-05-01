"""Always Has Been — astronaut cynical-reveal meme."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    front_speech = fields["front_speech"]
    back_speech = fields.get("back_speech", "always has been")
    return f"""A single-panel "Always Has Been" astronaut reaction meme in {BLOB_STYLE}

Layout: tall portrait 1024x1792 image, single full-bleed panel. Background: deep navy starfield with \
small flat-design white stars and a curved horizon of a planet (pale blue Earth-like) at the bottom \
quarter of the panel.

TWO blob characters in white astronaut spacesuits floating in space, both wearing rounded white \
astronaut helmets with reflective visors that frame their bald heads — but the dot-eyes and mouths \
are still clearly visible through the visors as if drawn on top.

FRONT astronaut (closer, lower in frame): a pastel-pink blob in a spacesuit, body angled three-quarters \
to the right, looking out at the planet horizon with a confused, wide-eyed slack-jawed expression. \
A clean white speech bubble points down from above this character containing: {front_speech!r}.

REAR astronaut (behind and slightly above the first, on the right): a pastel-blue blob in a spacesuit, \
facing the viewer with a deadpan flat expression — straight horizontal mouth, half-lidded eyes. \
This character holds a small flat-design grey cartoon pistol in one stubby gloved hand, pointed \
casually at the back of the front astronaut's helmet. A clean white speech bubble points to this \
character containing: {back_speech!r}."""


TEMPLATE = MemeTemplate(
    id="always_has_been",
    display_name="Always Has Been",
    story_shape=(
        "A cynical reveal — the new, alarming thing is actually how it's "
        "always been. Disillusionment punchlines, 'wait, it was always X?' "
        "framings."
    ),
    required_fields=["front_speech"],
    field_descriptions={
        "front_speech": (
            "The wide-eyed realisation question from the front astronaut. "
            "Phrase as a question or shocked statement. ≤10 words. Lowercase."
        ),
        "back_speech": (
            "Optional. The reveal. Defaults to 'always has been'. Only "
            "override if a specific variant fits better."
        ),
    },
    example_fields={
        "front_speech": "wait, it's all AI marketing?",
    },
    build_prompt=_build,
)
