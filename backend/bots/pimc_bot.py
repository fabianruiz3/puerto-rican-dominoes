"""A bot that reasons about the hands it cannot see.

It never looks at anyone else's tiles. At each turn it takes what it is
entitled to know -- its own hand, the board, how many tiles each opponent
holds, and the numbers each has proven void by passing -- invents a set of
deals consistent with all of that, solves each one exactly, and plays the move
that does best averaged over them.

This is determinization, the standard approach for trick-taking games where
every card is dealt and nothing is drawn: the uncertainty is entirely about
who holds what, so sampling who holds what turns one hard problem into many
easy ones. Its known weakness is that it assumes the uncertainty resolves at
once, so it will not deliberately play to gather information; in exchange it
searches concretely instead of interpolating over an abstraction.

The opposing seats are modelled as playing the heuristic, and so is the
partner -- the partner's real strategy is not available to it any more than
the partner's tiles are.
"""

import random

from dominoes.bots import BotBase
from dominoes.rules import legal_moves_for_hand

from cfr.determinize import sample_world_relaxed, unseen_tiles
from cfr.engine import LEFT, RIGHT, START, TILE_A, TILE_B, TILE_ID, TILE_MASK, HandSim
from cfr.oracle import best_response_value, new_played

_END_LABEL = {LEFT: "left", RIGHT: "right", START: "start"}


class PIMCBot(BotBase):
    """Perfect-information Monte Carlo over deals consistent with the record."""

    def __init__(self, worlds: int = 12, seed=None, fallback=None):
        self.worlds = worlds
        self.rng = random.Random(seed)
        if fallback is None:
            from .greedy_bot import GreedyBot

            fallback = GreedyBot()
        self.fallback = fallback
        self.consistent = 0
        self.relaxed = 0

    def choose_move(self, hand, ends, context=None):
        forced = (context or {}).get("forced_tile")
        legal = legal_moves_for_hand(hand, ends, forced)
        if not legal:
            return None
        if len(legal) == 1:
            return legal[0]
        if context is None:
            return self.fallback.choose_move(hand, ends, context)

        seat = context["player_id"]
        own = 0
        for tile in hand:
            own |= TILE_MASK[TILE_ID[(tile.a, tile.b)]]

        board_seen = 0
        seen = [0] * 7
        for tile in context["board"]:
            board_seen |= TILE_MASK[TILE_ID[(tile.a, tile.b)]]
            seen[tile.a] += 1
            seen[tile.b] += 1

        others = [(seat + 1) & 3, (seat + 2) & 3, (seat + 3) & 3]
        counts = [context["hand_counts"][s] for s in others]
        voids = []
        for s in others:
            mask = 0
            for n in context["known_voids"][s]:
                mask |= 1 << n
            voids.append(mask)

        # Who has laid down which numbers, for the heuristic model.
        played = new_played()
        for move in context["move_history"]:
            if move["tile"] is None:
                continue
            a, b = move["tile"]
            played[move["player"]][a] += 1
            played[move["player"]][b] += 1

        pool = unseen_tiles(own, board_seen)
        if sum(counts) != len(pool):
            # The record and the tile count disagree; not a position this can
            # reason about, so defer rather than invent something wrong.
            return self.fallback.choose_move(hand, ends, context)

        own_voids = 0
        for n in context["known_voids"][seat]:
            own_voids |= 1 << n

        totals = [0.0] * len(legal)
        for _ in range(self.worlds):
            world, exact = sample_world_relaxed(pool, others, counts, voids, self.rng)
            if exact:
                self.consistent += 1
            else:
                self.relaxed += 1

            hands = [0, 0, 0, 0]
            hands[seat] = own
            for s, h in zip(others, world):
                hands[s] = h

            for i, (tile, end) in enumerate(legal):
                sim = HandSim(hands, seat, forced_open=False)
                sim.cp = seat
                sim.seen = list(seen)
                sim.voids = [0, 0, 0, 0]
                for s, mask in zip(others, voids):
                    sim.voids[s] = mask
                sim.voids[seat] = own_voids
                if ends is not None:
                    sim.left, sim.right = ends

                tile_id = TILE_ID[(tile.a, tile.b)]
                engine_end = START if end == "start" else (LEFT if end == "left" else RIGHT)
                mine = list(played)
                mine[seat] = list(played[seat])
                mine[seat][TILE_A[tile_id]] += 1
                mine[seat][TILE_B[tile_id]] += 1
                sim.apply((tile_id, engine_end))
                totals[i] += best_response_value(sim, seat, mine)

        best = max(range(len(legal)), key=lambda i: totals[i])
        return legal[best]

    @property
    def consistency_rate(self) -> float:
        total = self.consistent + self.relaxed
        return self.consistent / total if total else 0.0
