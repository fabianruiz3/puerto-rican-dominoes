"""The view of a hand that a bot is allowed to see.

BotContext is what gets handed to BotBase.choose_move as `context`. It is a
Mapping, so `context["board"]` and `context.get("capicu_bonus", 0)` keep
working for bots written against the old dict, while `context.board` matches
the attribute style documented in the in-app Bot API panel.

Everything here is public information -- the board, who played what, who
passed on what, how many tiles each player is holding. No hidden hands.
"""

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Optional

from .types import Domino, MatchConfig, GameMode


@dataclass(frozen=True)
class BotContext(Mapping):
    player_id: int
    mode: str
    teammate_index: Optional[int]
    board: list[Domino]
    ends: Optional[tuple[int, int]]
    hand_counts: list[int]
    pass_counts: list[int]
    known_voids: list[list[int]]
    played_numbers: dict[int, int]
    teammate_played_numbers: dict[int, int]
    opponent_played_numbers: dict[int, int]
    move_history: list[dict]
    capicu_bonus: int
    chuchazo_bonus: int
    forced_tile: Optional[Domino] = None

    @property
    def player_index(self) -> int:
        """Back-compat alias for player_id."""
        return self.player_id

    def __getitem__(self, key):
        if key == "player_index":
            return self.player_id
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key) from None

    def __iter__(self):
        yield from (f.name for f in fields(self))
        yield "player_index"

    def __len__(self) -> int:
        return len(fields(self)) + 1


def build_bot_context(
    player_index: int,
    config: MatchConfig,
    board: list[Domino],
    ends: Optional[tuple[int, int]],
    hand_counts: list[int],
    move_history: list[dict],
    forced_tile: Optional[Domino] = None,
) -> BotContext:
    """Assemble the public view of the hand from `player_index`'s seat.

    `move_history` entries are {"player", "tile", "end", "ends"} where "tile" is
    None for a pass and "ends" is the board state the player faced on that turn.
    A pass against ends (L, R) proves the passer holds no L and no R, which is
    the main inference signal in dominoes -- that is what known_voids records.
    """
    teams = config.mode == GameMode.TEAMS
    teammate = (player_index + 2) % 4 if teams else None

    played_numbers = {i: 0 for i in range(7)}
    teammate_played = {i: 0 for i in range(7)}
    opponent_played = {i: 0 for i in range(7)}
    pass_counts = [0, 0, 0, 0]
    voids: list[set[int]] = [set(), set(), set(), set()]

    for move in move_history:
        actor = move["player"]
        tile = move["tile"]
        if tile is None:
            pass_counts[actor] += 1
            move_ends = move.get("ends")
            if move_ends is not None:
                voids[actor].update(move_ends)
            continue
        a, b = tile
        played_numbers[a] += 1
        played_numbers[b] += 1
        if actor == player_index:
            continue
        bucket = teammate_played if actor == teammate else opponent_played
        bucket[a] += 1
        bucket[b] += 1

    return BotContext(
        player_id=player_index,
        mode=config.mode.name,
        teammate_index=teammate,
        board=list(board),
        ends=ends,
        hand_counts=list(hand_counts),
        pass_counts=pass_counts,
        known_voids=[sorted(v) for v in voids],
        played_numbers=played_numbers,
        teammate_played_numbers=teammate_played,
        opponent_played_numbers=opponent_played,
        move_history=list(move_history),
        capicu_bonus=config.capicu_bonus,
        chuchazo_bonus=config.chuchazo_bonus,
        forced_tile=forced_tile,
    )
