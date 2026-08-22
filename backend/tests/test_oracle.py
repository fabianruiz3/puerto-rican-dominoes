"""The oracle's opponent has to be the same heuristic it is measured against.

The oracle exists to establish a ceiling: it sees all four hands and searches
exactly, so whatever it scores against GreedyBot is more than any policy could.
That number is only meaningful if the seats it beats are playing the same
GreedyBot the CFR bot is benchmarked against, so fast_greedy_move is checked
against the real one move by move.
"""

import random

from bots.greedy_bot import GreedyBot
from cfr.engine import LEFT, RIGHT, START, TILES, mask_tiles, new_hand
from cfr.oracle import fast_greedy_move, new_played, oracle_move, oracle_value
from dominoes.context import build_bot_context
from dominoes.types import Domino, GameMode, MatchConfig

CONFIG = MatchConfig(target_points=200, mode=GameMode.TEAMS)
END_LABEL = {START: "start", LEFT: "left", RIGHT: "right"}


def hand_in_engine_order(sim, seat):
    """Tiles ordered as the engine enumerates them, so ties break alike."""
    return [Domino(*TILES[t]) for t in mask_tiles(sim.hands[seat])]


def walk(hands=120, seed=0):
    """Play hands with the fast greedy, yielding each decision it faced."""
    rng = random.Random(seed)
    for h in range(hands):
        sim = new_hand(rng, starter=rng.randrange(4), forced_open=(h % 4 == 0))
        played = new_played()
        board, history = [], []
        while not sim.is_terminal():
            seat = sim.cp
            if sim.legal(seat):
                yield sim, seat, played, board, history
            move = fast_greedy_move(sim, seat, played)
            prior = None if sim.left < 0 else (sim.left, sim.right)
            if move is None:
                history.append(
                    {"player": seat, "tile": None, "end": "pass", "ends": prior}
                )
            else:
                tile, end = move
                a, b = TILES[tile]
                history.append(
                    {"player": seat, "tile": (a, b), "end": END_LABEL[end], "ends": prior}
                )
                board.append(Domino(a, b))
                played[seat][a] += 1
                played[seat][b] += 1
            sim.apply(move)


def test_fast_greedy_picks_exactly_what_greedybot_picks():
    real = GreedyBot()
    checked = agreed = 0
    for sim, seat, played, board, history in walk():
        context = build_bot_context(
            player_index=seat,
            config=CONFIG,
            board=board,
            ends=None if sim.left < 0 else (sim.left, sim.right),
            hand_counts=[bin(m).count("1") for m in sim.hands],
            move_history=history,
            forced_tile=Domino(6, 6) if (sim.forced >= 0 and sim.left < 0) else None,
        )
        theirs = real.choose_move(hand_in_engine_order(sim, seat), context["ends"], context)
        mine = fast_greedy_move(sim, seat, played)
        tile, end = mine
        checked += 1
        if theirs == (Domino(*TILES[tile]), END_LABEL[end]):
            agreed += 1
    assert checked > 2000
    assert agreed == checked, f"diverged on {checked - agreed} of {checked} decisions"


def test_the_played_counts_the_search_maintains_match_the_context():
    """The search updates played-per-seat incrementally rather than rebuilding
    a context at every node; if that drifted, the opponent would drift too."""
    for sim, seat, played, board, history in walk(hands=40, seed=5):
        context = build_bot_context(
            player_index=seat,
            config=CONFIG,
            board=board,
            ends=None if sim.left < 0 else (sim.left, sim.right),
            hand_counts=[bin(m).count("1") for m in sim.hands],
            move_history=history,
        )
        partner = (seat + 2) & 3
        assert dict(enumerate(played[partner])) == context.teammate_played_numbers
        opponents = [0] * 7
        for other in ((seat + 1) & 3, (seat + 3) & 3):
            for n in range(7):
                opponents[n] += played[other][n]
        assert dict(enumerate(opponents)) == context.opponent_played_numbers


def test_the_oracle_never_scores_worse_than_the_heuristic_it_replaces():
    """Searching every line it could play cannot do worse than the one line
    the heuristic would have picked."""
    rng = random.Random(3)
    for _ in range(25):
        sim = new_hand(rng, starter=rng.randrange(4), forced_open=False)
        played = new_played()
        oracle = oracle_value(sim, team=0, played=played)

        # Value of the same deal with the heuristic playing every seat.
        greedy_sim = new_hand(random.Random(0))
        greedy_sim.hands = list(sim.hands)
        greedy_sim.cp = greedy_sim.starter = sim.cp
        greedy_sim.forced = sim.forced
        gp = new_played()
        while not greedy_sim.is_terminal():
            seat = greedy_sim.cp
            move = fast_greedy_move(greedy_sim, seat, gp)
            if move is not None:
                gp[seat][TILES[move[0]][0]] += 1
                gp[seat][TILES[move[0]][1]] += 1
            greedy_sim.apply(move)
        heuristic = greedy_sim.utility(0, 100, 100)
        assert oracle >= heuristic, f"oracle {oracle} < heuristic {heuristic}"


def test_the_oracle_returns_a_legal_move():
    rng = random.Random(9)
    sim = new_hand(rng, starter=0, forced_open=False)
    move = oracle_move(sim, team=0, played=new_played())
    assert move in sim.legal(sim.cp)
