from typing import Optional
from .types import Domino, GameMode

# Standard Puerto Rican opening: the first hand of a match is opened by whoever
# holds the double six, and they must lead it. Later hands are opened freely by
# whoever earned the start (see next_starter).
OPENING_TILE = Domino(6, 6)


def legal_moves_for_hand(
    hand: list[Domino],
    ends: Optional[tuple[int, int]],
    forced_tile: Optional[Domino] = None,
) -> list[tuple[Domino, str]]:
    """Every legal (tile, end) placement for `hand` against board `ends`.

    `forced_tile` constrains the opening lead only. It is ignored once the board
    has ends, and ignored if the holder somehow does not have the tile.
    """
    if ends is None:
        if forced_tile is not None and forced_tile in hand:
            return [(forced_tile, "start")]
        return [(tile, "start") for tile in hand]
    left, right = ends
    legal = []
    for tile in hand:
        a, b = (tile.a, tile.b)
        if a == left or b == left:
            legal.append((tile, "left"))
        if a == right or b == right:
            legal.append((tile, "right"))
    return legal


def resulting_ends(
    ends: Optional[tuple[int, int]], tile: Domino, end: str
) -> tuple[int, int]:
    """The board ends after placing `tile` on `end`."""
    if ends is None or end == "start":
        return (tile.a, tile.b)
    left, right = ends
    if end == "left":
        return (tile.b, right) if tile.a == left else (tile.a, right)
    return (left, tile.b) if tile.a == right else (left, tile.a)


def canonical_moves(
    hand: list[Domino],
    ends: Optional[tuple[int, int]],
    forced_tile: Optional[Domino] = None,
) -> list[tuple[Domino, str]]:
    """Legal moves with duplicates collapsed.

    legal_moves_for_hand reports a tile twice when it matches both ends, but the
    two placements are the same position whenever they leave the board in the
    same state up to reflection -- which is exactly when the ends are equal. A
    capicu tile played against unequal ends genuinely reaches two different
    boards, so both placements survive.
    """
    seen = set()
    out = []
    for tile, end in legal_moves_for_hand(hand, ends, forced_tile):
        key = (tile.a, tile.b, tuple(sorted(resulting_ends(ends, tile, end))))
        if key in seen:
            continue
        seen.add(key)
        out.append((tile, end))
    return out


def team_for_player(player_index: int) -> int:
    return 0 if player_index in (0, 2) else 1


def team_players(team: int) -> list[int]:
    return [0, 2] if team == 0 else [1, 3]


def resolve_blocked_hand(
    hands_pips: list[int], mode: GameMode, blocker: Optional[int]
) -> tuple[int, int]:
    """Settle a tranque. Returns (winner_index, winner_team).

    The tranque is won on pips: in TEAMS by the lower combined team total, in
    FFA by the individual low hand. `winner_index` is the player who won it on
    pips, which is also who opens the next hand.

    Ties go to the team of the player who closed the board -- the usual house
    rule, and the tie has to resolve somewhere deterministically.
    """
    if mode == GameMode.FFA:
        winner = min(range(4), key=lambda i: (hands_pips[i], i))
        return winner, team_for_player(winner)
    team0_pips = hands_pips[0] + hands_pips[2]
    team1_pips = hands_pips[1] + hands_pips[3]
    if team0_pips < team1_pips:
        team = 0
    elif team1_pips < team0_pips:
        team = 1
    else:
        team = team_for_player(blocker) if blocker is not None else 0
    winner = min(team_players(team), key=lambda i: (hands_pips[i], i))
    return winner, team


def next_starter(winner_index: int) -> int:
    """Who opens the next hand.

    Domino-out: the player who went out. Tranque: the player who won it on pips.
    resolve_blocked_hand already returns that player, so both cases are the same
    value and this exists to name the rule at the call sites.
    """
    return winner_index
