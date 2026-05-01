"""Shared style fragments used across comic-template image-gen prompts."""


BLOB_STYLE = (
    "Minimalist modern flat-design aesthetic. Flat solid pastel colors only — no gradients, "
    "no shading, no outlines on the characters. Characters are smooth simple geometric blob "
    "shapes: bald with no hair, no eyebrows, no facial hair, no gendered features, oversized "
    "round heads, large round black-dot eyes, and simple curved mouths. Stubby simple cartoon "
    "arms and short rounded legs when needed for poses. "
    "Avoid: depicting any real person, photographic realism, anime, manga, hair, gendered features, "
    "cross-hatching, harsh contrast, watermarks, signatures, text outside the designated areas."
)
"""Anchor description of the blob-character visual identity. Every template
embeds this verbatim so the daily strip stays stylistically coherent across
formats."""


CAPTION_BOX_STYLE = (
    "Clean WHITE RECTANGULAR caption boxes with thin BLACK BORDERS containing neat sentence-case "
    "sans-serif black text. Speech bubbles are clean white rectangles with thin black borders and "
    "a small triangular pointer."
)
"""Standard caption / speech-bubble treatment shared by most templates. Some
templates (e.g. the 6-panel classic) reuse this; iconic-typography memes
(currently only Stonks) override it."""
