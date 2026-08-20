"""Merging shards and exporting a policy, with the bits that got lost.

The merge originally joined (infoset, action) by packing them into one integer
as (info << 6) | action. Infoset keys use all 64 bits, so that shift silently
dropped the top six: every merged key came back truncated, distinct infosets
collided, and the exported policy missed about 98% of its lookups in play.
Nothing raised -- it read as an undertrained bot. These tests use keys with
high bits set, which is what the real hash produces and what the bug destroyed.
"""

import os
import random
import tempfile

import numpy as np
import pytest

from cfr.policy import Policy, from_arrays, merge_shards, save_shard, sum_by_pair

HIGH_BIT_KEYS = np.array(
    [
        0xFFFF_FFFF_FFFF_FFFF,
        0x8000_0000_0000_0000,
        0xDEAD_BEEF_CAFE_BABE,
        0x0000_0000_0000_0001,
        0xFC00_0000_0000_0001,  # differs from the next only in the top six bits
        0x0000_0000_0000_0001 | (1 << 63),
    ],
    dtype=np.uint64,
)


def test_summing_pairs_preserves_the_whole_64_bit_key():
    action = np.zeros(len(HIGH_BIT_KEYS), dtype=np.uint8)
    info, _, regret, _ = sum_by_pair(
        HIGH_BIT_KEYS, action, np.ones(len(HIGH_BIT_KEYS)), np.ones(len(HIGH_BIT_KEYS))
    )
    assert set(info.tolist()) == set(HIGH_BIT_KEYS.tolist())
    assert regret.sum() == len(HIGH_BIT_KEYS)


def test_keys_differing_only_in_their_top_bits_stay_distinct():
    a = np.uint64(0x0000_0000_0000_00FF)
    b = np.uint64(0xFC00_0000_0000_00FF)  # same low 58 bits
    info = np.array([a, b], dtype=np.uint64)
    action = np.zeros(2, dtype=np.uint8)
    out_info, _, regret, _ = sum_by_pair(info, action, np.array([1.0, 2.0]), np.zeros(2))
    assert len(out_info) == 2, "the two keys were merged into one"
    assert sorted(regret.tolist()) == [1.0, 2.0]


def test_the_same_key_with_different_actions_stays_separate():
    info = np.array([7, 7, 7], dtype=np.uint64)
    action = np.array([0, 1, 1], dtype=np.uint8)
    out_info, out_action, regret, _ = sum_by_pair(
        info, action, np.array([1.0, 2.0, 3.0]), np.zeros(3)
    )
    assert list(zip(out_info.tolist(), out_action.tolist())) == [(7, 0), (7, 1)]
    assert regret.tolist() == [1.0, 5.0]


def test_duplicate_pairs_are_summed():
    info = np.array([5, 5], dtype=np.uint64)
    action = np.array([2, 2], dtype=np.uint8)
    _, _, regret, strategy = sum_by_pair(
        info, action, np.array([1.5, 2.5]), np.array([10.0, 1.0])
    )
    assert regret.tolist() == [4.0]
    assert strategy.tolist() == [11.0]


def test_summing_an_empty_table_is_not_an_error():
    out = sum_by_pair(
        np.zeros(0, np.uint64), np.zeros(0, np.uint8), np.zeros(0), np.zeros(0)
    )
    assert all(len(a) == 0 for a in out)


def test_the_merge_is_independent_of_the_order_shards_arrive_in():
    rng = random.Random(0)
    info = np.array([rng.getrandbits(64) for _ in range(400)], dtype=np.uint64)
    action = np.array([rng.randrange(40) for _ in range(400)], dtype=np.uint8)
    regret = np.arange(400, dtype=np.float64)
    strategy = np.arange(400, dtype=np.float64) * 2

    with tempfile.TemporaryDirectory() as d:
        paths = []
        for i in range(4):
            s = slice(i * 100, (i + 1) * 100)
            path = os.path.join(d, f"shard{i}.npz")
            save_shard(path, info[s], action[s], regret[s], strategy[s])
            paths.append(path)
        forward = merge_shards(paths)
        backward = merge_shards(list(reversed(paths)))

    for a, b in zip(forward, backward):
        assert np.array_equal(a, b)
    # float32 on disk, so compare the totals loosely.
    assert forward[2].sum() == pytest.approx(regret.sum(), rel=1e-5)
    assert forward[3].sum() == pytest.approx(strategy.sum(), rel=1e-5)


def test_a_policy_survives_a_save_and_load_with_high_bit_keys():
    action = np.arange(len(HIGH_BIT_KEYS), dtype=np.uint8)
    policy = from_arrays(
        HIGH_BIT_KEYS, action, np.ones(len(HIGH_BIT_KEYS)), "tiny", meta={"n": 1}
    )
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "p.npz")
        policy.save(path)
        loaded = Policy.load(path)
    assert loaded.level == "tiny"
    for key in HIGH_BIT_KEYS.tolist():
        assert loaded.lookup(key) is not None, f"lost key {key:#x}"


def test_a_full_training_round_trip_keeps_every_key_it_trained_on():
    """The end-to-end guard: train, merge, export, then look up what was
    trained. This is the check the truncation bug walked straight past."""
    from cfr.abstraction import actions_for, canonical_moves, key_for, slot_key
    from cfr.mccfr import GameSpec, RegretTable, traverse
    from cfr.train import accumulate, run_round, sample_root

    class Args:
        pass

    table = RegretTable()
    rng = random.Random(1)
    spec = GameSpec(
        actions=lambda s, seat: actions_for(s, seat, "tiny"),
        key=lambda s, seat: key_for(s, seat, "tiny"),
        utility=lambda s, seat: s.utility(seat & 1),
    )
    for i in range(150):
        sim = sample_root(rng, 0.125)
        for tr in range(4):
            traverse(sim, tr, table, rng, spec, slot_key, weight=float(i + 1))

    trained = set(
        np.unique(np.frombuffer(table.info, dtype=np.uint64, count=len(table))).tolist()
    )
    delta = table.deltas()
    checkpoint = accumulate(None, delta + (0,))
    checkpoint = accumulate(checkpoint, delta + (0,))  # a second round
    policy = from_arrays(checkpoint[0], checkpoint[1], checkpoint[3], "tiny")

    held = set(np.unique(policy.info).tolist())

    # Every infoset that accumulated averaging weight must survive export.
    # Ones that only ever saw regret updates -- visited as the traverser and
    # never averaged over -- carry no strategy and are dropped on purpose.
    info, _, _, strategy = checkpoint
    with_mass = set(np.unique(info[strategy > 0.0]).tolist())
    assert with_mass, "the round produced no averaging weight at all"
    assert with_mass <= held, (
        f"{len(with_mass - held):,} infosets with strategy mass were lost on export"
    )

    covered = len(trained & held) / len(trained)
    assert covered > 0.85, f"only {covered:.1%} of trained infosets survived export"
