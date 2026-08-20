"""Which bots the game can seat, and how to build one.

Lives under bots/ rather than dominoes/ because the good implementations are
here and they import from dominoes -- putting the registry the other way round
would make the import circular. main.py builds the seat list and hands it to
MatchState, which only ever needs objects with choose_move.
"""

import os
from typing import Callable, Optional

from dominoes.bots import BotBase

from .greedy_bot import GreedyBot
from .random_bot import RandomBot

CFR_POLICY_PATH = os.path.join(os.path.dirname(__file__), "cfr_policy.npz")


_policy_cache = None


def _make_cfr() -> BotBase:
    """Three seats share one loaded policy.

    CFRBot keeps per-instance RNG and hit counters, so the seats stay
    independent; only the read-only table is shared, which avoids parsing the
    same file once per seat.
    """
    global _policy_cache
    from cfr.policy import Policy

    from .cfr_bot import CFRBot

    if _policy_cache is None:
        _policy_cache = Policy.load(CFR_POLICY_PATH)
    return CFRBot(_policy_cache)


_BOTS: dict[str, tuple[str, Callable[[], BotBase]]] = {
    "greedy": ("Heuristic: counts suits, tracks the partner, chases bonuses", GreedyBot),
    "random": ("Plays a random legal move", RandomBot),
    "cfr": ("Trained by self-play with counterfactual regret minimisation", _make_cfr),
}


def cfr_available() -> bool:
    """True once a trained policy has been installed by cluster/fetch.sh."""
    return os.path.exists(CFR_POLICY_PATH)


def available() -> list[dict]:
    return [
        {
            "name": name,
            "description": description,
            "ready": name != "cfr" or cfr_available(),
        }
        for name, (description, _) in _BOTS.items()
    ]


def make(name: str) -> BotBase:
    """Build one bot by name. Raises KeyError for an unknown name and
    FileNotFoundError when the CFR policy has not been trained yet."""
    if name not in _BOTS:
        raise KeyError(name)
    if name == "cfr" and not cfr_available():
        raise FileNotFoundError(
            "No trained CFR policy. Train one (see cluster/README.md) and "
            "install it with cluster/fetch.sh."
        )
    return _BOTS[name][1]()


def seat_bots(name: str, human_seat: Optional[int] = 0) -> list[Optional[BotBase]]:
    """A four-seat list with `human_seat` left empty for the human."""
    return [None if i == human_seat else make(name) for i in range(4)]
