from collections import Counter
from dominoes.bots import BotBase
from dominoes.rules import legal_moves_for_hand


def _resulting_ends(current_ends, tile, end):
    if current_ends is None or end == "start":
        return (tile.a, tile.b)
    left, right = current_ends
    if end == "left":
        if tile.a == left:
            return (tile.b, right)
        return (tile.a, right)
    if tile.a == right:
        return (left, tile.b)
    return (left, tile.a)


class GreedyBot(BotBase):

    def choose_move(self, hand, ends, context=None):
        legal = legal_moves_for_hand(hand, ends)
        if not legal:
            return None
        context = context or {}
        teammate_counts = Counter(context.get("teammate_played_numbers", {}))
        opponent_counts = Counter(context.get("opponent_played_numbers", {}))
        capicu_bonus = context.get("capicu_bonus", 0)
        chuchazo_bonus = context.get("chuchazo_bonus", 0)
        hand_number_counts = Counter()
        for tile in hand:
            hand_number_counts[tile.a] += 1
            hand_number_counts[tile.b] += 1

        def score(move):
            tile, end = move
            remaining_counts = hand_number_counts.copy()
            remaining_counts[tile.a] -= 1
            remaining_counts[tile.b] -= 1
            new_left, new_right = _resulting_ends(ends, tile, end)
            s = 0.0
            s += 2.5 * remaining_counts[new_left]
            s += 2.5 * remaining_counts[new_right]
            s += 1.5 * max(remaining_counts.values(), default=0)
            s += 0.35 * tile.pips()
            s += 1.4 * teammate_counts[new_left]
            s += 1.4 * teammate_counts[new_right]
            s -= 1.0 * opponent_counts[new_left]
            s -= 1.0 * opponent_counts[new_right]
            if tile.is_double():
                s -= 0.2
                s += 0.8 * remaining_counts[tile.a]
            if len(hand) == 1:
                if new_left == new_right:
                    s += capicu_bonus
                if tile.is_double_blank():
                    s += chuchazo_bonus
            return s

        return max(legal, key=score)
