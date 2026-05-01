"""Type definitions for the comic-template registry."""

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class MemeTemplate:
    """One comic format the daily agent can choose from.

    The generator subagents see `display_name`, `story_shape`, `field_descriptions`,
    and `example_fields` when deciding whether to pick this template and what to
    fill in. The critic compares filled candidates across templates. The image-gen
    step calls `build_prompt(fields)` to produce the final string handed to
    gpt-image-2.
    """

    id: str
    """Stable machine identifier, e.g. 'drake', 'classic_6_panel'."""

    display_name: str
    """Human-readable name shown to subagents, e.g. 'Drake Pointing'."""

    story_shape: str
    """One-sentence description of the kind of news this template fits."""

    required_fields: list[str]
    """Field names a generator must fill, in canonical order."""

    field_descriptions: dict[str, str]
    """field_name → what to put in it (shown to the generator)."""

    example_fields: dict[str, str]
    """A worked example the generator can imitate. Should be plausible but not
    on-the-nose for the day's actual story."""

    build_prompt: Callable[[dict[str, str]], str] = field(repr=False)
    """fields → fully-formed image-gen prompt string."""

    def render_for_generator(self) -> str:
        """Format this template's metadata as a compact block a generator can read."""
        lines = [
            f"id: {self.id}",
            f"name: {self.display_name}",
            f"fits stories shaped like: {self.story_shape}",
            "fields:",
        ]
        for name in self.required_fields:
            desc = self.field_descriptions.get(name, "")
            lines.append(f"  - {name}: {desc}")
        if self.example_fields:
            lines.append("example:")
            for name, value in self.example_fields.items():
                lines.append(f"  {name}: {value!r}")
        return "\n".join(lines)
