from .types import Domino, MatchConfig
from .rules import legal_moves

class BotBase:
    def choose_move(
        self,
        handList: list[Domino],
        board_ends: tuple[int, int] | None
    ) -> tuple[Domino | None, str | None]:
        """
        Choose a move for the bot.
        Returns a tuple of (tile, end) where end is 'left' or 'right', or (None, None) to pass.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")
    

class GreedyBot(BotBase):
    def choose_move(self, handList, board_ends):
        legal = legal_moves(handList, board_ends)
        if not legal:
            return None, None  # Pass if no legal moves
        
        def score(move):
            tile = move
            s = tile.pips()
            if tile.is_double():
                s += 5  # Bonus for doubles
            return s
        
        best_tile = max(legal, key=score)
        # Choose which end to play (default to 'right')
        return best_tile, 'right'