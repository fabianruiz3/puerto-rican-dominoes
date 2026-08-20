"""The arena runs uploaded code, so it has to survive whatever comes back.

Two things matter beyond not crashing. A bot that never plays a legal move
should not be able to corrupt the board or manufacture a tranque by refusing
to play. And when a bot is not really running -- which is what a wrongly
loaded class looks like -- that should be visible rather than scored as a
normal match.
"""

import pytest

from bots.arena import run_arena
from bots.greedy_bot import GreedyBot
from bots.random_bot import RandomBot
from dominoes.bots import BotBase, coerce_move
from dominoes.rules import legal_moves_for_hand
from dominoes.types import Domino

HAND = [Domino(1, 2), Domino(3, 3)]
LEGAL = legal_moves_for_hand(HAND, (1, 3))


def bot_returning(value):
    class Rigged(BotBase):
        def choose_move(self, hand, ends, context=None):
            return value(hand) if callable(value) else value

    return Rigged()


@pytest.mark.parametrize(
    "value",
    [
        5,  # not iterable at all
        "left",  # a string is iterable, and wrong
        3.5,
        (Domino(6, 6), "left"),  # a tile that is not in hand
        lambda hand: (hand[0], "middle"),  # no such end
        lambda hand: (hand[0], "left", 99),  # wrong arity
        object(),
    ],
)
def test_the_arena_survives_whatever_a_bot_returns(value):
    result = run_arena(bot_returning(value), GreedyBot(), num_matches=3, target_points=100, seed=1)
    assert result["team_a_wins"] + result["team_b_wins"] == 3
    assert result["bot_a_bad_returns"] > 0, "a misbehaving bot went unreported"


def test_a_bot_that_never_plays_cannot_manufacture_a_tranque():
    """Returning None is a pass, and a pass is only legal with nothing to
    play. Without that check a bot could refuse to move and block every hand."""
    refuser = bot_returning(None)
    result = run_arena(refuser, GreedyBot(), num_matches=20, target_points=200, seed=1)
    assert result["bot_a_bad_returns"] > 0
    assert result["blocked_hand_rate"] < 0.6, "refusing to play still blocked the game"


def test_well_behaved_bots_are_never_flagged():
    result = run_arena(GreedyBot(), RandomBot(), num_matches=20, target_points=200, seed=1)
    assert result["bot_a_bad_returns"] == 0
    assert result["bot_b_bad_returns"] == 0


def test_the_forced_opening_lead_is_not_counted_against_a_bot():
    """The 6-6 lead is the harness's rule. A bot that does not know about it
    gets overruled, but that is not its mistake."""

    class IgnoresForcedLead(BotBase):
        def choose_move(self, hand, ends, context=None):
            legal = legal_moves_for_hand(hand, ends)  # no forced_tile
            return legal[0] if legal else None

    result = run_arena(IgnoresForcedLead(), GreedyBot(), num_matches=15, target_points=200, seed=4)
    assert result["bot_a_bad_returns"] == 0


def test_the_built_in_bots_honour_the_forced_lead():
    for bot in (GreedyBot(), RandomBot()):
        move = bot.choose_move(
            [Domino(6, 6), Domino(3, 4), Domino(0, 0)],
            None,
            {"forced_tile": Domino(6, 6)},
        )
        assert move == (Domino(6, 6), "start"), type(bot).__name__


# ------------------------------------------------------------- coerce_move


def test_coerce_move_passes_a_legal_move_through_untouched():
    assert coerce_move(LEGAL[0], LEGAL) == (LEGAL[0], None)


def test_coerce_move_allows_a_pass_only_with_nothing_to_play():
    assert coerce_move(None, []) == (None, None)
    move, complaint = coerce_move(None, LEGAL)
    assert move == LEGAL[0]
    assert "legal moves available" in complaint


def test_coerce_move_clamps_an_illegal_move_and_says_so():
    move, complaint = coerce_move((Domino(6, 6), "left"), LEGAL)
    assert move == LEGAL[0]
    assert "illegal move" in complaint


def test_coerce_move_reports_the_type_it_could_not_use():
    move, complaint = coerce_move(7, LEGAL)
    assert move == LEGAL[0]
    assert "returned int" in complaint


def test_coerce_move_has_nothing_to_fall_back_on_when_nothing_is_legal():
    move, complaint = coerce_move(7, [])
    assert move is None
    assert complaint is not None
