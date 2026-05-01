"""Two Buttons / Daily Struggle — impossible choice between two options."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    button_left = fields["button_left"]
    button_right = fields["button_right"]
    return f"""A single-panel "Daily Struggle / Two Buttons" reaction meme in {BLOB_STYLE}

Layout: tall portrait 1024x1792 image, single full-bleed panel, pale yellow solid background.

In the lower half of the panel: a control panel with TWO large round red push-buttons side by side, \
each button has a clean white rectangular caption box mounted directly above it. \
LEFT button caption: {button_left!r}. \
RIGHT button caption: {button_right!r}.

Above the buttons, a single pastel-pink blob character is shown from the chest up, sweating profusely \
with multiple visible blue water droplets streaming down the round bald head. \
The blob's eyes are wide, anxious, slightly crossed in panic, with a tight pinched mouth. \
One stubby cartoon arm is raised, hand hovering hesitantly between the two buttons, \
finger pointed but undecided. The character is clearly agonising over an impossible choice."""


TEMPLATE = MemeTemplate(
    id="two_buttons",
    display_name="Two Buttons / Daily Struggle",
    story_shape=(
        "Two contradictory options that someone must pick between — both "
        "compelling or both bad. Industry dilemmas, leadership crossroads."
    ),
    required_fields=["button_left", "button_right"],
    field_descriptions={
        "button_left": (
            "Label on the left button. The two options should be in genuine "
            "tension. ≤8 words. Title case is fine."
        ),
        "button_right": (
            "Label on the right button. Should pull against button_left. "
            "≤8 words."
        ),
    },
    example_fields={
        "button_left": "Hire 1,000 AI engineers",
        "button_right": "Lay off 20% of staff",
    },
    build_prompt=_build,
)
