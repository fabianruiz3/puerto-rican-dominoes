"""Storing and querying a trained strategy.

A run reaches millions of information sets, so the shipped policy is not a
Python dict -- that would cost hundreds of bytes an entry and a slow load. It
is three parallel arrays sorted by infoset key, queried with a binary search:
thirteen bytes an entry, and a lookup that touches two cache lines.

    info   uint64  infoset key, sorted, repeated once per action
    action uint8   action id in the 42-entry vocabulary
    prob   float32 probability of that action at that infoset
"""

from typing import Optional

import numpy as np

POLICY_VERSION = 1


class Policy:
    """A trained strategy, queried by infoset key."""

    __slots__ = ("info", "action", "prob", "level", "meta")

    def __init__(self, info, action, prob, level: str, meta: Optional[dict] = None):
        order = np.argsort(info, kind="stable")
        self.info = np.ascontiguousarray(info[order], dtype=np.uint64)
        self.action = np.ascontiguousarray(action[order], dtype=np.uint8)
        self.prob = np.ascontiguousarray(prob[order], dtype=np.float32)
        self.level = level
        self.meta = meta or {}

    def __len__(self) -> int:
        return len(self.info)

    @property
    def n_infosets(self) -> int:
        return int(np.unique(self.info).size)

    def lookup(self, key: int) -> Optional[tuple[np.ndarray, np.ndarray]]:
        """(actions, probabilities) at `key`, or None if it was never trained."""
        k = np.uint64(key)
        lo = int(np.searchsorted(self.info, k, side="left"))
        if lo >= self.info.size or self.info[lo] != k:
            return None
        hi = int(np.searchsorted(self.info, k, side="right"))
        return self.action[lo:hi], self.prob[lo:hi]

    def save(self, path: str) -> None:
        np.savez_compressed(
            path,
            info=self.info,
            action=self.action,
            prob=self.prob,
            level=np.array(self.level),
            version=np.array(POLICY_VERSION),
            meta=np.array(repr(self.meta)),
        )

    @classmethod
    def load(cls, path: str) -> "Policy":
        with np.load(path, allow_pickle=False) as data:
            version = int(data["version"])
            if version != POLICY_VERSION:
                raise ValueError(
                    f"policy {path} is version {version}, expected {POLICY_VERSION}"
                )
            meta = {}
            if "meta" in data:
                try:
                    meta = eval(str(data["meta"]), {"__builtins__": {}}, {})
                except Exception:
                    meta = {}
            return cls(
                data["info"], data["action"], data["prob"], str(data["level"]), meta
            )


def from_table(table, level: str, min_mass: float = 0.0, meta=None) -> Policy:
    """Normalise a RegretTable's accumulated strategy into a Policy.

    Information sets whose total averaging weight is at or below `min_mass`
    are dropped, including any that never accumulated weight at all. Those were
    reached rarely and their strategy is still near uniform, so storing them
    costs memory to say nothing -- and the bot's heuristic fallback handles a
    lookup miss at least as well as a near-uniform entry would.
    """
    n = len(table)
    info = np.frombuffer(table.info, dtype=np.uint64, count=n).copy()
    action = np.frombuffer(table.action, dtype=np.uint8, count=n).copy()
    strategy = np.frombuffer(table.strategy, dtype=np.float64, count=n).copy()
    return from_arrays(info, action, strategy, level, min_mass, meta)


def from_arrays(info, action, strategy, level, min_mass=0.0, meta=None) -> Policy:
    """Normalise raw (infoset, action, accumulated weight) triples."""
    info = np.asarray(info, dtype=np.uint64)
    action = np.asarray(action, dtype=np.uint8)
    strategy = np.asarray(strategy, dtype=np.float64)

    order = np.lexsort((action, info))
    info, action, strategy = info[order], action[order], strategy[order]

    uniq, start, counts = np.unique(info, return_index=True, return_counts=True)
    totals = np.add.reduceat(strategy, start) if len(start) else np.zeros(0)

    keep_infoset = totals > max(min_mass, 0.0)
    if not keep_infoset.any():
        return Policy(
            np.zeros(0, np.uint64), np.zeros(0, np.uint8), np.zeros(0, np.float32),
            level, meta,
        )
    per_row_total = np.repeat(np.where(totals > 0.0, totals, 1.0), counts)
    prob = (strategy / per_row_total).astype(np.float32)
    keep = np.repeat(keep_infoset, counts) & (prob > 0.0)
    return Policy(info[keep], action[keep], prob[keep], level, meta)


def merge_shards(paths: list[str]) -> tuple:
    """Sum raw (info, action, regret, strategy) shards from parallel workers.

    Regrets and strategy sums are both accumulations over iterations, so
    summing what independent workers produced is the standard way to run CFR
    across machines. Returns arrays ready for another round or for from_arrays.
    """
    infos, actions, regrets, strategies = [], [], [], []
    for path in paths:
        with np.load(path, allow_pickle=False) as data:
            infos.append(data["info"])
            actions.append(data["action"])
            regrets.append(data["regret"])
            strategies.append(data["strategy"])
    if not infos:
        empty = np.zeros(0)
        return (
            empty.astype(np.uint64),
            empty.astype(np.uint8),
            empty,
            empty,
        )

    info = np.concatenate(infos)
    action = np.concatenate(actions)
    regret = np.concatenate(regrets).astype(np.float64)
    strategy = np.concatenate(strategies).astype(np.float64)

    # Join on (infoset, action). np.unique over a composite key keeps the
    # merge order-independent, so shards can arrive in any order.
    composite = (info.astype(np.uint64) << np.uint64(6)) | action.astype(np.uint64)
    uniq, inverse = np.unique(composite, return_inverse=True)
    out_regret = np.zeros(uniq.size)
    out_strategy = np.zeros(uniq.size)
    np.add.at(out_regret, inverse, regret)
    np.add.at(out_strategy, inverse, strategy)
    return (
        (uniq >> np.uint64(6)).astype(np.uint64),
        (uniq & np.uint64(63)).astype(np.uint8),
        out_regret,
        out_strategy,
    )


def save_shard(path, info, action, regret, strategy) -> None:
    np.savez(
        path,
        info=np.asarray(info, dtype=np.uint64),
        action=np.asarray(action, dtype=np.uint8),
        regret=np.asarray(regret, dtype=np.float32),
        strategy=np.asarray(strategy, dtype=np.float32),
    )
