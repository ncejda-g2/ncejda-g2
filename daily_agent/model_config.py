"""Model and serving settings for the direct LiteLLM text calls.

The newspaper uses one model end-to-end, but not one reasoning budget. Small,
repetitive classification tasks get a lower effort while editorial judgment and
comedy writing retain more room to think.
"""

from __future__ import annotations

import os


LUNA_MODEL = os.environ.get("NEWSPAPER_LUNA_MODEL", "openai/gpt-5.6-luna")
IMAGE_MODEL = "openai/gpt-image-2.5-flare"

# The configured LiteLLM deployment currently accepts xhigh as its highest
# reasoning setting (it rejects max). A global override is kept for quick local
# experiments; production defaults are intentionally role-specific.
_GLOBAL_REASONING_EFFORT = os.environ.get("NEWSPAPER_LUNA_REASONING_EFFORT")


def _effort(role: str, default: str) -> str:
    """Resolve a role-specific override, then the legacy global override."""

    return os.environ.get(
        f"NEWSPAPER_LUNA_{role.upper()}_REASONING_EFFORT",
        _GLOBAL_REASONING_EFFORT or default,
    )


# Cheap, schema-constrained filtering does not benefit much from maximum
# deliberation. Editorial selection and factual summaries need more judgment.
LUNA_SOURCE_CLASSIFICATION_REASONING_EFFORT = _effort(
    "source_classification", "medium"
)
LUNA_TRENDING_CLASSIFICATION_REASONING_EFFORT = _effort(
    "trending_classification", "low"
)
LUNA_TRENDING_REACTIONS_REASONING_EFFORT = _effort("trending_reactions", "low")
LUNA_EDITORIAL_REASONING_EFFORT = _effort("editorial", "high")
LUNA_SUMMARY_REASONING_EFFORT = _effort("summary", "high")

# The five independent pitches are the quality-sensitive creative stage.
LUNA_COMEDY_REASONING_EFFORT = _effort("comedy", "xhigh")
LUNA_CRITIC_REASONING_EFFORT = _effort("critic", "high")

# Keep standard serving explicitly. This is independent from reasoning effort:
# no Fast, Priority, Flex, or Pro mode is selected for the experiment.
LUNA_SERVICE_TIER = "default"
