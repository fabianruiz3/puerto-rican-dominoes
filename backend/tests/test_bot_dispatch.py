"""Calling a bot's choose_move.

Both the game loop and the arena used to call choose_move with three arguments
and retry with two on TypeError, to support bots written against the older
two-argument signature. That retry cannot tell "this bot takes two arguments"
from "this bot raised TypeError in its own code", so a bot with a type error
inside it was quietly run a second time without its context: the author's logic
executed twice, and the failure surfaced from the wrong call.
"""

import pytest

from dominoes.bots import BotBase, accepts_context, call_bot
from dominoes.rules import legal_moves_for_hand
from dominoes.types import Domino

HAND = [Domino(1, 2), Domino(3, 3)]
ENDS = (1, 3)


class ThreeArg(BotBase):
    def choose_move(self, hand, ends, context=None):
        return ("three", context)


class TwoArg(BotBase):
    def choose_move(self, hand, ends):
        return ("two", None)


class VarArgs(BotBase):
    def choose_move(self, *args, **kwargs):
        return ("varargs", len(args))


class KeywordOnly(BotBase):
    def choose_move(self, hand, ends, **kwargs):
        return ("kwargs", kwargs.get("context"))


def test_a_three_argument_bot_receives_the_context():
    assert call_bot(ThreeArg(), HAND, ENDS, {"player_id": 2}) == (
        "three",
        {"player_id": 2},
    )


def test_a_two_argument_bot_is_called_with_two_arguments():
    assert call_bot(TwoArg(), HAND, ENDS, {"player_id": 2}) == ("two", None)


@pytest.mark.parametrize("cls", [ThreeArg, VarArgs, KeywordOnly])
def test_signatures_that_can_take_a_context_are_detected(cls):
    assert accepts_context(cls()) is True


def test_a_two_argument_signature_is_detected():
    assert accepts_context(TwoArg()) is False


def test_a_type_error_inside_the_bot_is_raised_once_not_retried():
    calls = []

    class Buggy(BotBase):
        def choose_move(self, hand, ends, context=None):
            calls.append(context)
            raise TypeError("a type error in the author's own code")

    with pytest.raises(TypeError, match="author's own code"):
        call_bot(Buggy(), HAND, ENDS, {"player_id": 0})
    assert len(calls) == 1, "the bot was run a second time"


def test_a_bot_with_side_effects_runs_exactly_once():
    plays = []

    class Counter(BotBase):
        def choose_move(self, hand, ends, context=None):
            plays.append(1)
            return legal_moves_for_hand(hand, ends)[0]

    bot = Counter()
    for _ in range(5):
        call_bot(bot, HAND, ENDS, {})
    assert len(plays) == 5


def test_the_signature_is_inspected_once_per_class():
    from dominoes.bots import _ACCEPTS_CONTEXT

    _ACCEPTS_CONTEXT.pop(ThreeArg, None)
    accepts_context(ThreeArg())
    assert ThreeArg in _ACCEPTS_CONTEXT
    accepts_context(ThreeArg())  # cached; must not re-inspect or change answer
    assert _ACCEPTS_CONTEXT[ThreeArg] is True
