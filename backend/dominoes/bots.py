from typing import Optional
from .types import Domino
from .rules import legal_moves_for_hand

class BotBase:

    def choose_move(self, hand: list[Domino], ends) -> Optional[tuple[Domino, str]]:
        raise NotImplementedError

class GreedyBot(BotBase):

    def choose_move(self, hand: list[Domino], ends):
        legal = legal_moves_for_hand(hand, ends)
        if not legal:
            return None

        def score(move):
            tile, end = move
            s = tile.pips()
            if tile.is_double():
                s -= 0.5
            return s
        return max(legal, key=score)