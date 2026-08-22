"""How well could anything possibly play?

Before chasing a higher win rate it is worth knowing what the ceiling is. In
this game every tile is dealt, so once the deal is fixed there is no hidden
randomness left -- only hidden *information*. A player that could see all four
hands and search the rest of the hand exactly is therefore strictly better than
any policy that cannot, and whatever it scores against a given opponent is an
upper bound on what CFR could ever reach against that opponent.

That is what this measures. The oracle team searches every line it could play
while the opposing seats answer with the heuristic; alpha-beta over the team's
point swing. The tree is small because only the oracle's own seats branch --
about 2.5 ways, eleven times a hand.

`fast_greedy_move` is GreedyBot re-expressed over the integer engine so the
search can afford to call it at every node. tests/test_oracle.py asserts it
picks the same move as the real GreedyBot across thousands of positions; a
ceiling measured against a different opponent than the one being benchmarked
would be worthless.
"""

from .engine import (
    LEFT,
    RIGHT,
    START,
    TILE_A,
    TILE_B,
    TILE_IS_DOUBLE,
    TILE_PIPS,
    mask_tiles,
    other_pip,
)

CAPICU_BONUS = 100
CHUCHAZO_BONUS = 100


def _number_counts(hand: int) -> list[int]:
    counts = [0] * 7
    for t in mask_tiles(hand):
        counts[TILE_A[t]] += 1
        counts[TILE_B[t]] += 1
    return counts


def fast_greedy_move(sim, seat, played):
    """GreedyBot's choice, over the integer engine.

    `played` is played[seat][number]: how many pip-slots of each number each
    seat has laid down, which is what GreedyBot reads out of its context.
    """
    moves = sim.legal(seat)
    if not moves:
        return None

    hand = sim.hands[seat]
    counts = _number_counts(hand)
    hand_size = bin(hand).count("1")
    partner = (seat + 2) & 3
    teammate = played[partner]
    opponents = [0] * 7
    for other in ((seat + 1) & 3, (seat + 3) & 3):
        row = played[other]
        for n in range(7):
            opponents[n] += row[n]

    best = None
    best_score = None
    for tile, end in moves:
        remaining = list(counts)
        remaining[TILE_A[tile]] -= 1
        remaining[TILE_B[tile]] -= 1
        if end == START or sim.left < 0:
            new_left, new_right = TILE_A[tile], TILE_B[tile]
        elif end == LEFT:
            new_left, new_right = other_pip(tile, sim.left), sim.right
        else:
            new_left, new_right = sim.left, other_pip(tile, sim.right)

        score = 0.0
        score += 2.5 * remaining[new_left]
        score += 2.5 * remaining[new_right]
        score += 1.5 * max(remaining)
        score += 0.35 * TILE_PIPS[tile]
        score += 1.4 * teammate[new_left]
        score += 1.4 * teammate[new_right]
        score -= 1.0 * opponents[new_left]
        score -= 1.0 * opponents[new_right]
        if TILE_IS_DOUBLE[tile]:
            score -= 0.2
            score += 0.8 * remaining[TILE_A[tile]]
        if hand_size == 1:
            if new_left == new_right:
                score += CAPICU_BONUS
            if TILE_A[tile] == 0 and TILE_B[tile] == 0:
                score += CHUCHAZO_BONUS
        if best_score is None or score > best_score:
            best_score = score
            best = (tile, end)
    return best


def _record(played, seat, tile, delta):
    row = played[seat]
    row[TILE_A[tile]] += delta
    row[TILE_B[tile]] += delta


def oracle_value(sim, team, played, alpha=-10**9, beta=10**9):
    """Best point swing `team` can force, seeing everything.

    The opposing seats answer with the heuristic, so this is the value of a
    perfect-information best response to that opponent -- the most any policy
    could extract from this deal.
    """
    if sim.is_terminal():
        return sim.utility(team, CAPICU_BONUS, CHUCHAZO_BONUS)

    seat = sim.cp
    if (seat & 1) != team:
        move = fast_greedy_move(sim, seat, played)
        if move is not None:
            _record(played, seat, move[0], 1)
        sim.apply(move)
        value = oracle_value(sim, team, played, alpha, beta)
        sim.undo(move)
        if move is not None:
            _record(played, seat, move[0], -1)
        return value

    moves = sim.legal(seat)
    if not moves:
        sim.apply(None)
        value = oracle_value(sim, team, played, alpha, beta)
        sim.undo(None)
        return value

    best = -(10**9)
    for move in moves:
        _record(played, seat, move[0], 1)
        sim.apply(move)
        value = oracle_value(sim, team, played, alpha, beta)
        sim.undo(move)
        _record(played, seat, move[0], -1)
        if value > best:
            best = value
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def best_response_value(sim, seat, played, alpha=-10**9, beta=10**9):
    """Best point swing `seat` alone can force, in a fully known position.

    Only `seat` chooses; the other three answer with the heuristic, partner
    included. This is the per-world search a determinizing player runs -- it
    never sees a real hand, only a sampled one it invented.
    """
    if sim.is_terminal():
        return sim.utility(seat & 1, CAPICU_BONUS, CHUCHAZO_BONUS)

    actor = sim.cp
    if actor != seat:
        move = fast_greedy_move(sim, actor, played)
        if move is not None:
            _record(played, actor, move[0], 1)
        sim.apply(move)
        value = best_response_value(sim, seat, played, alpha, beta)
        sim.undo(move)
        if move is not None:
            _record(played, actor, move[0], -1)
        return value

    moves = sim.legal(actor)
    if not moves:
        sim.apply(None)
        value = best_response_value(sim, seat, played, alpha, beta)
        sim.undo(None)
        return value

    best = -(10**9)
    for move in moves:
        _record(played, actor, move[0], 1)
        sim.apply(move)
        value = best_response_value(sim, seat, played, alpha, beta)
        sim.undo(move)
        _record(played, actor, move[0], -1)
        if value > best:
            best = value
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def oracle_move(sim, team, played):
    """The oracle's own move at the current node."""
    moves = sim.legal(sim.cp)
    if not moves:
        return None
    best_move, best_value = None, -(10**9)
    for move in moves:
        _record(played, sim.cp, move[0], 1)
        sim.apply(move)
        value = oracle_value(sim, team, played)
        sim.undo(move)
        _record(played, sim.cp, move[0], -1)
        if value > best_value:
            best_value, best_move = value, move
    return best_move


def new_played() -> list[list[int]]:
    return [[0] * 7 for _ in range(4)]
