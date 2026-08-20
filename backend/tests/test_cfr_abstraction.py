"""The two properties the abstraction has to have for CFR to mean anything.

If a key depended on tiles the acting seat cannot see, CFR would converge to a
policy that needs hidden information to execute -- unplayable. If an action id
shifted meaning between visits to the same key, regrets would accumulate
against moving targets and the average strategy would be noise.
"""

import os
import random
import subprocess
import sys

import pytest

from cfr.abstraction import (
    ACTION_COUNT,
    COARSE,
    STANDARD,
    action_id,
    canonical_moves,
    hand_profile,
    infoset_key,
    legal_actions,
    slot_key,
)
from cfr.engine import (
    LEFT,
    RIGHT,
    TILE_ID,
    TILE_MASK,
    HandSim,
    mask_tiles,
    new_hand,
)


def sim_from(hands, left, right, cp=0):
    """A HandSim posed at a specific board, for hand-built positions."""
    masks = [sum(TILE_MASK[TILE_ID[t]] for t in h) for h in hands]
    sim = HandSim(masks, starter=cp, forced_open=False)
    sim.left, sim.right = left, right
    sim.cp = cp
    return sim


def random_positions(n=300, seed=0):
    rng = random.Random(seed)
    pick = random.Random(seed + 1)
    out = []
    for i in range(n):
        sim = new_hand(rng, starter=rng.randrange(4), forced_open=(i % 3 == 0))
        while not sim.is_terminal():
            if canonical_moves(sim, sim.cp):
                out.append((sim, sim.cp))
                yield sim, sim.cp
            moves = canonical_moves(sim, sim.cp)
            sim.apply(pick.choice(moves) if moves else None)


# ------------------------------------------------- no hidden-information leak


@pytest.mark.parametrize("level", [STANDARD, COARSE])
def test_the_key_ignores_which_tiles_the_opponents_actually_hold(level):
    """Redealing the other three hands among themselves must not move the key.

    Seat 0 can see how many tiles each opponent holds and what they have shown
    void in -- never which tiles those are.
    """
    rng = random.Random(5)
    checked = 0
    for _ in range(200):
        sim = new_hand(rng, starter=0, forced_open=False)
        if not canonical_moves(sim, 0):
            continue
        before = infoset_key(sim, 0, level)
        pool = [t for seat in (1, 2, 3) for t in mask_tiles(sim.hands[seat])]
        rng.shuffle(pool)
        sizes = [bin(sim.hands[s]).count("1") for s in (1, 2, 3)]
        cursor = 0
        for seat, size in zip((1, 2, 3), sizes):
            sim.hands[seat] = sum(TILE_MASK[t] for t in pool[cursor : cursor + size])
            cursor += size
        assert infoset_key(sim, 0, level) == before
        checked += 1
    assert checked > 100


@pytest.mark.parametrize("level", [STANDARD, COARSE])
def test_the_key_does_move_when_the_acting_seats_own_hand_changes(level):
    a = sim_from([[(3, 4), (5, 5)], [(0, 1)], [(0, 2)], [(0, 3)]], 3, 5)
    b = sim_from([[(3, 4), (6, 6)], [(0, 1)], [(0, 2)], [(0, 3)]], 3, 5)
    assert infoset_key(a, 0, level) != infoset_key(b, 0, level)


def test_the_key_tracks_opponent_hand_sizes():
    a = sim_from([[(3, 4)], [(0, 1), (0, 2)], [(1, 2)], [(0, 3)]], 3, 5)
    b = sim_from([[(3, 4)], [(0, 1)], [(1, 2)], [(0, 3)]], 3, 5)
    assert infoset_key(a, 0) != infoset_key(b, 0)


def test_the_key_tracks_voids_shown_on_the_current_ends():
    a = sim_from([[(3, 4)], [(0, 1)], [(1, 2)], [(0, 2)]], 3, 5)
    b = sim_from([[(3, 4)], [(0, 1)], [(1, 2)], [(0, 2)]], 3, 5)
    b.voids[1] = 1 << 3
    assert infoset_key(a, 0) != infoset_key(b, 0)


def test_a_void_on_a_number_that_is_not_an_open_end_is_not_in_the_key():
    a = sim_from([[(3, 4)], [(0, 1)], [(1, 2)], [(0, 2)]], 3, 5)
    b = sim_from([[(3, 4)], [(0, 1)], [(1, 2)], [(0, 2)]], 3, 5)
    b.voids[1] = 1 << 6  # neither end is a six
    assert infoset_key(a, 0) == infoset_key(b, 0)


# ------------------------------------------------------ board mirror symmetry


def test_a_position_and_its_mirror_share_a_key():
    hands = [[(3, 4), (5, 5), (2, 6)], [(0, 1)], [(1, 2)], [(0, 2)]]
    straight = sim_from(hands, 3, 5)
    mirrored = sim_from(hands, 5, 3)
    assert infoset_key(straight, 0) == infoset_key(mirrored, 0)


def test_mirroring_the_board_mirrors_the_action_ids_consistently():
    hands = [[(3, 4), (5, 5), (2, 6)], [(0, 1)], [(1, 2)], [(0, 2)]]
    straight = sim_from(hands, 3, 5)
    mirrored = sim_from(hands, 5, 3)
    assert set(legal_actions(straight, 0)[0]) == set(legal_actions(mirrored, 0)[0])


def test_equal_ends_collapse_the_two_sides_into_one_action():
    sim = sim_from([[(3, 4)], [(0, 1)], [(1, 2)], [(0, 2)]], 3, 3)
    assert len(sim.legal(0)) == 2  # reported for both ends
    assert len(canonical_moves(sim, 0)) == 1
    ids, _ = legal_actions(sim, 0)
    assert len(ids) == 1


# ------------------------------------------------------- action id behaviour


def test_action_ids_are_injective_over_the_canonical_moves_of_a_position():
    for sim, seat in random_positions(200, seed=3):
        moves = canonical_moves(sim, seat)
        ids = [action_id(sim, m) for m in moves]
        assert len(set(ids)) == len(ids)


def test_action_ids_stay_inside_the_declared_vocabulary():
    for sim, seat in random_positions(200, seed=4):
        for move in canonical_moves(sim, seat):
            assert 0 <= action_id(sim, move) < ACTION_COUNT


def test_an_action_id_does_not_depend_on_the_hand_it_was_played_from():
    """Ids must be global, or regrets at a shared key would not be comparable."""
    a = sim_from([[(3, 4), (5, 5)], [(0, 1)], [(1, 2)], [(0, 2)]], 3, 5)
    b = sim_from([[(3, 4), (6, 6), (2, 2)], [(0, 1)], [(1, 2)], [(0, 2)]], 3, 5)
    move = (TILE_ID[(3, 4)], LEFT)
    assert action_id(a, move) == action_id(b, move)


def test_every_legal_action_group_maps_back_to_a_legal_move():
    for sim, seat in random_positions(200, seed=6):
        ids, groups = legal_actions(sim, seat)
        legal = set(sim.legal(seat))
        assert len(ids) == len(groups)
        for group in groups:
            assert group
            for move in group:
                assert move in legal


def test_slot_keys_separate_the_actions_of_one_infoset():
    key = infoset_key(sim_from([[(3, 4)], [(0, 1)], [(1, 2)], [(0, 2)]], 3, 5), 0)
    slots = {slot_key(key, a) for a in range(ACTION_COUNT)}
    assert len(slots) == ACTION_COUNT


# --------------------------------------------------------------- determinism


def test_keys_are_identical_in_a_fresh_interpreter_with_a_different_hash_seed():
    """Cluster workers and the local exporter must agree on every key.

    Anything routed through Python's salted str hash would silently disagree
    between processes, so the digest is recomputed under PYTHONHASHSEED=1.
    """
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = (
        "import random, sys;"
        f"sys.path.insert(0, {backend!r});"
        "from cfr.engine import new_hand;"
        "from cfr.abstraction import infoset_key, canonical_moves;"
        "rng = random.Random(0); pick = random.Random(1); acc = 0;"
        "\nfor _ in range(50):\n"
        "    sim = new_hand(rng)\n"
        "    while not sim.is_terminal():\n"
        "        if canonical_moves(sim, sim.cp):\n"
        "            acc = (acc + infoset_key(sim, sim.cp)) % (2**61 - 1)\n"
        "        ms = canonical_moves(sim, sim.cp)\n"
        "        sim.apply(pick.choice(ms) if ms else None)\n"
        "print(acc)"
    )
    outs = set()
    for seed in ("0", "1", "12345"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        )
        assert proc.returncode == 0, proc.stderr
        outs.add(proc.stdout.strip())
    assert len(outs) == 1, f"keys differ across hash seeds: {outs}"
