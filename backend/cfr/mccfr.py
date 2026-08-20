"""External-sampling Monte Carlo CFR.

At a node belonging to the traverser every action is expanded; at every other
node one action is sampled from the current strategy. Regrets are written at
the traverser's nodes, the average strategy is accumulated at everyone else's.
That is Lanctot's external sampling, and it suits this game: the traverser
branches only ~2.5 ways and acts ~5.6 times a hand, so a full traversal costs
around 155 leaf paths.

A caveat worth stating plainly. CFR's convergence guarantee is for two-player
zero-sum games. Teams dominoes is zero-sum between the two teams, but a team is
two seats that cannot see each other's tiles, so it is not a two-player game
and no equilibrium guarantee carries over. CFR is used here as a strong
self-play procedure, the same way it is used for bridge and other partnership
games -- the evidence that it works is the arena win rate, not a theorem.

The traversal is generic over a small game interface so that the exact code
that trains the dominoes bot can also be run against games whose solutions are
known in closed form. tests/test_mccfr.py does that with Rock-Paper-Scissors
and Kuhn poker; without such a check a subtly wrong CFR would just look like a
mediocre bot.
"""

from array import array
from typing import Callable, NamedTuple

import numpy as _np


class GameSpec(NamedTuple):
    """How the traversal talks to a game.

    actions(game, seat) -> (action_ids, groups); each group holds the concrete
        moves sharing an id, played uniformly when there is more than one.
    key(game, seat)     -> the abstracted information set id.
    utility(game, seat) -> signed payoff for `seat` at a terminal node.
    """

    actions: Callable
    key: Callable
    utility: Callable


class BaseTable:
    """Regret carried in from previous training rounds, held read-only.

    Two sorted numpy arrays rather than a dict, because worker processes are
    forked and a Python dict is not copy-on-write friendly: merely reading it
    touches per-object refcounts and the pages get copied into every worker. A
    numpy array is one object, so reading it shares. A lookup costs a binary
    search, but only on a slot's first touch in a round -- after that the
    worker's own dict caches the index.
    """

    __slots__ = ("slots", "regret")

    def __init__(self, slots=None, regret=None):
        self.slots = slots
        self.regret = regret

    def __len__(self) -> int:
        return 0 if self.slots is None else len(self.slots)

    def regret_of(self, slot: int) -> float:
        if self.slots is None or len(self.slots) == 0:
            return 0.0
        key = _np.uint64(slot)
        i = int(_np.searchsorted(self.slots, key))
        if i < self.slots.size and self.slots[i] == key:
            return float(self.regret[i])
        return 0.0


class RegretTable:
    """Cumulative regret and strategy, one slot per (infoset, action).

    Storing per pair rather than per infoset keeps memory proportional to the
    pairs actually visited -- most infosets offer two or three of the 42
    vocabulary actions -- and makes merging shards a join on one integer key.

    array('d') rather than a list of floats: eight bytes a slot instead of
    thirty-two, and indexing still yields a plain Python float.

    With a `base`, the table holds one round's *delta*: a slot's regret starts
    at whatever previous rounds accumulated (regret matching needs the running
    total) while its strategy weight starts at zero, and `deltas()` subtracts
    the carried-in value back out so shards can simply be summed.
    """

    __slots__ = ("slots", "regret", "strategy", "info", "action", "origin", "base")

    def __init__(self, base: "BaseTable | None" = None):
        self.slots: dict[int, int] = {}
        self.regret = array("d")
        self.strategy = array("d")
        self.info = array("Q")  # infoset key per slot, for export
        self.action = array("B")  # action id per slot, for export
        self.origin = array("d")  # regret carried in, subtracted back out
        self.base = base

    def __len__(self) -> int:
        return len(self.regret)

    def index(self, slot: int, info: int, action: int) -> int:
        idx = self.slots.get(slot)
        if idx is None:
            idx = len(self.regret)
            self.slots[slot] = idx
            carried = 0.0 if self.base is None else self.base.regret_of(slot)
            self.regret.append(carried)
            self.origin.append(carried)
            self.strategy.append(0.0)
            self.info.append(info)
            self.action.append(action)
        return idx

    def deltas(self):
        """(info, action, regret_delta, strategy_delta) as numpy arrays."""
        n = len(self.regret)
        info = _np.frombuffer(self.info, dtype=_np.uint64, count=n).copy()
        action = _np.frombuffer(self.action, dtype=_np.uint8, count=n).copy()
        regret = _np.frombuffer(self.regret, dtype=_np.float64, count=n)
        origin = _np.frombuffer(self.origin, dtype=_np.float64, count=n)
        strategy = _np.frombuffer(self.strategy, dtype=_np.float64, count=n).copy()
        return info, action, (regret - origin), strategy


def regret_matching(regret: array, idxs: list[int]) -> list[float]:
    """Strategy proportional to positive regret; uniform when there is none."""
    total = 0.0
    positive = []
    for ix in idxs:
        r = regret[ix]
        if r > 0.0:
            positive.append(r)
            total += r
        else:
            positive.append(0.0)
    if total > 0.0:
        return [p / total for p in positive]
    share = 1.0 / len(idxs)
    return [share] * len(idxs)


def _sample(strategy: list[float], roll: float) -> int:
    acc = 0.0
    for i, p in enumerate(strategy):
        acc += p
        if roll < acc:
            return i
    return len(strategy) - 1


def traverse(
    game,
    traverser: int,
    table: RegretTable,
    rng,
    spec: GameSpec,
    slot_key: Callable[[int, int], int],
    weight: float = 1.0,
    clamp_regret: bool = True,
) -> float:
    """One external-sampling traversal. Returns the traverser's payoff.

    `weight` scales the average-strategy accumulation, so a caller can apply
    linear averaging by passing the round number -- later, better-informed
    strategies then dominate the average.

    `clamp_regret` floors cumulative regret at zero (the CFR+ trick). It costs
    nothing and in practice reaches a good strategy far sooner, at the price of
    the plain-CFR bound -- which this game does not enjoy regardless.
    """
    if game.is_terminal():
        return spec.utility(game, traverser)

    seat = game.cp
    ids, groups = spec.actions(game, seat)
    if not ids:
        game.apply(None)
        value = traverse(
            game, traverser, table, rng, spec, slot_key, weight, clamp_regret
        )
        game.undo(None)
        return value

    info = spec.key(game, seat)
    idxs = [table.index(slot_key(info, a), info, a) for a in ids]
    strategy = regret_matching(table.regret, idxs)

    if seat == traverser:
        utils = [0.0] * len(ids)
        node_value = 0.0
        for i, group in enumerate(groups):
            move = group[0] if len(group) == 1 else rng.choice(group)
            game.apply(move)
            utils[i] = traverse(
                game, traverser, table, rng, spec, slot_key, weight, clamp_regret
            )
            game.undo(move)
            node_value += strategy[i] * utils[i]
        regret = table.regret
        if clamp_regret:
            for i, ix in enumerate(idxs):
                r = regret[ix] + utils[i] - node_value
                regret[ix] = r if r > 0.0 else 0.0
        else:
            for i, ix in enumerate(idxs):
                regret[ix] += utils[i] - node_value
        return node_value

    accum = table.strategy
    for i, ix in enumerate(idxs):
        accum[ix] += weight * strategy[i]
    choice = _sample(strategy, rng.random())
    group = groups[choice]
    move = group[0] if len(group) == 1 else rng.choice(group)
    game.apply(move)
    value = traverse(
        game, traverser, table, rng, spec, slot_key, weight, clamp_regret
    )
    game.undo(move)
    return value


def average_strategy(table: RegretTable) -> dict[int, dict[int, float]]:
    """Normalise the accumulated strategy into infoset -> {action: prob}.

    Slots that only ever saw regret updates and never an averaging visit carry
    zero mass; an infoset with no mass at all falls back to uniform over the
    actions it was seen to have, which is the best available answer for a
    position the traverser reached but never had to average over.
    """
    totals: dict[int, float] = {}
    seen: dict[int, list[int]] = {}
    strategy = table.strategy
    for slot_idx in range(len(table.regret)):
        info = table.info[slot_idx]
        totals[info] = totals.get(info, 0.0) + strategy[slot_idx]
        seen.setdefault(info, []).append(slot_idx)

    out: dict[int, dict[int, float]] = {}
    for info, slot_idxs in seen.items():
        total = totals[info]
        if total > 0.0:
            out[info] = {
                table.action[i]: strategy[i] / total
                for i in slot_idxs
                if strategy[i] > 0.0
            }
        else:
            share = 1.0 / len(slot_idxs)
            out[info] = {table.action[i]: share for i in slot_idxs}
    return out
