"""Run the real traversal on games whose solutions are known in closed form.

A subtly wrong CFR does not crash -- it produces a mediocre bot, and there is
no way to tell that apart from an abstraction that needs more training. So the
same traverse() that trains the dominoes policy is pointed at Rock-Paper-
Scissors (equilibrium: uniform) and Kuhn poker (equilibrium known exactly,
game value -1/18) before any cluster time is spent.
"""

import itertools
import random

import pytest

from cfr.abstraction import slot_key
from cfr.mccfr import GameSpec, RegretTable, average_strategy, regret_matching, traverse

# --------------------------------------------------------- rock paper scissors

RPS_PAYOFF = [[0, -1, 1], [1, 0, -1], [-1, 1, 0]]  # row = player 0's throw


class RPS:
    """Simultaneous play modelled sequentially: seat 1's key ignores the
    history, so it never learns what seat 0 threw."""

    def __init__(self):
        self.moves = []
        self.cp = 0

    def is_terminal(self):
        return len(self.moves) == 2

    def apply(self, move):
        self.moves.append(move)
        self.cp = len(self.moves) & 1

    def undo(self, move):
        self.moves.pop()
        self.cp = len(self.moves) & 1


RPS_SPEC = GameSpec(
    actions=lambda g, seat: ([0, 1, 2], [[0], [1], [2]]),
    key=lambda g, seat: seat,
    utility=lambda g, seat: (
        RPS_PAYOFF[g.moves[0]][g.moves[1]] * (1 if seat == 0 else -1)
    ),
)


def test_rock_paper_scissors_converges_to_the_uniform_equilibrium():
    table = RegretTable()
    rng = random.Random(0)
    for i in range(1, 60001):
        for traverser in (0, 1):
            traverse(RPS(), traverser, table, rng, RPS_SPEC, slot_key, weight=i)
    avg = average_strategy(table)
    for seat in (0, 1):
        probs = avg[seat]
        assert len(probs) == 3
        for action in (0, 1, 2):
            assert probs[action] == pytest.approx(1 / 3, abs=0.03), (seat, probs)


def test_regret_matching_is_proportional_to_positive_regret():
    from array import array

    regret = array("d", [3.0, 1.0, -5.0])
    assert regret_matching(regret, [0, 1, 2]) == pytest.approx([0.75, 0.25, 0.0])
    assert regret_matching(array("d", [-1.0, -2.0]), [0, 1]) == pytest.approx([0.5, 0.5])


# ------------------------------------------------------------------ kuhn poker

JACK, QUEEN, KING = 0, 1, 2
CHECK, BET = 0, 1
# history -> (is_terminal, payoff to player 0 in units, or None for showdown)
KUHN_TERMINAL = {
    (CHECK, CHECK): None,  # showdown for 1
    (BET, CHECK): 1,  # player 1 folds
    (BET, BET): None,  # showdown for 2
    (CHECK, BET, CHECK): -1,  # player 0 folds
    (CHECK, BET, BET): None,  # showdown for 2
}
KUHN_POT = {(CHECK, CHECK): 1, (BET, BET): 2, (CHECK, BET, BET): 2}


class Kuhn:
    def __init__(self, cards):
        self.cards = cards
        self.history = []
        self.cp = 0

    def is_terminal(self):
        return tuple(self.history) in KUHN_TERMINAL

    def apply(self, move):
        self.history.append(move)
        self.cp = len(self.history) & 1

    def undo(self, move):
        self.history.pop()
        self.cp = len(self.history) & 1

    def payoff_to_p0(self):
        h = tuple(self.history)
        fixed = KUHN_TERMINAL[h]
        if fixed is not None:
            return fixed
        stake = KUHN_POT[h]
        return stake if self.cards[0] > self.cards[1] else -stake


KUHN_SPEC = GameSpec(
    actions=lambda g, seat: ([CHECK, BET], [[CHECK], [BET]]),
    key=lambda g, seat: g.cards[seat] * 16 + _history_code(g.history),
    utility=lambda g, seat: g.payoff_to_p0() * (1 if seat == 0 else -1),
)


def _history_code(history):
    code = 1
    for move in history:
        code = code * 2 + move
    return code


def kuhn_key(card, history):
    return card * 16 + _history_code(list(history))


@pytest.fixture(scope="module")
def kuhn_average():
    table = RegretTable()
    rng = random.Random(11)
    deals = list(itertools.permutations([JACK, QUEEN, KING], 2))
    for i in range(1, 120001):
        cards = deals[rng.randrange(6)]
        for traverser in (0, 1):
            traverse(Kuhn(cards), traverser, table, rng, KUHN_SPEC, slot_key, weight=i)
    return average_strategy(table)


def prob(avg, card, history, action):
    return avg[kuhn_key(card, history)].get(action, 0.0)


def test_kuhn_player_one_folds_a_jack_to_a_bet(kuhn_average):
    assert prob(kuhn_average, JACK, (BET,), BET) < 0.05


def test_kuhn_player_one_always_calls_a_king(kuhn_average):
    assert prob(kuhn_average, KING, (BET,), BET) > 0.95


def test_kuhn_player_one_calls_a_queen_one_time_in_three(kuhn_average):
    assert prob(kuhn_average, QUEEN, (BET,), BET) == pytest.approx(1 / 3, abs=0.06)


def test_kuhn_player_one_bluffs_a_jack_one_time_in_three(kuhn_average):
    assert prob(kuhn_average, JACK, (CHECK,), BET) == pytest.approx(1 / 3, abs=0.06)


def test_kuhn_player_one_always_bets_a_king_behind_a_check(kuhn_average):
    assert prob(kuhn_average, KING, (CHECK,), BET) > 0.95


def test_kuhn_player_zero_never_bets_a_queen_first(kuhn_average):
    assert prob(kuhn_average, QUEEN, (), BET) < 0.05


def test_kuhn_player_zero_bluffs_the_jack_three_times_less_than_it_bets_the_king(
    kuhn_average,
):
    """Kuhn's equilibria form a one-parameter family: P0 bets the jack with
    probability a in [0, 1/3] and the king with 3a. The ratio is the invariant.
    """
    jack = prob(kuhn_average, JACK, (), BET)
    king = prob(kuhn_average, KING, (), BET)
    assert jack < 1 / 3 + 0.06
    assert king == pytest.approx(3 * jack, abs=0.10)


def exact_value(avg):
    """Expected payoff to player 0 under the averaged profile, by enumeration."""

    def walk(cards, history):
        game = Kuhn(cards)
        game.history = list(history)
        if game.is_terminal():
            return game.payoff_to_p0()
        seat = len(history) & 1
        probs = avg[kuhn_key(cards[seat], history)]
        total = 0.0
        for action in (CHECK, BET):
            p = probs.get(action, 0.0)
            if p:
                total += p * walk(cards, tuple(history) + (action,))
        return total

    deals = list(itertools.permutations([JACK, QUEEN, KING], 2))
    return sum(walk(d, ()) for d in deals) / len(deals)


def test_kuhn_game_value_matches_the_analytic_minus_one_eighteenth(kuhn_average):
    assert exact_value(kuhn_average) == pytest.approx(-1 / 18, abs=0.012)
