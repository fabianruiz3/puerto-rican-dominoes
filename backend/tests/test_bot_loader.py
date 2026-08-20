"""Choosing the right class out of an uploaded bot file.

The loader used to take the first BotBase subclass in dir(), which is
alphabetical and blind to whether the class was defined in the file or
imported into it. A file importing GreedyBot to compare against therefore ran
GreedyBot, and the arena scored greedy against itself while reporting the
author's bot name.
"""

import pytest

from bots.bot_loader import load_bot_from_source
from dominoes.bots import BotBase
from dominoes.types import Domino

PREAMBLE = """
from dominoes.bots import BotBase
from dominoes.rules import legal_moves_for_hand
"""


def test_the_class_the_file_defines_wins_over_one_it_imported():
    src = PREAMBLE + """
from bots.greedy_bot import GreedyBot          # alphabetically first

class ZanyBot(BotBase):
    def choose_move(self, hand, ends, context=None):
        legal = legal_moves_for_hand(hand, ends)
        return legal[-1] if legal else None
"""
    bot = load_bot_from_source(src, "t1")
    assert type(bot).__name__ == "ZanyBot"


def test_a_single_defined_class_loads_whatever_it_is_called():
    src = PREAMBLE + """
class Aardvark(BotBase):
    def choose_move(self, hand, ends, context=None):
        return None
"""
    assert type(load_bot_from_source(src, "t2")).__name__ == "Aardvark"


def test_an_explicit_BOT_assignment_settles_it():
    src = PREAMBLE + """
class First(BotBase):
    def choose_move(self, hand, ends, context=None):
        return None

class Second(BotBase):
    def choose_move(self, hand, ends, context=None):
        return None

BOT = Second
"""
    assert type(load_bot_from_source(src, "t3")).__name__ == "Second"


def test_two_defined_classes_ask_for_BOT_rather_than_guessing():
    src = PREAMBLE + """
class Alpha(BotBase):
    def choose_move(self, hand, ends, context=None):
        return None

class Beta(BotBase):
    def choose_move(self, hand, ends, context=None):
        return None
"""
    with pytest.raises(ValueError, match="BOT = Beta"):
        load_bot_from_source(src, "t4")


def test_a_file_with_only_imported_bots_is_rejected_clearly():
    src = "from bots.greedy_bot import GreedyBot\n"
    with pytest.raises(ValueError, match="imported from elsewhere do not count"):
        load_bot_from_source(src, "t5")


def test_BOT_pointing_at_something_that_is_not_a_bot_is_rejected():
    src = PREAMBLE + """
class Fine(BotBase):
    def choose_move(self, hand, ends, context=None):
        return None

BOT = 42
"""
    with pytest.raises(ValueError, match="must be a class inheriting from BotBase"):
        load_bot_from_source(src, "t6")


def test_the_loaded_bot_actually_plays():
    src = PREAMBLE + """
class LastLegal(BotBase):
    def choose_move(self, hand, ends, context=None):
        legal = legal_moves_for_hand(hand, ends)
        return legal[-1] if legal else None
"""
    bot = load_bot_from_source(src, "t7")
    assert isinstance(bot, BotBase)
    move = bot.choose_move([Domino(3, 4), Domino(5, 5)], (5, 2))
    assert move == (Domino(5, 5), "left")


def test_the_temporary_module_does_not_linger_in_sys_modules():
    import sys

    before = set(sys.modules)
    load_bot_from_source(PREAMBLE + """
class Tidy(BotBase):
    def choose_move(self, hand, ends, context=None):
        return None
""", "t8")
    assert not (set(sys.modules) - before), "the loader leaked a module"


def test_a_syntax_error_in_the_upload_surfaces_rather_than_being_swallowed():
    with pytest.raises(SyntaxError):
        load_bot_from_source("class Broken(:\n", "t9")
