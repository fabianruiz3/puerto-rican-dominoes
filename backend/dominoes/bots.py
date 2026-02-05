from typing import List, Optional, Tuple
from .types import Domino
from .rules import legal_moves_for_hand


class BotBase:
    def choose_move(
        self,
        hand: List[Domino],
        ends,
    ) -> Optional[Tuple[Domino, str]]:
        raise NotImplementedError


class GreedyBot(BotBase):
    def choose_move(self, hand: List[Domino], ends):
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
