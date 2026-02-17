"""
Greedy Bot strategy that prioritizes high-pip tiles.

Slightly prefers non-double tiles. Use as a baseline bot.
"""
from dominoes.bots import BotBase
from dominoes.rules import legal_moves_for_hand


class GreedyBot(BotBase):
    def choose_move(self, hand, ends):
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
