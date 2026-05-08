"""Anakin/Padme — 4-panel optimistic-claim → ominous-realisation meme."""

from ._shared import BLOB_STYLE
from ._types import MemeTemplate


def _build(fields: dict[str, str]) -> str:
    p1 = fields["panel1_dialog"]
    p2 = fields["panel2_dialog"]
    p4 = fields["panel4_dialog"]
    return f"""A 4-panel "Anakin and Padme" reaction meme in {BLOB_STYLE}

Layout: square 1024x1024 image divided into a 2x2 grid of FOUR equal panels with thin white \
gutters between them. Reading order: top-left, top-right, bottom-left, bottom-right.

The setting in every panel is the same: an outdoor green meadow at sunset with a soft pale orange \
and pastel-green flat-design background, a couple of simple stylised flowers in the foreground.

TWO blob characters are in every panel: a pastel-blue blob (call them character A) and a pastel-pink \
blob (call them character B), shown from the chest up, sitting opposite each other facing each other \
in profile.

Panel 1 (top-left): Character A (pastel-blue, on the LEFT, facing right) leans in with a wide proud \
smile. White speech bubble from A: {p1!r}.

Panel 2 (top-right): Character B (pastel-pink, on the RIGHT, facing left) smiles back warmly with \
slight raised brows. White speech bubble from B: {p2!r}.

Panel 3 (bottom-left): SAME framing as Panel 1 — character A on the left facing right — but now A's \
expression has gone completely BLANK and SILENT: flat horizontal mouth line, half-lidded eyes, no \
smile, no speech bubble at all. Character A says nothing.

Panel 4 (bottom-right): SAME framing as Panel 2 — character B on the right facing left — but now \
B's smile has DROPPED, eyes are now wide and horrified, mouth slightly open in dawning realisation. \
White speech bubble from B: {p4!r}. Both characters and setting must look consistent across all \
four panels — same colors, same body shapes, same backgrounds — only expressions and speech change."""


TEMPLATE = MemeTemplate(
    id="anakin_padme",
    display_name="Anakin / Padme 4-Panel",
    story_shape=(
        "An optimistic claim followed by a dawning ominous realisation. "
        "Works for tech-progress-with-hidden-cost stories, AI safety asks "
        "that go unanswered, premature 'we solved it' announcements."
    ),
    required_fields=["panel1_dialog", "panel2_dialog", "panel4_dialog"],
    field_descriptions={
        "panel1_dialog": (
            "Character A's proud opening claim. Should sound exciting/positive "
            "on the surface. ≤14 words. Sentence case."
        ),
        "panel2_dialog": (
            "Character B's concerned follow-up — a trailing-off question that "
            "sets up the silent dread. Must end in '...right?' or similar. "
            "≤14 words."
        ),
        "panel4_dialog": (
            "Character B's horrified second 'right?' — usually shorter than "
            "panel2_dialog, often just '...right?' itself. ≤8 words."
        ),
    },
    example_fields={
        "panel1_dialog": "I trained an AI agent that fixes its own bugs.",
        "panel2_dialog": "...you tested it in a sandbox first, right?",
        "panel4_dialog": "...right?",
    },
    build_prompt=_build,
)
