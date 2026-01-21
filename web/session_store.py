from uuid import uuid4
from dominoes.game import MatchState

_store: dict[str, MatchState] = {}


def create_match(match: MatchState) -> str:
    game_id = str(uuid4())
    _store[game_id] = match
    return game_id


def get_match(game_id: str) -> MatchState:
    return _store[game_id]


def save_match(game_id: str, match: MatchState) -> None:
    _store[game_id] = match