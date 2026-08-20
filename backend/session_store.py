"""In-memory match storage.

Bounded on purpose. Matches were previously kept in a plain dict for the life
of the process, so every game ever started stayed resident -- fine for a single
local session, a slow leak for anything left running. The least recently
touched match is dropped once the cap is reached; a client holding a dropped id
gets the same 404 it would get for any unknown match.
"""

from collections import OrderedDict
from uuid import uuid4

from dominoes.game import MatchState

MAX_MATCHES = 200

_store: "OrderedDict[str, MatchState]" = OrderedDict()


def create_match(match: MatchState) -> str:
    game_id = str(uuid4())
    _store[game_id] = match
    while len(_store) > MAX_MATCHES:
        _store.popitem(last=False)
    return game_id


def get_match(game_id: str) -> MatchState:
    match = _store[game_id]
    _store.move_to_end(game_id)  # keep games in play from ageing out
    return match


def save_match(game_id: str, match: MatchState) -> None:
    _store[game_id] = match
    _store.move_to_end(game_id)
