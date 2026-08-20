import pytest

from dominoes.rules import (
    OPENING_TILE,
    canonical_moves,
    legal_moves_for_hand,
    resolve_blocked_hand,
    resulting_ends,
    team_for_player,
)
from dominoes.types import Domino, GameMode


def test_forced_opening_restricts_lead_to_the_double_six():
    hand = [Domino(6, 6), Domino(3, 5), Domino(0, 0)]
    assert legal_moves_for_hand(hand, None, OPENING_TILE) == [(Domino(6, 6), "start")]


def test_forced_opening_is_ignored_once_the_board_has_ends():
    hand = [Domino(6, 6), Domino(3, 5)]
    moves = legal_moves_for_hand(hand, (3, 6), OPENING_TILE)
    assert (Domino(3, 5), "left") in moves
    assert (Domino(6, 6), "right") in moves


def test_forced_opening_without_the_tile_falls_back_to_a_free_lead():
    hand = [Domino(3, 5), Domino(0, 0)]
    assert len(legal_moves_for_hand(hand, None, OPENING_TILE)) == 2


def test_free_lead_offers_every_tile():
    hand = [Domino(6, 6), Domino(3, 5), Domino(0, 0)]
    assert len(legal_moves_for_hand(hand, None)) == 3


@pytest.mark.parametrize(
    "ends,tile,end,expected",
    [
        ((3, 5), Domino(3, 4), "left", (4, 5)),
        ((3, 5), Domino(4, 5), "right", (3, 4)),
        ((3, 5), Domino(3, 5), "left", (5, 5)),
        ((3, 5), Domino(3, 5), "right", (3, 3)),
        (None, Domino(6, 6), "start", (6, 6)),
    ],
)
def test_resulting_ends(ends, tile, end, expected):
    assert resulting_ends(ends, tile, end) == expected


def test_canonical_moves_collapses_the_duplicate_on_equal_ends():
    # 3|5 against ends (3, 3) reaches the same board either way.
    assert len(legal_moves_for_hand([Domino(3, 5)], (3, 3))) == 2
    assert len(canonical_moves([Domino(3, 5)], (3, 3))) == 1


def test_canonical_moves_keeps_both_placements_of_a_capicu_tile():
    # 3|5 against ends (3, 5) reaches (5, 5) or (3, 3) -- genuinely different.
    assert len(canonical_moves([Domino(3, 5)], (3, 5))) == 2


def test_tranque_is_won_by_the_lower_team_total_not_the_low_individual():
    # Seat 0 holds the lowest hand in the game but their partner is heavy, so
    # team 1 wins 40 to 42 and the start passes to their low seat.
    hands_pips = [2, 20, 40, 20]
    winner, team = resolve_blocked_hand(hands_pips, GameMode.TEAMS, blocker=1)
    assert team == 1
    assert winner == 1
    assert team_for_player(winner) == team


def test_tranque_winner_is_the_low_seat_on_the_winning_team():
    hands_pips = [5, 30, 4, 30]
    winner, team = resolve_blocked_hand(hands_pips, GameMode.TEAMS, blocker=0)
    assert team == 0
    assert winner == 2  # 4 pips beats their partner's 5


def test_tranque_tie_goes_to_the_team_that_closed_the_board():
    hands_pips = [10, 10, 10, 10]
    _, team = resolve_blocked_hand(hands_pips, GameMode.TEAMS, blocker=1)
    assert team == 1
    _, team = resolve_blocked_hand(hands_pips, GameMode.TEAMS, blocker=2)
    assert team == 0


def test_ffa_tranque_is_won_by_the_low_individual_hand():
    winner, _ = resolve_blocked_hand([9, 3, 40, 20], GameMode.FFA, blocker=0)
    assert winner == 1
