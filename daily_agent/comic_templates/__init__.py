"""Comic template registry — every comic format the daily agent can pick from.

Add a new template by:
  1. Creating a new module here that exports a `TEMPLATE: MemeTemplate`.
  2. Importing it below and adding it to `_ALL`.
The generator/critic pipeline reads `REGISTRY` and never references templates
by hardcoded id elsewhere.
"""

from ._types import MemeTemplate

# meme templates (13)
from .always_has_been import TEMPLATE as ALWAYS_HAS_BEEN
from .anakin_padme import TEMPLATE as ANAKIN_PADME
from .buff_doge_cheems import TEMPLATE as BUFF_DOGE_CHEEMS
from .disaster_girl import TEMPLATE as DISASTER_GIRL
from .drake import TEMPLATE as DRAKE
from .expanding_brain import TEMPLATE as EXPANDING_BRAIN
from .one_does_not_simply import TEMPLATE as ONE_DOES_NOT_SIMPLY
from .roll_safe import TEMPLATE as ROLL_SAFE
from .same_picture import TEMPLATE as SAME_PICTURE
from .stonks import TEMPLATE as STONKS
from .this_is_fine import TEMPLATE as THIS_IS_FINE
from .trade_offer import TEMPLATE as TRADE_OFFER
from .two_buttons import TEMPLATE as TWO_BUTTONS

# classic 6-panel (1)
from .classic_6_panel import TEMPLATE as CLASSIC_6_PANEL


_ALL: list[MemeTemplate] = [
    CLASSIC_6_PANEL,
    DRAKE,
    TWO_BUTTONS,
    THIS_IS_FINE,
    SAME_PICTURE,
    EXPANDING_BRAIN,
    ALWAYS_HAS_BEEN,
    TRADE_OFFER,
    DISASTER_GIRL,
    ANAKIN_PADME,
    BUFF_DOGE_CHEEMS,
    STONKS,
    ROLL_SAFE,
    ONE_DOES_NOT_SIMPLY,
]


REGISTRY: dict[str, MemeTemplate] = {tpl.id: tpl for tpl in _ALL}
"""All available comic templates, keyed by id."""


__all__ = [
    "MemeTemplate",
    "REGISTRY",
]
