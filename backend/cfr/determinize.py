"""Inventing worlds that are consistent with what a seat legitimately knows.

A player cannot see the other three hands. What it can see is its own tiles,
the tiles on the board, how many each opponent is holding, and -- crucially --
which numbers each has proven not to hold by passing. Everything consistent
with that is a world the hand might really be in.

Sampling those worlds and solving each one is how strong bots for trick-taking
games with no draw pile are usually built. It is not clairvoyance: the sampler
is given only the public record plus the seat's own hand, and
tests/test_determinize.py asserts that every world it produces is consistent
with that record and that the real hands are never consulted.
"""

from .engine import N_TILES, TILE_A, TILE_B, TILE_MASK, mask_tiles


def unseen_tiles(own_hand: int, board_seen: int) -> list[int]:
    """Tiles that are neither in this hand nor already played."""
    known = own_hand | board_seen
    return [t for t in range(N_TILES) if not (known >> t) & 1]


def _blocked(tile: int, voids: int) -> bool:
    return bool((voids >> TILE_A[tile]) & 1 or (voids >> TILE_B[tile]) & 1)


def sample_world(pool: list[int], seats: list[int], counts: list[int],
                 voids: list[int], rng, attempts: int = 24):
    """Deal `pool` to `seats` respecting hand sizes and proven voids.

    Returns a list of hand masks aligned with `seats`, or None if no
    consistent deal was found. Tiles are placed most-constrained-first, which
    is what keeps late-hand positions -- where the voids bite hardest -- from
    failing over and over.
    """
    for _ in range(attempts):
        order = list(pool)
        rng.shuffle(order)
        # Deal the tiles nobody may hold last; place the fussiest tiles first.
        order.sort(key=lambda t: sum(0 if _blocked(t, voids[i]) else 1 for i in range(len(seats))))
        remaining = list(counts)
        hands = [0] * len(seats)
        ok = True
        for tile in order:
            choices = [
                i for i in range(len(seats))
                if remaining[i] > 0 and not _blocked(tile, voids[i])
            ]
            if not choices:
                ok = False
                break
            # Prefer the seat with the most room, so capacity runs out evenly.
            rng.shuffle(choices)
            pick = max(choices, key=lambda i: remaining[i])
            hands[pick] |= TILE_MASK[tile]
            remaining[pick] -= 1
        if ok and not any(remaining):
            return hands
    return None


def sample_world_relaxed(pool, seats, counts, voids, rng):
    """A consistent world if one can be found, otherwise a plausible one.

    Voids are inferences, and a run of them can leave the constraints
    unsatisfiable for a given shuffle. Rather than fail a turn, fall back to
    ignoring them: a world that respects hand sizes is still far better than
    no world at all, and the search downstream degrades gracefully.
    """
    world = sample_world(pool, seats, counts, voids, rng)
    if world is not None:
        return world, True
    order = list(pool)
    rng.shuffle(order)
    hands = [0] * len(seats)
    cursor = 0
    for i, n in enumerate(counts):
        for tile in order[cursor:cursor + n]:
            hands[i] |= TILE_MASK[tile]
        cursor += n
    return hands, False
