"""Fuzz the hand loop and assert the things CFR will rely on.

CFR trains against a simulator; if the simulator drifts from the rules the
policy is optimal for a game nobody plays. These run every hand of many random
matches through a full invariant check.
"""

import random

import pytest

from bots.arena import run_single_match
from bots.greedy_bot import GreedyBot
from bots.random_bot import RandomBot
from dominoes.rules import team_for_player
from dominoes.tiles import generate_double_six_set
from dominoes.types import GameMode, MatchConfig

CONFIG = MatchConfig(target_points=200, mode=GameMode.TEAMS)
FULL_SET = sorted((t.a, t.b) for t in generate_double_six_set())


def played_tiles(hand_rec):
    return [(m.tile_a, m.tile_b) for m in hand_rec.moves if m.end != "pass"]


def norm(t):
    return (min(t), max(t))


@pytest.fixture(scope="module")
def matches():
    random.seed(20260820)
    bots = [GreedyBot(), RandomBot(), GreedyBot(), RandomBot()]
    return [run_single_match(bots, CONFIG, i) for i in range(60)]


def test_every_deal_uses_the_full_double_six_set_exactly_once(matches):
    for m in matches:
        for h in m.hands:
            dealt = sorted(norm(t) for hand in h.starting_hands for t in hand)
            assert dealt == FULL_SET
            assert all(len(hand) == 7 for hand in h.starting_hands)


def test_no_tile_is_played_twice_and_every_play_came_from_that_seats_hand(matches):
    for m in matches:
        for h in m.hands:
            played = [norm(t) for t in played_tiles(h)]
            assert len(played) == len(set(played)), "a tile was played twice"
            owner = {}
            for seat, hand in enumerate(h.starting_hands):
                for t in hand:
                    owner[norm(t)] = seat
            for mv in h.moves:
                if mv.end == "pass":
                    continue
                assert owner[norm((mv.tile_a, mv.tile_b))] == mv.player


def test_the_final_layout_is_a_connected_chain_matching_the_reported_ends(matches):
    for m in matches:
        for h in m.hands:
            layout = h.final_layout
            if not layout:
                continue
            for left, right in zip(layout, layout[1:]):
                assert left[1] == right[0], f"broken chain at {left} -> {right}"
            assert h.final_ends == (layout[0][0], layout[-1][1])


def test_a_seat_only_passes_when_it_truly_has_nothing_to_play(matches):
    for m in matches:
        for h in m.hands:
            remaining = [set(norm(t) for t in hand) for hand in h.starting_hands]
            ends = None
            for mv in h.moves:
                if mv.end == "pass":
                    assert ends is not None, "cannot pass on an empty board"
                    left, right = ends
                    for a, b in remaining[mv.player]:
                        assert left not in (a, b) and right not in (a, b), (
                            f"seat {mv.player} passed holding {a}|{b} on ends {ends}"
                        )
                    continue
                tile = norm((mv.tile_a, mv.tile_b))
                remaining[mv.player].discard(tile)
                if ends is None:
                    ends = (mv.tile_a, mv.tile_b)
                else:
                    left, right = ends
                    a, b = mv.tile_a, mv.tile_b
                    if mv.end == "left":
                        assert left in (a, b)
                        ends = (b, right) if a == left else (a, right)
                    else:
                        assert right in (a, b)
                        ends = (left, b) if a == right else (left, a)


def test_the_first_hand_of_a_match_is_opened_with_the_double_six(matches):
    for m in matches:
        first = m.hands[0]
        opener = first.moves[0]
        assert (opener.tile_a, opener.tile_b) == (6, 6)
        assert opener.player == first.first_player
        assert (6, 6) in [norm(t) for t in first.starting_hands[first.first_player]]


def test_later_hands_are_opened_by_whoever_won_the_previous_one(matches):
    for m in matches:
        for prev, nxt in zip(m.hands, m.hands[1:]):
            assert nxt.first_player == prev.next_starter
            assert nxt.first_player == prev.winner


def test_a_domino_out_win_means_that_seat_emptied_its_hand(matches):
    for m in matches:
        for h in m.hands:
            if h.blocked:
                continue
            played_by_winner = sum(
                1 for mv in h.moves if mv.player == h.winner and mv.end != "pass"
            )
            assert played_by_winner == 7


def test_a_tranque_ends_on_four_straight_passes_with_nobody_out(matches):
    seen_tranque = False
    for m in matches:
        for h in m.hands:
            if not h.blocked:
                continue
            seen_tranque = True
            assert [mv.end for mv in h.moves[-4:]] == ["pass"] * 4
            for seat in range(4):
                played = sum(
                    1 for mv in h.moves if mv.player == seat and mv.end != "pass"
                )
                assert played < 7
    assert seen_tranque, "fuzz corpus never produced a tranque"


def test_points_go_to_both_seats_of_exactly_one_team(matches):
    for m in matches:
        for h in m.hands:
            pts = h.points_earned
            winning_team = team_for_player(h.winner)
            winners = [0, 2] if winning_team == 0 else [1, 3]
            losers = [1, 3] if winning_team == 0 else [0, 2]
            assert pts[winners[0]] == pts[winners[1]] > 0
            assert pts[losers[0]] == pts[losers[1]] == 0


def test_the_next_starter_is_always_on_the_team_that_won(matches):
    for m in matches:
        for h in m.hands:
            assert team_for_player(h.next_starter) == team_for_player(h.winner)


def test_final_scores_are_the_sum_of_the_hand_awards(matches):
    for m in matches:
        totals = [0, 0, 0, 0]
        for h in m.hands:
            for seat in range(4):
                totals[seat] += h.points_earned[seat]
        assert totals == m.final_scores


def test_a_match_stops_as_soon_as_a_team_reaches_the_target(matches):
    for m in matches:
        assert max(m.final_scores) >= CONFIG.target_points
        before = [0, 0, 0, 0]
        for h in m.hands[:-1]:
            for seat in range(4):
                before[seat] += h.points_earned[seat]
        assert max(before) < CONFIG.target_points, "match ran past the target"
