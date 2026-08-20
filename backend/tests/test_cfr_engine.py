"""Prove the CFR simulator settles hands exactly like the shipped engine.

CFR optimises against cfr/engine.py. If that engine drifts from
dominoes/rules.py the resulting policy is tuned for a different game, and the
drift would be invisible -- the bot would just quietly underperform. So every
hand is replayed move-for-move through both and the settlements compared.
"""

import random

import pytest

from cfr.engine import (
    LEFT,
    RIGHT,
    START,
    TILES,
    HandSim,
    mask_tiles,
    new_hand,
)
from dominoes.rules import (
    OPENING_TILE,
    legal_moves_for_hand,
    resolve_blocked_hand,
    resulting_ends,
)
from dominoes.scoring import compute_hand_scores_teams
from dominoes.types import Domino, GameMode, MatchConfig

CONFIG = MatchConfig(target_points=200, mode=GameMode.TEAMS)


class Reference:
    """The same hand played through the shipped rules modules."""

    def __init__(self, hands, starter, forced_open):
        self.hands = [list(h) for h in hands]
        self.ends = None
        self.ends_before = None
        self.passes = 0
        self.cp = starter
        self.forced = OPENING_TILE if forced_open else None
        self.last_tile = None

    def legal(self):
        return legal_moves_for_hand(
            self.hands[self.cp], self.ends, self.forced if self.ends is None else None
        )

    def play(self, move):
        if move is None:
            self.passes += 1
        else:
            tile, end = move
            self.ends_before = self.ends
            self.ends = resulting_ends(self.ends, tile, end)
            self.hands[self.cp].remove(tile)
            self.passes = 0
            self.forced = None
            self.last_tile = tile
        self.cp = (self.cp + 1) % 4

    def settle(self):
        pips = [sum(t.pips() for t in h) for h in self.hands]
        blocked = self.passes >= 4
        if blocked:
            blocker = (self.cp - 1) % 4
            winner, _ = resolve_blocked_hand(pips, GameMode.TEAMS, blocker)
        else:
            winner = (self.cp - 1) % 4
        deltas = compute_hand_scores_teams(
            config=CONFIG,
            hands_pips=pips,
            winner_index=winner,
            winning_tile=self.last_tile,
            blocked=blocked,
            ends_before=self.ends_before,
            ends_after=self.ends,
        )
        team = 0 if winner in (0, 2) else 1
        return team, deltas[winner]


def to_domino(tile_id):
    a, b = TILES[tile_id]
    return Domino(a, b)


def sim_move_to_ref(sim, move):
    if move is None:
        return None
    tile, end = move
    label = "start" if end == START else ("left" if end == LEFT else "right")
    return (to_domino(tile), label)


@pytest.mark.parametrize("forced_open", [True, False])
def test_the_two_engines_settle_every_hand_identically(forced_open):
    rng = random.Random(4242)
    picker = random.Random(99)
    blocked_seen = 0
    capicu_seen = 0
    for _ in range(400):
        sim = new_hand(rng, starter=rng.randrange(4), forced_open=forced_open)
        ref = Reference(
            [[to_domino(t) for t in mask_tiles(h)] for h in sim.hands],
            sim.cp,
            forced_open,
        )
        while not sim.is_terminal():
            moves = sim.legal(sim.cp)
            move = picker.choice(moves) if moves else None
            ref_move = sim_move_to_ref(sim, move)
            # Both engines must agree on what is legal before either plays.
            assert (ref_move is None) == (move is None)
            if ref_move is not None:
                assert ref_move in ref.legal()
            assert len(ref.legal()) == len(moves)
            sim.apply(move)
            ref.play(ref_move)
        assert sim.payoff() == ref.settle()
        if sim.passes >= 4:
            blocked_seen += 1
        elif sim.left == sim.right and sim.ends_before is not None:
            capicu_seen += 1
    assert blocked_seen > 0, "corpus never produced a tranque"
    assert capicu_seen > 0, "corpus never produced a capicu"


def test_undo_restores_the_state_exactly():
    rng = random.Random(7)
    picker = random.Random(8)
    for _ in range(50):
        sim = new_hand(rng)
        trail = []
        while not sim.is_terminal():
            snapshot = (
                list(sim.hands),
                sim.left,
                sim.right,
                sim.passes,
                sim.cp,
                sim.forced,
                sim.last_tile,
                sim.ends_before,
                list(sim.voids),
                list(sim.seen),
            )
            moves = sim.legal(sim.cp)
            move = picker.choice(moves) if moves else None
            sim.apply(move)
            trail.append((move, snapshot))
        while trail:
            move, snapshot = trail.pop()
            sim.undo(move)
            assert (
                list(sim.hands),
                sim.left,
                sim.right,
                sim.passes,
                sim.cp,
                sim.forced,
                sim.last_tile,
                sim.ends_before,
                list(sim.voids),
                list(sim.seen),
            ) == snapshot


def test_the_utility_of_a_hand_is_zero_sum_between_the_teams():
    rng = random.Random(11)
    picker = random.Random(12)
    for _ in range(200):
        sim = new_hand(rng)
        while not sim.is_terminal():
            moves = sim.legal(sim.cp)
            sim.apply(picker.choice(moves) if moves else None)
        assert sim.utility(0) == -sim.utility(1)


def test_a_pass_marks_the_seat_void_in_both_open_ends():
    hands = [0, 0, 0, 0]
    sim = HandSim(hands, starter=0, forced_open=False)
    sim.left, sim.right = 3, 5
    sim.cp = 2
    sim.apply(None)
    assert sim.voids[2] == (1 << 3) | (1 << 5)


def test_seen_counts_track_the_pips_on_the_board():
    rng = random.Random(3)
    sim = new_hand(rng)
    sim.apply(sim.legal(sim.cp)[0])  # the 6-6 contributes two pip-slots of six
    assert sim.seen[6] == 2
    assert sum(sim.seen) == 2
    # Every later tile adds exactly two more pip-slots across the seven numbers.
    played = 1
    while not sim.is_terminal():
        moves = sim.legal(sim.cp)
        sim.apply(moves[0] if moves else None)
        if moves:
            played += 1
        assert sum(sim.seen) == 2 * played
