"""A bot that plays a policy trained by cfr/train.py.

The trained table is keyed on the abstracted information set, so at each turn
the bot rebuilds the position the trainer would have seen -- from the public
context plus its own tiles, never anything hidden -- looks the key up, and
plays from the stored distribution.

A trained table cannot cover every position: the abstraction saturates on the
lines that come up, and rare positions are pruned at export because a strategy
averaged over three visits is noise. On a miss the bot falls back to the
heuristic GreedyBot, which is a real player rather than a random one, so a
gap in coverage costs accuracy instead of the hand.
"""

import os
import random

from dominoes.bots import BotBase
from dominoes.rules import legal_moves_for_hand

from cfr.abstraction import actions_for, key_for
from cfr.engine import LEFT, RIGHT, START, TILE_ID, TILE_MASK, HandSim
from cfr.policy import Policy

DEFAULT_POLICY = os.path.join(os.path.dirname(__file__), "cfr_policy.npz")

_END_LABEL = {LEFT: "left", RIGHT: "right", START: "start"}


def sim_from_context(hand, ends, context) -> tuple[HandSim, int]:
    """Rebuild the trainer's view of this position from what a bot may see.

    Opponent hands are stand-in masks with the right number of bits: the
    abstraction only ever reads their popcount, never which tiles they are.
    """
    seat = context["player_id"]
    own = 0
    for tile in hand:
        own |= TILE_MASK[TILE_ID[(tile.a, tile.b)]]

    counts = context["hand_counts"]
    masks = [
        own if i == seat else ((1 << counts[i]) - 1) for i in range(4)
    ]
    sim = HandSim(masks, starter=seat, forced_open=False)
    sim.cp = seat
    if ends is not None:
        sim.left, sim.right = ends

    voids = [0, 0, 0, 0]
    for i, numbers in enumerate(context["known_voids"]):
        for n in numbers:
            voids[i] |= 1 << n
    sim.voids = voids

    seen = [0] * 7
    for tile in context["board"]:
        seen[tile.a] += 1
        seen[tile.b] += 1
    sim.seen = seen

    forced = context["forced_tile"]
    sim.forced = TILE_ID[(forced.a, forced.b)] if forced is not None else -1
    return sim, seat


class CFRBot(BotBase):
    """Plays a trained CFR policy, falling back to GreedyBot on a miss."""

    def __init__(self, policy=None, sample: bool = False, seed=None):
        """`sample` draws from the average strategy instead of playing its mode.

        Playing the mode is the default because it measurably wins more: 56.4%
        against GreedyBot versus 49.5% sampling, on the same policy and seeds.
        Mixing is what makes an equilibrium strategy unexploitable, but that
        only pays against an opponent adapting to you. Against fixed opponents
        it just adds noise to a decision the table has already made.
        """
        from .greedy_bot import GreedyBot

        if policy is None:
            policy = DEFAULT_POLICY
        self.policy = Policy.load(policy) if isinstance(policy, str) else policy
        self.sample = sample
        self.rng = random.Random(seed)
        self.fallback = GreedyBot()
        self.hits = 0
        self.misses = 0

    def choose_move(self, hand, ends, context=None):
        legal = legal_moves_for_hand(hand, ends)
        if not legal:
            return None
        if context is None:
            self.misses += 1
            return self.fallback.choose_move(hand, ends, context)

        sim, seat = sim_from_context(hand, ends, context)
        ids, groups = actions_for(sim, seat, self.policy.level)
        if not ids:
            self.misses += 1
            return self.fallback.choose_move(hand, ends, context)

        entry = self.policy.lookup(key_for(sim, seat, self.policy.level))
        if entry is None:
            self.misses += 1
            return self.fallback.choose_move(hand, ends, context)

        actions, probs = entry
        # Keep only what is legal here: the key is an abstraction, so a stored
        # action can belong to a different position folded into the same key.
        allowed = {a: i for i, a in enumerate(ids)}
        weights = [
            (allowed[int(a)], float(p))
            for a, p in zip(actions, probs)
            if int(a) in allowed
        ]
        total = sum(w for _, w in weights)
        if total <= 0.0:
            self.misses += 1
            return self.fallback.choose_move(hand, ends, context)

        self.hits += 1
        if self.sample:
            roll = self.rng.random() * total
            acc = 0.0
            choice = weights[-1][0]
            for idx, w in weights:
                acc += w
                if roll < acc:
                    choice = idx
                    break
        else:
            choice = max(weights, key=lambda kv: kv[1])[0]

        group = groups[choice]
        tile, end = group[0] if len(group) == 1 else self.rng.choice(group)
        return self._to_domino_move(hand, tile, end, ends)

    @staticmethod
    def _to_domino_move(hand, tile_id, end, ends):
        for tile in hand:
            if TILE_ID[(tile.a, tile.b)] == tile_id:
                return (tile, _END_LABEL[end])
        raise ValueError(f"policy chose tile {tile_id}, which is not in hand")

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0
