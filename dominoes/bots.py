from .types import Domino, MatchCongig
from .rules import legal_moves

class BotBase:
    def choose_move(
        self,
        handList: list[Domino],
        board_ends: tuple[int, int] | None
    ) -> Domino | None:
        """
        Choose a move for the bot.
        Returns the chosen Domino tile, or None to pass.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")
    

class GreedyBot(BotBase):
    def choose_move(self, handList, board_ends):
        legal = legal_moves(handList, board_ends)
        if not legal:
            return None  # Pass if no legal
        
        def score(move):
            tile, end = move
            s = tile.pips()
            if tile.is_double():
                s += 5  # Bonus for doubles
            return s
        
        best_move = max(legal, key=score)
        return best_move