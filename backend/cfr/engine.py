"""A single hand of teams dominoes, stripped down for tree search.

The arena simulator allocates Domino objects and rebuilds a context dict on
every turn, which is fine at a few thousand hands a second but not inside a CFR
traversal that revisits the same subtree hundreds of times. This module models
the same rules with make/unmake on a flat state:

  * tiles are ints 0..27, hands are 28-bit masks
  * the layout is dropped entirely -- only the two open ends can ever affect
    legality or scoring, so the tile order carries no information
  * every mutation is reversible, so a traversal never copies the state

dominoes/rules.py stays the source of truth for the rules themselves; the
cross-check in tests/test_cfr_engine.py replays move-for-move against the arena
to prove the two agree.
"""

from typing import Optional

# ---------------------------------------------------------------- tile tables

TILES: list[tuple[int, int]] = [(a, b) for a in range(7) for b in range(a, 7)]
N_TILES = len(TILES)  # 28
TILE_ID: dict[tuple[int, int], int] = {}
for _i, (_a, _b) in enumerate(TILES):
    TILE_ID[(_a, _b)] = _i
    TILE_ID[(_b, _a)] = _i

TILE_A = tuple(a for a, _ in TILES)
TILE_B = tuple(b for _, b in TILES)
TILE_PIPS = tuple(a + b for a, b in TILES)
TILE_IS_DOUBLE = tuple(a == b for a, b in TILES)
TILE_MASK = tuple(1 << i for i in range(N_TILES))

# Tiles carrying each number, as a mask -- used for legality and for counting.
NUMBER_MASK = tuple(
    sum(1 << i for i, (a, b) in enumerate(TILES) if a == n or b == n) for n in range(7)
)
DOUBLE_MASK = sum(1 << i for i, d in enumerate(TILE_IS_DOUBLE) if d)

DOUBLE_SIX = TILE_ID[(6, 6)]
DOUBLE_BLANK = TILE_ID[(0, 0)]
DOUBLE_ID = tuple(TILE_ID[(n, n)] for n in range(7))

# Every number appears on 8 pip-slots across the set: seven tiles carry it and
# the double carries it twice.
SLOTS_PER_NUMBER = 8

# How many of number n each tile carries (2 for the double, else 1).
_TILE_NUM_COUNT = tuple(
    tuple((1 if a == n else 0) + (1 if b == n else 0) for n in range(7))
    for a, b in TILES
)

LEFT, RIGHT, START = 0, 1, 2


def mask_pips(mask: int) -> int:
    total = 0
    while mask:
        low = mask & -mask
        total += TILE_PIPS[low.bit_length() - 1]
        mask ^= low
    return total


def mask_tiles(mask: int) -> list[int]:
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def other_pip(tile: int, matched: int) -> int:
    """The pip left exposed after `tile` is joined onto a `matched` end."""
    a = TILE_A[tile]
    return TILE_B[tile] if a == matched else a


# ---------------------------------------------------------------------- state


class HandSim:
    """One hand in progress. Mutate with `apply`, rewind with `undo`."""

    __slots__ = (
        "hands",
        "left",
        "right",
        "passes",
        "cp",
        "voids",
        "seen",
        "starter",
        "forced",
        "last_tile",
        "ends_before",
        "history",
    )

    def __init__(self, hands: list[int], starter: int, forced_open: bool):
        self.hands = list(hands)
        self.left = -1
        self.right = -1
        self.passes = 0
        self.cp = starter
        self.starter = starter
        # Numbers each seat has proven void in, as 7-bit masks.
        self.voids = [0, 0, 0, 0]
        # Pip-slots of each number visible on the board, index 0..6.
        self.seen = [0] * 7
        self.forced = DOUBLE_SIX if forced_open else -1
        self.last_tile = -1
        self.ends_before: Optional[tuple[int, int]] = None
        self.history: list[tuple] = []

    # -- queries ---------------------------------------------------------

    def board_empty(self) -> bool:
        return self.left < 0

    def legal(self, seat: int) -> list[tuple[int, int]]:
        """Legal (tile, end) placements for `seat`, forced lead included."""
        hand = self.hands[seat]
        if self.left < 0:
            if self.forced >= 0 and hand & TILE_MASK[self.forced]:
                return [(self.forced, START)]
            return [(t, START) for t in mask_tiles(hand)]
        moves = []
        left, right = self.left, self.right
        for t in mask_tiles(hand):
            a, b = TILE_A[t], TILE_B[t]
            if a == left or b == left:
                moves.append((t, LEFT))
            if a == right or b == right:
                moves.append((t, RIGHT))
        return moves

    def is_terminal(self) -> bool:
        if self.passes >= 4:
            return True
        return any(h == 0 for h in self.hands)

    # -- mutation --------------------------------------------------------

    def apply(self, move: Optional[tuple[int, int]]) -> None:
        """Play `move`, or pass when it is None."""
        self.history.append(
            (
                self.left,
                self.right,
                self.passes,
                self.cp,
                self.forced,
                self.last_tile,
                self.ends_before,
                self.voids[self.cp],
            )
        )
        cp = self.cp
        if move is None:
            # A pass proves the seat holds neither open end.
            if self.left >= 0:
                self.voids[cp] |= (1 << self.left) | (1 << self.right)
            self.passes += 1
        else:
            tile, end = move
            self.ends_before = None if self.left < 0 else (self.left, self.right)
            if self.left < 0:
                self.left, self.right = TILE_A[tile], TILE_B[tile]
            elif end == LEFT:
                self.left = other_pip(tile, self.left)
            else:
                self.right = other_pip(tile, self.right)
            counts = _TILE_NUM_COUNT[tile]
            seen = self.seen
            for n in range(7):
                seen[n] += counts[n]
            self.hands[cp] &= ~TILE_MASK[tile]
            self.passes = 0
            self.forced = -1
            self.last_tile = tile
        self.cp = (cp + 1) & 3

    def undo(self, move: Optional[tuple[int, int]]) -> None:
        (
            self.left,
            self.right,
            self.passes,
            self.cp,
            self.forced,
            self.last_tile,
            self.ends_before,
            void,
        ) = self.history.pop()
        self.voids[self.cp] = void
        if move is not None:
            tile = move[0]
            self.hands[self.cp] |= TILE_MASK[tile]
            counts = _TILE_NUM_COUNT[tile]
            seen = self.seen
            for n in range(7):
                seen[n] -= counts[n]

    # -- settlement ------------------------------------------------------

    def payoff(self, capicu_bonus: int = 100, chuchazo_bonus: int = 100) -> tuple[int, int]:
        """Settle a finished hand. Returns (winning_team, points).

        Mirrors dominoes/scoring.compute_hand_scores_teams and
        dominoes/rules.resolve_blocked_hand.
        """
        pips = [mask_pips(h) for h in self.hands]
        blocked = self.passes >= 4
        if blocked:
            team0 = pips[0] + pips[2]
            team1 = pips[1] + pips[3]
            if team0 < team1:
                team = 0
            elif team1 < team0:
                team = 1
            else:
                # Tie goes to the team that closed the board. Four passes have
                # brought cp back to the first passer, so the last seat to play
                # a tile is the one before it.
                blocker = (self.cp - 1) & 3
                team = blocker & 1
            losers = (pips[1] + pips[3]) if team == 0 else (pips[0] + pips[2])
            return team, losers

        winner = (self.cp - 1) & 3
        team = winner & 1
        losers = (pips[1] + pips[3]) if team == 0 else (pips[0] + pips[2])
        bonus = 0
        if self.ends_before is not None and self.left == self.right:
            bonus += capicu_bonus
        if self.last_tile == DOUBLE_BLANK:
            bonus += chuchazo_bonus
        return team, losers + bonus

    def utility(self, team: int, capicu_bonus: int = 100, chuchazo_bonus: int = 100) -> int:
        """Signed points from `team`'s point of view."""
        winning_team, points = self.payoff(capicu_bonus, chuchazo_bonus)
        return points if winning_team == team else -points


# ------------------------------------------------------------------- dealing


def deal(rng) -> tuple[list[int], int]:
    """Deal all 28 tiles. Returns (hands as masks, double-six holder)."""
    order = list(range(N_TILES))
    rng.shuffle(order)
    hands = [0, 0, 0, 0]
    for i, tile in enumerate(order):
        hands[i & 3] |= TILE_MASK[tile]
    holder = next(s for s in range(4) if hands[s] & TILE_MASK[DOUBLE_SIX])
    return hands, holder


def new_hand(rng, starter: Optional[int] = None, forced_open: bool = True) -> HandSim:
    """A fresh hand. Defaults to the opening hand of a match: the double-six
    holder leads and must play the 6-6."""
    hands, holder = deal(rng)
    if forced_open or starter is None:
        return HandSim(hands, holder, forced_open=forced_open)
    return HandSim(hands, starter, forced_open=False)
