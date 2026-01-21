from typing import Optional
from .types import Domino

def legal_moves(hand: list[Domino], board_ends: Optional[tuple[int, int]]) -> list[Domino]:
    """Determine the legal moves a player can make given their hand and the current board ends."""
    if board_ends is None:
        return hand  # Any tile can be played if the board is empty
    left_end, right_end = board_ends
    legal = []
    for tile in hand:
        if tile.a == left_end or tile.b == left_end or tile.a == right_end or tile.b == right_end:
            legal.append(tile)
    return legal