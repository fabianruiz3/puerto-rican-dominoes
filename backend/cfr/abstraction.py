"""Compressing a position into the information set CFR actually learns about.

The raw game has C(28,7)*C(21,7)*C(14,7) = 4.7e14 deals, so a table keyed on
the literal position would be a record of things seen once and never again.
Two separate compressions happen here.

**Actions** map to a small global vocabulary. Away from the opening a move is
identified by which canonical end it attaches to and which pip it leaves
exposed -- and that pair already names the tile, since joining a known end and
exposing a known pip determines it. That gives 2*7 placement actions, plus one
opening action per tile, 42 in all. The vocabulary is global: action id 9 means
the same thing at every key, so regrets stay comparable across visits even
though the legal subset changes. Encoding the *legal set* into the key instead
was measured at 0.90 distinct keys per visit -- every position unique, nothing
learned -- because the set of moves you can make betrays your whole hand.

**States** keep the board, the seat sizes, what each opponent has shown void
in, and a description of the acting hand relative to the two open ends. Two
levels are provided; measured growth over random play (visits per distinct
key, higher is better for convergence):

    hands       25k     50k    100k    200k
    STANDARD    1.5     1.8     2.1     2.5
    COARSE      2.8     3.5     4.4     5.8

Both are sublinear and still climbing at 200k hands, so both saturate; COARSE
trades hand-shape detail for many more visits per infoset.

Two invariants are enforced in tests/test_cfr_abstraction.py:

  * A key depends only on public state and the acting seat's own hand -- never
    on another seat's tiles. Leaking hidden information would let CFR converge
    to a policy that cannot be played.
  * Board orientation is canonicalised. Which end is "left" is arbitrary, so
    the ends are sorted and action sides flipped to match, folding every
    position together with its mirror image.
"""

from .engine import (
    DOUBLE_MASK,
    LEFT,
    RIGHT,
    SLOTS_PER_NUMBER,
    START,
    TILE_A,
    TILE_B,
    TILE_IS_DOUBLE,
    mask_pips,
    mask_tiles,
    other_pip,
)

# --------------------------------------------------------- action vocabulary
#
# The vocabulary has to be labelled the same way the state key is. A key that
# has forgotten which number an end carries cannot be paired with an action
# that names one: positions with unrelated pips fold onto the same key, and the
# stored actions are then illegal in nearly all of them. Measured, that failure
# looks like a policy that never fires -- 14 usable lookups out of 12,533.
#
# So there are two vocabularies, chosen by level:
#
#   LABELLED (standard, coarse)  side x exposed pip, plus one id per opening
#                                tile. Injective: an id names exactly one move.
#   SYMMETRIC (compact, tiny)    canonical end slot x is-double x tile weight x
#                                whether the exposed pip stays covered. Several
#                                moves can share an id, and the group is played
#                                uniformly.
#
# Both stay under 64 ids so that (infoset, action) packs into one integer for
# the shard merge.

N_PLACEMENT_ACTIONS = 14  # labelled: canonical side (2) x exposed pip (7)
N_OPENING_ACTIONS = 28  # labelled: one per tile, for a free lead
ACTION_COUNT = 64  # vocabulary ceiling; 6 bits in the shard packing

SYM_PLACEMENT = 32  # symmetric: end slot (2) x double (2) x weight (4) x cover (2)
SYM_OPENING = 8  # symmetric: double (2) x weight (4)

STANDARD = "standard"
COARSE = "coarse"
COMPACT = "compact"
TINY = "tiny"
LEVELS = (STANDARD, COARSE, COMPACT, TINY)

NO_BOARD = 7  # end sentinel for an empty board


def cap(value: int, ceiling: int) -> int:
    return value if value < ceiling else ceiling


# ------------------------------------------------------------------ hashing

_MASK64 = (1 << 64) - 1
_SEED = 0xCBF29CE484222325


def _mix(h: int, v: int) -> int:
    """boost::hash_combine.

    Deterministic across runs, Python versions and machines -- unlike hash() on
    anything containing a str -- which matters because cluster workers and the
    local exporter must agree on every key they produce.
    """
    h ^= (v + 0x9E3779B97F4A7C15 + ((h << 6) & _MASK64) + (h >> 2)) & _MASK64
    return h & _MASK64


def slot_key(infoset: int, action: int) -> int:
    """The table key for one (infoset, action) pair."""
    return _mix(infoset, action)


def slot_keys(info, action):
    """slot_key over whole arrays.

    A round starts by deriving the slot key of every entry in the checkpoint,
    which at a hundred million entries is minutes of interpreter time done one
    call at a time. uint64 arithmetic wraps in numpy exactly as the masked
    Python version does, so this is the same function, vectorised.
    tests/test_cfr_abstraction.py pins them together.
    """
    import numpy as np

    h = np.asarray(info, dtype=np.uint64).copy()
    v = np.asarray(action, dtype=np.uint64)
    with np.errstate(over="ignore"):
        h ^= v + np.uint64(0x9E3779B97F4A7C15) + (h << np.uint64(6)) + (h >> np.uint64(2))
    return h


# ------------------------------------------------------------------ features


def _pip_bucket(pips: int) -> int:
    if pips <= 10:
        return 0
    if pips <= 20:
        return 1
    if pips <= 30:
        return 2
    return 3


def hand_profile(hand: int) -> tuple[list[int], list[int]]:
    """(tiles carrying each number, pip-slots of each number) for a hand.

    The two differ on doubles: 3|3 is one tile carrying a three but two slots
    of it, and slots are what decide whether a number can be exhausted.
    """
    tiles = [0] * 7
    slots = [0] * 7
    for t in mask_tiles(hand):
        a, b = TILE_A[t], TILE_B[t]
        slots[a] += 1
        slots[b] += 1
        tiles[a] += 1
        if b != a:
            tiles[b] += 1
    return tiles, slots


def canonical_ends(sim) -> tuple[int, int]:
    if sim.left < 0:
        return NO_BOARD, NO_BOARD
    if sim.left <= sim.right:
        return sim.left, sim.right
    return sim.right, sim.left


def canonical_moves(sim, seat: int) -> list[tuple[int, int]]:
    """Legal moves with the mirror duplicate removed.

    A tile matching both ends is reported twice, but when both ends carry the
    same number the two placements reach the same board.
    """
    moves = sim.legal(seat)
    if sim.left < 0 or sim.left != sim.right:
        return moves
    seen = set()
    out = []
    for tile, end in moves:
        if tile in seen:
            continue
        seen.add(tile)
        out.append((tile, end))
    return out


def action_id(sim, move: tuple[int, int]) -> int:
    """This move's id in the global vocabulary.

    Depends only on the move and the board -- never on the hand -- so the same
    id means the same thing wherever it appears.
    """
    tile, end = move
    if end == START:
        return N_PLACEMENT_ACTIONS + tile
    left, right = sim.left, sim.right
    matched = left if end == LEFT else right
    exposed = other_pip(tile, matched)
    if left == right:
        side = 0  # both ends carry the same number: one move, not two
    else:
        side = 1 if ((end == RIGHT) != (left > right)) else 0
    return side * 7 + exposed


def legal_actions(sim, seat: int) -> tuple[list[int], list[list[tuple[int, int]]]]:
    """(action ids, concrete moves per id) for `seat`.

    Ids are injective over canonical moves, so each group holds one move; the
    grouping is kept so a future coarser vocabulary does not need new callers.
    """
    grouped: dict[int, list[tuple[int, int]]] = {}
    for move in canonical_moves(sim, seat):
        grouped.setdefault(action_id(sim, move), []).append(move)
    ids = sorted(grouped)
    return ids, [grouped[i] for i in ids]


def _weight_bucket(pips: int) -> int:
    """Coarse weight of a single tile: 0-3, 4-6, 7-9, 10-12."""
    if pips <= 3:
        return 0
    if pips <= 6:
        return 1
    if pips <= 9:
        return 2
    return 3


def end_slots(sim, seat: int, level: str) -> dict[int, int]:
    """Which canonical slot each open end occupies, as {end_number: slot}.

    The state key and the action ids must agree on which end is "first", and
    for a pip-abstract level that ordering cannot come from pip value. It comes
    from the same profile the key sorts on. When both ends have identical
    profiles they are interchangeable under the abstraction, so both map to
    slot 0 and their moves merge -- which is correct, not a collision.
    """
    if sim.left < 0:
        return {}
    left, right = sim.left, sim.right
    if left == right:
        return {left: 0}
    if level in (STANDARD, COARSE):
        return {min(left, right): 0, max(left, right): 1}

    tiles, slots = hand_profile(sim.hands[seat])
    others = [(seat + 1) & 3, (seat + 3) & 3]
    partner = (seat + 2) & 3

    def profile(end):
        return (
            cap(tiles[end], 2),
            cap(max(0, SLOTS_PER_NUMBER - sim.seen[end] - slots[end]), 2),
            (sim.voids[partner] >> end) & 1,
            1 if any((sim.voids[o] >> end) & 1 for o in others) else 0,
        )

    pl, pr = profile(left), profile(right)
    if pl == pr:
        return {left: 0, right: 0}
    return ({left: 0, right: 1} if pl < pr else {left: 1, right: 0})


def symmetric_action_id(sim, seat: int, move: tuple[int, int], level: str) -> int:
    """A pip-abstract action id, for the levels whose keys drop pip identity."""
    tile, end = move
    is_double = 1 if TILE_IS_DOUBLE[tile] else 0
    weight = _weight_bucket(TILE_A[tile] + TILE_B[tile])
    if end == START:
        return SYM_PLACEMENT + is_double * 4 + weight

    matched = sim.left if end == LEFT else sim.right
    exposed = other_pip(tile, matched)
    slot = end_slots(sim, seat, level).get(matched, 0)
    tiles, _ = hand_profile(sim.hands[seat])
    covered = 1 if tiles[exposed] - 1 > 0 else 0
    return slot * 16 + is_double * 8 + weight * 2 + covered


def actions_for(sim, seat: int, level: str):
    """(action ids, concrete moves per id) under `level`'s vocabulary."""
    if level in (STANDARD, COARSE):
        return legal_actions(sim, seat)
    grouped: dict[int, list[tuple[int, int]]] = {}
    for move in canonical_moves(sim, seat):
        grouped.setdefault(symmetric_action_id(sim, seat, move, level), []).append(move)
    ids = sorted(grouped)
    return ids, [grouped[i] for i in ids]


def infoset_key(sim, seat: int, level: str = STANDARD) -> int:
    """The abstracted information set `seat` is looking at."""
    hand = sim.hands[seat]
    tiles, slots = hand_profile(hand)
    partner = (seat + 2) & 3
    nxt = (seat + 1) & 3
    prv = (seat + 3) & 3
    cl, cr = canonical_ends(sim)

    h = _SEED
    # Public: the board, how much each seat still holds, what they have shown.
    h = _mix(h, cl)
    h = _mix(h, cr)
    h = _mix(h, bin(hand).count("1"))
    h = _mix(h, bin(sim.hands[partner]).count("1"))
    h = _mix(h, bin(sim.hands[nxt]).count("1"))
    h = _mix(h, bin(sim.hands[prv]).count("1"))

    if cl != NO_BOARD:
        # Only the voids that bear on the current ends. Carrying the full 7-bit
        # void mask for all three seats measured no stronger and much larger.
        for other in (partner, nxt, prv):
            mask = sim.voids[other]
            h = _mix(h, ((mask >> cl) & 1) | (((mask >> cr) & 1) << 1))
        # Private: how this hand relates to the two open ends.
        h = _mix(h, cap(tiles[cl], 3))
        h = _mix(h, cap(tiles[cr], 3))
        # Slots of each end neither on the board nor in this hand: a ceiling on
        # how many answers the other three seats can still be holding.
        h = _mix(h, cap(max(0, SLOTS_PER_NUMBER - sim.seen[cl] - slots[cl]), 3))
        h = _mix(h, cap(max(0, SLOTS_PER_NUMBER - sim.seen[cr] - slots[cr]), 3))

    if level == STANDARD:
        # Hand shape: the two longest numbers held, doubles, and total weight.
        longest = sorted(tiles, reverse=True)
        h = _mix(h, cap(longest[0], 4))
        h = _mix(h, cap(longest[1], 4))
        h = _mix(h, cap(bin(hand & DOUBLE_MASK).count("1"), 3))
        h = _mix(h, _pip_bucket(mask_pips(hand)))
    return h


def compact_key(sim, seat: int) -> int:
    """A key that forgets which numbers the ends are, only what they do.

    Dominoes is very nearly symmetric under relabelling the pips: whether an
    end is a three or a five changes almost nothing about who can answer it.
    What matters is how many of it this hand holds, how many are unaccounted
    for, and whether the opponents have shown void in it. Dropping the labels
    -- the same suit-isomorphism poker solvers use -- collapses the 29 possible
    end pairs into a handful of buckets and cuts the table by more than an
    order of magnitude.

    Pip *values* still matter for scoring, so they are not thrown away
    entirely: a coarse weight bucket for the two ends stays in the key, and the
    action vocabulary is labelled, so the policy can still learn to expose a
    blank rather than a six.

    The two ends are canonicalised by their (coverage, unseen) profile rather
    than by pip value, since pip value is no longer in the key to sort on.
    """
    hand = sim.hands[seat]
    tiles, slots = hand_profile(hand)
    partner = (seat + 2) & 3
    nxt = (seat + 1) & 3
    prv = (seat + 3) & 3

    h = _SEED
    h = _mix(h, bin(hand).count("1"))
    h = _mix(h, cap(bin(sim.hands[partner]).count("1"), 4))
    h = _mix(h, cap(bin(sim.hands[nxt]).count("1"), 4))
    h = _mix(h, cap(bin(sim.hands[prv]).count("1"), 4))

    if sim.left < 0:
        h = _mix(h, 63)  # opening lead: no ends to describe
        return h

    left, right = sim.left, sim.right
    profiles = []
    for end in (left, right):
        profiles.append(
            (
                cap(tiles[end], 3),
                cap(max(0, SLOTS_PER_NUMBER - sim.seen[end] - slots[end]), 3),
                ((sim.voids[partner] >> end) & 1)
                | (((sim.voids[nxt] >> end) & 1) << 1)
                | (((sim.voids[prv] >> end) & 1) << 2),
            )
        )
    for prof in sorted(profiles):
        for field in prof:
            h = _mix(h, field)
    h = _mix(h, 1 if left == right else 0)
    h = _mix(h, _pip_bucket((left + right) * 2))  # coarse weight of the ends
    h = _mix(h, cap(bin(hand & DOUBLE_MASK).count("1"), 3))
    h = _mix(h, _pip_bucket(mask_pips(hand)))
    return h


def tiny_key(sim, seat: int) -> int:
    """The smallest level: only what a player would say out loud.

    How many tiles everyone has left, how well this hand covers each open end,
    how many answers to each end are still unaccounted for, and whether the
    partner or an opponent has shown void in it. Everything else -- pip
    identity, exact hand shape, exact opponent counts past three -- is dropped.

    The point is coverage, not resolution. A finer abstraction describes each
    position better but spreads a training run over so many information sets
    that the ones arising in real play are never visited: at COMPACT, a 36k
    traversal run covered 0.1% of the positions the bot then met in the arena.
    A policy that is roughly right about positions it recognises beats a
    precise one that recognises nothing.
    """
    hand = sim.hands[seat]
    tiles, slots = hand_profile(hand)
    partner = (seat + 2) & 3
    others = ((seat + 1) & 3, (seat + 3) & 3)

    h = _SEED
    h = _mix(h, bin(hand).count("1"))
    h = _mix(h, cap(bin(sim.hands[partner]).count("1"), 3))
    opp_counts = sorted(cap(bin(sim.hands[o]).count("1"), 3) for o in others)
    h = _mix(h, opp_counts[0])
    h = _mix(h, opp_counts[1])
    h = _mix(h, cap(bin(hand & DOUBLE_MASK).count("1"), 2))

    if sim.left < 0:
        return _mix(h, 63)  # opening lead

    profiles = []
    for end in (sim.left, sim.right):
        opp_void = 1 if any((sim.voids[o] >> end) & 1 for o in others) else 0
        profiles.append(
            (
                cap(tiles[end], 2),
                cap(max(0, SLOTS_PER_NUMBER - sim.seen[end] - slots[end]), 2),
                (sim.voids[partner] >> end) & 1,
                opp_void,
            )
        )
    for prof in sorted(profiles):
        for field in prof:
            h = _mix(h, field)
    return h


def key_for(sim, seat: int, level: str) -> int:
    if level == TINY:
        return tiny_key(sim, seat)
    if level == COMPACT:
        return compact_key(sim, seat)
    return infoset_key(sim, seat, level)
