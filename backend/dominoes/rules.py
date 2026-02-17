from typing import Optional
from .types import Domino


def legal_moves_for_hand(hand: list[Domino], ends: Optional[tuple[int, int]]) -> list[tuple[Domino, str]]:
    if ends is None:
        return [(tile, "start") for tile in hand]
    left, right = ends
    legal = []
    for tile in hand:
        a, b = tile.a, tile.b
        if a == left or b == left:
            legal.append((tile, "left"))
        if a == right or b == right:
            legal.append((tile, "right"))
    return legal
