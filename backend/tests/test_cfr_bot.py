"""The bot must see exactly what the trainer saw.

At training time the position is a HandSim; at play time the bot rebuilds it
from the public BotContext plus its own tiles. If those two views disagree
about the infoset key, every lookup misses. If they agree on the key but
disagree on the action ids, lookups land and then produce nothing usable --
which is how a pip-abstract key paired with a pip-labelled action vocabulary
failed: 14 usable lookups out of 12,533, indistinguishable from undertraining.
Both halves are checked here, for every level.
"""

import random

import numpy as np
import pytest

from bots.cfr_bot import CFRBot, sim_from_context
from bots.greedy_bot import GreedyBot
from bots.random_bot import RandomBot
from cfr.abstraction import LEVELS, actions_for, canonical_moves, key_for
from cfr.engine import LEFT, RIGHT, START, TILES, mask_tiles, new_hand
from cfr.policy import from_arrays
from dominoes.context import build_bot_context
from dominoes.rules import legal_moves_for_hand
from dominoes.types import Domino, GameMode, MatchConfig

CONFIG = MatchConfig(target_points=200, mode=GameMode.TEAMS)
END_LABEL = {START: "start", LEFT: "left", RIGHT: "right"}


def replay(hands=40, seed=0):
    """Walk hands, yielding (sim, seat, hand, ends, context) at each decision.

    The context is built exactly as arena.py builds it, so what the test
    compares is the real play-time input, not a convenient stand-in.
    """
    rng = random.Random(seed)
    pick = random.Random(seed + 1)
    for h in range(hands):
        sim = new_hand(rng, starter=rng.randrange(4), forced_open=(h % 3 == 0))
        board, history = [], []
        while not sim.is_terminal():
            seat = sim.cp
            moves = canonical_moves(sim, seat)
            if moves:
                hand = [Domino(*TILES[t]) for t in mask_tiles(sim.hands[seat])]
                ends = None if sim.left < 0 else (sim.left, sim.right)
                ctx = build_bot_context(
                    player_index=seat,
                    config=CONFIG,
                    board=board,
                    ends=ends,
                    hand_counts=[bin(m).count("1") for m in sim.hands],
                    move_history=history,
                    forced_tile=(
                        Domino(6, 6) if (sim.forced >= 0 and sim.left < 0) else None
                    ),
                )
                yield sim, seat, hand, ends, ctx
            move = pick.choice(moves) if moves else None
            prior = None if sim.left < 0 else (sim.left, sim.right)
            if move is None:
                history.append(
                    {"player": seat, "tile": None, "end": "pass", "ends": prior}
                )
            else:
                tile, end = move
                a, b = TILES[tile]
                history.append(
                    {
                        "player": seat,
                        "tile": (a, b),
                        "end": END_LABEL[end],
                        "ends": prior,
                    }
                )
                board.append(Domino(a, b))
            sim.apply(move)


@pytest.mark.parametrize("level", LEVELS)
def test_the_rebuilt_position_produces_the_same_infoset_key(level):
    checked = 0
    for sim, seat, hand, ends, ctx in replay():
        rebuilt, rebuilt_seat = sim_from_context(hand, ends, ctx)
        assert rebuilt_seat == seat
        assert key_for(rebuilt, seat, level) == key_for(sim, seat, level)
        checked += 1
    assert checked > 400


@pytest.mark.parametrize("level", LEVELS)
def test_the_rebuilt_position_produces_the_same_action_ids(level):
    """A matching key with mismatched action ids is worse than a miss: the
    lookup succeeds and returns actions that are not legal here."""
    checked = 0
    for sim, seat, hand, ends, ctx in replay():
        rebuilt, _ = sim_from_context(hand, ends, ctx)
        assert actions_for(rebuilt, seat, level)[0] == actions_for(sim, seat, level)[0]
        checked += 1
    assert checked > 400


@pytest.mark.parametrize("level", LEVELS)
def test_a_policy_trained_on_these_positions_is_usable_at_play_time(level):
    """Train a table on the exact positions the walk visits, then confirm the
    bot can actually use it -- key hit and at least one legal stored action."""
    info, action = [], []
    for sim, seat, _, _, _ in replay(hands=25, seed=3):
        key = key_for(sim, seat, level)
        for aid in actions_for(sim, seat, level)[0]:
            info.append(key)
            action.append(aid)
    policy = from_arrays(
        np.array(info, dtype=np.uint64),
        np.array(action, dtype=np.uint8),
        np.ones(len(info)),
        level,
    )
    bot = CFRBot(policy, seed=0)
    for _, seat, hand, ends, ctx in replay(hands=25, seed=3):
        move = bot.choose_move(hand, ends, ctx)
        assert move is not None
    assert bot.hit_rate > 0.95, f"{level}: hit rate {bot.hit_rate:.3f}"


def test_the_bot_only_ever_returns_a_legal_move():
    policy = from_arrays(
        np.array([1], dtype=np.uint64), np.array([0], dtype=np.uint8),
        np.ones(1), "tiny",
    )
    bot = CFRBot(policy, seed=0)
    for _, _, hand, ends, ctx in replay(hands=30, seed=5):
        tile, end = bot.choose_move(hand, ends, ctx)
        assert (tile, end) in legal_moves_for_hand(hand, ends)


def test_an_empty_policy_falls_back_to_greedy_on_every_turn():
    empty = from_arrays(
        np.zeros(0, np.uint64), np.zeros(0, np.uint8), np.zeros(0), "tiny"
    )
    bot = CFRBot(empty, seed=0)
    greedy = GreedyBot()
    for _, _, hand, ends, ctx in replay(hands=20, seed=7):
        assert bot.choose_move(hand, ends, ctx) == greedy.choose_move(hand, ends, ctx)
    assert bot.hits == 0
    assert bot.hit_rate == 0.0


def test_the_bot_passes_when_it_has_nothing_to_play():
    empty = from_arrays(
        np.zeros(0, np.uint64), np.zeros(0, np.uint8), np.zeros(0), "tiny"
    )
    bot = CFRBot(empty, seed=0)
    assert bot.choose_move([Domino(1, 2)], (3, 4), None) is None


def test_the_bot_plays_a_full_arena_match_without_error():
    from bots.arena import run_arena

    empty = from_arrays(
        np.zeros(0, np.uint64), np.zeros(0, np.uint8), np.zeros(0), "tiny"
    )
    result = run_arena(CFRBot(empty, seed=0), RandomBot(), num_matches=15, seed=2)
    assert result["team_a_wins"] + result["team_b_wins"] == 15


def policy_favouring(level, pick_last, seed=9, hands=8):
    """A policy built on infosets the bot will actually meet.

    Keying a test policy on an arbitrary integer looks like a test of the
    argmax but is not: no real position hashes to it, every lookup misses, and
    the bot answers from its GreedyBot fallback throughout. Inverting max to
    min in cfr_bot then left the whole suite green.
    """
    info, action, weight = [], [], []
    for sim, seat, _, _, _ in replay(hands=hands, seed=seed):
        ids = actions_for(sim, seat, level)[0]
        if not ids:
            continue
        key = key_for(sim, seat, level)
        favoured = ids[-1] if pick_last else ids[0]
        for aid in ids:
            info.append(key)
            action.append(aid)
            weight.append(9.0 if aid == favoured else 1.0)
    return from_arrays(
        np.array(info, dtype=np.uint64),
        np.array(action, dtype=np.uint8),
        np.array(weight),
        level,
    )


@pytest.mark.parametrize("level", LEVELS)
def test_the_bot_plays_the_action_the_table_scores_highest(level):
    """Weight the last legal action at every infoset, then the first, and the
    bot's choices must follow. This is what catches max being turned into min.
    """
    for pick_last in (True, False):
        policy = policy_favouring(level, pick_last=pick_last)
        bot = CFRBot(policy, seed=0)
        seen = decided = 0
        for sim, seat, hand, ends, ctx in replay(hands=8, seed=9):
            ids, groups = actions_for(sim, seat, level)
            if len(ids) < 2:
                continue
            seen += 1
            entry = policy.lookup(key_for(sim, seat, level))
            assert entry is not None, f"{level}: policy missed a trained infoset"
            stored = {int(a): float(p) for a, p in zip(*entry) if int(a) in ids}
            if not stored:
                continue
            best = max(stored.values())
            # The abstraction merges positions, so a key can carry several
            # actions at the same weight; any of those is a correct argmax.
            winners = [a for a, w in stored.items() if w >= best - 1e-9]
            allowed = [
                (Domino(*TILES[t]), END_LABEL[e])
                for a in winners
                for t, e in groups[ids.index(a)]
            ]
            chosen = bot.choose_move(hand, ends, ctx)
            assert chosen in allowed, (
                f"{level}: highest-weighted legal actions were {winners}, "
                f"bot played {chosen}"
            )
            decided += 1
        assert seen >= 10, f"{level}: only {seen} multi-action decisions"
        assert decided >= 8, f"{level}: only {decided} decisions had stored weights"
        assert bot.hit_rate > 0.9, f"{level}: hit rate {bot.hit_rate:.2f}"


def test_the_bot_plays_the_mode_by_default_and_does_so_deterministically():
    policy = policy_favouring("tiny", pick_last=True)
    bot = CFRBot(policy, seed=0)
    assert bot.sample is False, "the default must be the mode, not a sample"
    # One bot per run: several concrete moves can share an abstract action id,
    # and the tie between them is broken with the bot's own RNG, so the state
    # has to advance the same way in both runs.
    twin = CFRBot(policy, seed=0)
    first = [bot.choose_move(h, e, c) for _, _, h, e, c in replay(hands=8, seed=9)]
    again = [twin.choose_move(h, e, c) for _, _, h, e, c in replay(hands=8, seed=9)]
    assert first == again
    assert bot.hit_rate > 0.9


def test_sampling_can_be_asked_for_explicitly():
    empty = from_arrays(
        np.zeros(0, np.uint64), np.zeros(0, np.uint8), np.zeros(0), "tiny"
    )
    assert CFRBot(empty, sample=True).sample is True
