import random
from dominoes.bots import BotBase
from dominoes.rules import legal_moves_for_hand

class RandomBot(BotBase):

    def choose_move(self, hand, ends):
        legal = legal_moves_for_hand(hand, ends)
        if not legal:
            return None
        return random.choice(legal)