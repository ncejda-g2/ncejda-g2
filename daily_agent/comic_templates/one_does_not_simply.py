"""One Does Not Simply — dramatic warning meme."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    caption_bottom = fields["caption_bottom"]
    return f"""A single-panel "One Does Not Simply" reaction meme in {BLOB_STYLE} \
The goal is to MATCH THE ICONIC MEME EXACTLY — including the specific head-and-eye pose described \
below. Treat the head/eye direction as the most important visual element along with the pinch gesture.

Layout: square 1024x1024 image, single full-bleed panel.

Background: a warm-lit medieval fantasy interior reminiscent of an elven hall. On the LEFT side of \
the panel, a flat-design stone-arch hearth/fireplace with rounded curved stone blocks framing a dark \
inner recess (no flames visible, just the stone arch). On the RIGHT side of the panel, a flat-design \
mustard-yellow / pale-gold draped curtain or tapestry with simple geometric folds. The walls between \
are warm amber-tan stone. Overall warm-amber lighting tone — flat shapes only, no gradients, no glow, \
no blur. NO other characters or figures of any kind in the background. Just stone, curtain, and \
warm wall.

CENTER of the panel: a single pastel-blue blob character shown from the chest up.

THE HEAD-AND-EYE POSE — this is the load-bearing detail and must match the meme exactly:

1. The HEAD/FACE is TILTED so that the chin is DROPPED DOWN toward the character's chest, and the \
top of the head is angled away from the viewer. The face is pointed DOWN AND SLIGHTLY TO THE \
CHARACTER'S OWN RIGHT (which is the VIEWER'S LEFT). Imagine the character has tucked their chin \
inward and rotated their head to look down-and-leftward at the floor. The roundness of the bald head \
is clearly seen from a slightly-above angle because the head is dipped forward.

2. BUT the EYES are looking UP, AT THE CAMERA — directly toward the viewer. Both round black-dot \
eyes are FULLY VISIBLE — not obscured, not in profile. The eyes are positioned HIGH up in the face \
(near the top of the face area, since the chin is tucked), looking UP THROUGH a slightly furrowed \
brow line. The eyes catch the viewer's gaze even though the face itself is angled down-left.

3. The mouth is SMALL and SLIGHTLY OPEN as if caught mid-sentence delivering a wise weighty warning, \
with the corners pulled into a faint knowing closed-lip grimace.

ONE stubby cartoon arm is raised in front of the face/chest at about chin level, elbow bent. The \
HAND is in a precise PINCH GESTURE — the load-bearing visual signature of the meme:
- The THUMB and INDEX FINGER are pressed CLOSE TOGETHER, fingertips nearly touching with only a \
small visible gap of empty air between them (as if delicately holding something tiny).
- The middle, ring, and pinky fingers are clearly CURLED INWARD toward the palm.
- The hand is held up near the side of the character's face, the pinch oriented so the gap between \
thumb and forefinger is plainly visible to the viewer.
NOT a palm-up cautioning gesture. NOT an open hand. A precise, deliberate pinch.

CAPTIONS — use clean WHITE RECTANGULAR caption boxes with thin BLACK BORDERS containing neat \
sentence-case sans-serif black text. DO NOT use Impact-style overlay typography. DO NOT use white \
text with black outlines.

A clean white rectangular caption box pinned across the top of the panel contains: \
"One does not simply".

A second clean white rectangular caption box pinned across the bottom of the panel contains: \
{caption_bottom!r}."""


TEMPLATE = MemeTemplate(
    id="one_does_not_simply",
    display_name="One Does Not Simply",
    story_shape=(
        "A dramatic warning that something everyone is rushing into is "
        "actually much harder/riskier than it sounds. Premature shipping, "
        "underestimated complexity, naive optimism."
    ),
    required_fields=["caption_bottom"],
    field_descriptions={
        "caption_bottom": (
            "The punchline action that 'one does not simply' do. Should "
            "name a specific underestimated task. ≤14 words. Sentence case."
        ),
    },
    example_fields={
        "caption_bottom": "ship an LLM agent to production in two weeks",
    },
    build_prompt=_build,
)
