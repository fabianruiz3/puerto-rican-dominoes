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


def _make_pimc() -> BotBase:
    from .pimc_bot import PIMCBot

    return PIMCBot(worlds=PIMC_WORLDS)


# How many worlds the determinizing bot samples per turn. Twelve costs a few
# milliseconds a move and is well past the point of diminishing returns.
PIMC_WORLDS = 12

_BOTS: dict[str, tuple[str, Callable[[], BotBase]]] = {
    "greedy": ("Heuristic: counts suits, tracks the partner, chases bonuses", GreedyBot),
    "random": ("Plays a random legal move", RandomBot),
    "cfr": ("Trained by self-play with counterfactual regret minimisation", _make_cfr),
    "pimc": (
        "Samples the hands it cannot see, solves each, and plays the consensus",
        _make_pimc,
    ),
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


PARTNER_SEAT_OF = {0: 2, 1: 3, 2: 0, 3: 1}


def seat_bots(
    opponent: str,
    partner: Optional[str] = None,
    human_seat: Optional[int] = 0,
) -> list[Optional[BotBase]]:
    """A four-seat list with `human_seat` left empty.

    Seats pair 0+2 against 1+3, so `partner` fills the seat across from the
    human and `opponent` fills the other two. `partner` defaults to the same
    bot as the opponents. In FFA there are no teams, and the partner slot is
    simply the seat opposite.
    """
    if partner is None:
        partner = opponent
    mate = PARTNER_SEAT_OF[human_seat] if human_seat is not None else None
    seats: list[Optional[BotBase]] = []
    for i in range(4):
        if i == human_seat:
            seats.append(None)
        elif i == mate:
            seats.append(make(partner))
        else:
            seats.append(make(opponent))
    return seats
