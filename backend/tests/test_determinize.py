"""The determinizing bot must never use a tile it was not shown.

Its whole premise is that it reasons about hands it cannot see, so the useful
guarantee is not "it plays well" but "it could not have cheated": every world
it invents has to be consistent with the public record, and its choice has to
be a function of that record plus its own hand and nothing else.
"""

import random

import pytest

from bots.greedy_bot import GreedyBot
from bots.pimc_bot import PIMCBot
from cfr.determinize import sample_world, sample_world_relaxed, unseen_tiles
from cfr.engine import TILE_A, TILE_B, TILE_ID, TILE_MASK, mask_tiles, new_hand
from dominoes.context import build_bot_context
from dominoes.rules import legal_moves_for_hand
from dominoes.types import Domino, GameMode, MatchConfig

CONFIG = MatchConfig(target_points=200, mode=GameMode.TEAMS)


# ------------------------------------------------------------------ sampling


def test_a_sampled_world_deals_every_unseen_tile_exactly_once():
    rng = random.Random(0)
    pool = list(range(12))
    world = sample_world(pool, [1, 2, 3], [4, 4, 4], [0, 0, 0], rng)
    assert world is not None
    dealt = [t for h in world for t in mask_tiles(h)]
    assert sorted(dealt) == sorted(pool)


def test_a_sampled_world_respects_the_hand_sizes():
    rng = random.Random(1)
    world = sample_world(list(range(10)), [1, 2, 3], [5, 3, 2], [0, 0, 0], rng)
    assert [bin(h).count("1") for h in world] == [5, 3, 2]


def test_a_sampled_world_never_gives_a_seat_a_number_it_passed_on():
    """A seat that passed against ends (3, 5) holds no threes and no fives."""
    rng = random.Random(2)
    voids = [(1 << 3) | (1 << 5), 0, 0]
    pool = list(range(21))  # 21 tiles into three hands of seven
    for _ in range(40):
        world = sample_world(pool, [1, 2, 3], [7, 7, 7], voids, rng)
        assert world is not None
        for tile in mask_tiles(world[0]):
            assert TILE_A[tile] not in (3, 5)
            assert TILE_B[tile] not in (3, 5)


def test_an_impossible_set_of_voids_is_reported_rather_than_faked():
    """Every seat void in everything cannot be dealt to."""
    rng = random.Random(3)
    everything = (1 << 7) - 1
    assert sample_world(list(range(9)), [1, 2, 3], [3, 3, 3], [everything] * 3, rng) is None


def test_the_relaxed_sampler_still_deals_a_complete_world():
    rng = random.Random(4)
    everything = (1 << 7) - 1
    world, exact = sample_world_relaxed(
        list(range(9)), [1, 2, 3], [3, 3, 3], [everything] * 3, rng
    )
    assert exact is False
    assert [bin(h).count("1") for h in world] == [3, 3, 3]
    assert sorted(t for h in world for t in mask_tiles(h)) == list(range(9))


def test_unseen_tiles_excludes_this_hand_and_the_board():
    own = TILE_MASK[0] | TILE_MASK[5]
    board = TILE_MASK[9]
    pool = unseen_tiles(own, board)
    assert 0 not in pool and 5 not in pool and 9 not in pool
    assert len(pool) == 25


# ------------------------------------------------------------- no peeking


def position(seed=0, plies=6):
    """A mid-hand position with seat 0 to move, and the context it may see."""
    rng = random.Random(seed)
    pick = random.Random(seed + 1)
    sim = new_hand(rng, starter=0, forced_open=False)
    board, history = [], []
    from cfr.abstraction import canonical_moves
    from cfr.engine import LEFT, RIGHT, START

    labels = {START: "start", LEFT: "left", RIGHT: "right"}
    # Advance whole rounds so the walk always stops with seat 0 on turn.
    for _ in range(plies - plies % 4):
        if sim.is_terminal():
            break
        seat = sim.cp
        moves = canonical_moves(sim, seat)
        move = pick.choice(moves) if moves else None
        prior = None if sim.left < 0 else (sim.left, sim.right)
        if move is None:
            history.append({"player": seat, "tile": None, "end": "pass", "ends": prior})
        else:
            a, b = TILE_A[move[0]], TILE_B[move[0]]
            history.append(
                {"player": seat, "tile": (a, b), "end": labels[move[1]], "ends": prior}
            )
            board.append(Domino(a, b))
        sim.apply(move)
    return sim, board, history


def context_for(sim, board, history, seat=0):
    return build_bot_context(
        player_index=seat,
        config=CONFIG,
        board=board,
        ends=None if sim.left < 0 else (sim.left, sim.right),
        hand_counts=[bin(m).count("1") for m in sim.hands],
        move_history=history,
    )


def test_the_context_handed_to_a_bot_contains_nobody_elses_tiles():
    """The structural guarantee. A bot receives (hand, ends, context) and
    nothing else, so the question is whether `context` itself carries hidden
    tiles. Walk every field and check that the only tiles in it are the ones
    already face up on the board.

    An earlier version of this file tried to prove the point by redealing the
    hidden hands and asserting the bot's move did not change. That could never
    fail: BotContext snapshots the public state when it is built, so both calls
    received byte-identical arguments and the assertion reduced to "a seeded
    function is deterministic".
    """
    for seed in range(12):
        sim, board, history = position(seed)
        if sim.is_terminal():
            continue
        ctx = context_for(sim, board, history)
        on_board = {(t.a, t.b) for t in board} | {(t.b, t.a) for t in board}
        own = {(TILE_A[t], TILE_B[t]) for t in mask_tiles(sim.hands[0])}

        # Every tile mentioned anywhere in the context must be public or ours.
        for tile in ctx.board:
            assert (tile.a, tile.b) in on_board
        for move in ctx.move_history:
            if move["tile"] is not None:
                assert move["tile"] in on_board
        # Hidden hands appear only as counts.
        assert ctx.hand_counts == [bin(m).count("1") for m in sim.hands]
        leaked = [
            (TILE_A[t], TILE_B[t])
            for seat in (1, 2, 3)
            for t in mask_tiles(sim.hands[seat])
        ]
        blob = repr(ctx)
        for a, b in leaked:
            if (a, b) in on_board or (a, b) in own:
                continue
            assert f"Domino(a={a}, b={b})" not in blob, f"context leaked {a}|{b}"


def test_the_bot_actually_searches_rather_than_deferring_to_the_heuristic():
    """Kills the mutation that matters: replacing the whole search with the
    GreedyBot fallback used to leave every test in the suite green, so nothing
    exercised determinization at all."""
    greedy = GreedyBot()
    differs = decisions = 0
    for seed in range(30):
        sim, board, history = position(seed, plies=8)
        if sim.is_terminal() or sim.cp != 0:
            continue
        hand = [Domino(TILE_A[t], TILE_B[t]) for t in mask_tiles(sim.hands[0])]
        ends = None if sim.left < 0 else (sim.left, sim.right)
        if len(legal_moves_for_hand(hand, ends)) < 2:
            continue
        ctx = context_for(sim, board, history)
        decisions += 1
        if PIMCBot(worlds=8, seed=3).choose_move(hand, ends, ctx) != greedy.choose_move(
            hand, ends, ctx
        ):
            differs += 1
    assert decisions >= 8, f"only {decisions} usable positions"
    assert differs > 0, "the search never once disagreed with the heuristic"


def test_the_bot_changes_its_mind_when_the_pass_record_changes():
    """It is supposed to reason from what the opponents have shown void in.
    If the void record is ignored, this cannot happen."""
    changed = compared = 0
    for seed in range(30):
        sim, board, history = position(seed, plies=8)
        if sim.is_terminal() or sim.cp != 0:
            continue
        hand = [Domino(TILE_A[t], TILE_B[t]) for t in mask_tiles(sim.hands[0])]
        ends = None if sim.left < 0 else (sim.left, sim.right)
        if sim.left < 0 or len(legal_moves_for_hand(hand, ends)) < 2:
            continue
        plain = context_for(sim, board, history)

        # Same position, except the seat to our left has passed on both ends.
        loud = list(history) + [
            {"player": 1, "tile": None, "end": "pass", "ends": (sim.left, sim.right)}
        ]
        informed = context_for(sim, board, loud)
        assert informed.known_voids[1], "the pass did not register as a void"

        compared += 1
        if PIMCBot(worlds=8, seed=4).choose_move(hand, ends, plain) != PIMCBot(
            worlds=8, seed=4
        ).choose_move(hand, ends, informed):
            changed += 1
    assert compared >= 6, f"only {compared} comparable positions"
    assert changed > 0, "knowing an opponent is void never changed the play"


def test_the_bot_only_ever_returns_a_legal_move():
    for seed in range(30):
        sim, board, history = position(seed, plies=seed % 9)
        if sim.is_terminal() or sim.cp != 0:
            continue
        hand = [Domino(TILE_A[t], TILE_B[t]) for t in mask_tiles(sim.hands[0])]
        ends = None if sim.left < 0 else (sim.left, sim.right)
        legal = legal_moves_for_hand(hand, ends)
        move = PIMCBot(worlds=4, seed=1).choose_move(hand, ends, context_for(sim, board, history))
        if not legal:
            assert move is None
        else:
            assert move in legal


def test_the_bot_passes_when_it_has_nothing_to_play():
    bot = PIMCBot(worlds=4, seed=0)
    assert bot.choose_move([Domino(1, 2)], (3, 4), None) is None


def test_the_bot_defers_to_the_heuristic_without_a_context():
    bot = PIMCBot(worlds=4, seed=0)
    hand = [Domino(1, 2), Domino(3, 3)]
    assert bot.choose_move(hand, (1, 3), None) == GreedyBot().choose_move(hand, (1, 3), None)


def test_the_forced_opening_lead_is_the_only_move_considered():
    bot = PIMCBot(worlds=4, seed=0)
    move = bot.choose_move(
        [Domino(6, 6), Domino(3, 4), Domino(0, 0)], None, {"forced_tile": Domino(6, 6)}
    )
    assert move == (Domino(6, 6), "start")
