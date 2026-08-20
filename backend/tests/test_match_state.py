"""MatchState is the engine behind the HTTP API; arena.py is the engine behind
the bot arena. They have to agree about the rules, so the opening lead, the
starter chain and the tranque settlement are checked here too.
"""

import random

import pytest

from dominoes.game import MatchState
from dominoes.rules import OPENING_TILE, team_for_player
from dominoes.types import GameMode, MatchConfig


def new_match(mode=GameMode.TEAMS, seed=1):
    random.seed(seed)
    return MatchState.new_with_default_bots(MatchConfig(target_points=200, mode=mode))


def play_out(match):
    """Drive every seat with the default bots until the hand resolves."""
    while not match.is_hand_over():
        seat = match.hand_state.current_player
        legal = match.legal_moves(seat)
        if not legal:
            match.pass_turn()
        else:
            tile, end = legal[0]
            match.play_tile(seat, tile, end)
        match.next_player()
    match.resolve_hand()


def test_the_first_hand_forces_the_double_six_lead():
    m = new_match()
    m.start_new_hand()
    hs = m.hand_state
    assert hs.forced_tile == OPENING_TILE
    assert OPENING_TILE in m.players[hs.starter_index].hand
    assert m.legal_moves(hs.starter_index) == [(OPENING_TILE, "start")]


def test_the_forced_lead_is_surfaced_to_the_frontend():
    m = new_match()
    m.start_new_hand()
    assert m.to_dict()["hand_state"]["forced_tile"] == {"a": 6, "b": 6}


def test_the_force_lifts_after_the_opening_tile_is_played():
    m = new_match()
    m.start_new_hand()
    seat = m.hand_state.starter_index
    m.play_tile(seat, OPENING_TILE, "start")
    assert m.hand_state.forced_tile is None
    assert m.to_dict()["hand_state"]["forced_tile"] is None


def test_the_second_hand_is_opened_freely_by_the_previous_winner():
    m = new_match()
    m.start_new_hand()
    play_out(m)
    winner = m.last_hand_result["winner"]
    m.start_new_hand()
    assert m.hand_state.starter_index == winner
    assert m.hand_state.forced_tile is None
    assert len(m.legal_moves(winner)) == len(m.players[winner].hand)


def test_a_tranque_hands_the_start_to_the_seat_that_won_it_on_pips():
    m = new_match(seed=11)
    m.start_new_hand()
    # Force a tranque directly: four passes in a row from a mid-hand position.
    m.play_tile(m.hand_state.starter_index, OPENING_TILE, "start")
    m.next_player()
    for _ in range(4):
        m.pass_turn()
        m.next_player()
    assert m.is_blocked()
    m.resolve_hand()
    result = m.last_hand_result
    assert result["blocked"]
    assert result["next_starter"] == result["winner"]
    pips = [p["pips"] for p in result["remaining"]]
    winning_team = team_for_player(result["winner"])
    partner = [0, 2] if winning_team == 0 else [1, 3]
    assert result["winner"] == min(partner, key=lambda i: (pips[i], i))


def test_the_tranque_winners_team_is_the_one_that_gets_paid():
    m = new_match(seed=11)
    m.start_new_hand()
    m.play_tile(m.hand_state.starter_index, OPENING_TILE, "start")
    m.next_player()
    for _ in range(4):
        m.pass_turn()
        m.next_player()
    m.resolve_hand()
    result = m.last_hand_result
    paid = [s for s, pts in result["points_earned"].items() if pts > 0]
    assert sorted(paid) == sorted(
        [0, 2] if team_for_player(result["winner"]) == 0 else [1, 3]
    )


def test_passing_records_the_ends_the_seat_actually_faced():
    m = new_match()
    m.start_new_hand()
    seat = m.hand_state.starter_index
    m.play_tile(seat, OPENING_TILE, "start")
    m.next_player()
    m.pass_turn()
    last = m.hand_state.move_history[-1]
    assert last["tile"] is None
    assert last["ends"] == (6, 6)


def test_the_bot_context_reports_live_hand_sizes():
    m = new_match()
    m.start_new_hand()
    seat = m.hand_state.starter_index
    assert m.get_bot_context(0).hand_counts == [7, 7, 7, 7]
    m.play_tile(seat, OPENING_TILE, "start")
    counts = m.get_bot_context(0).hand_counts
    assert counts[seat] == 6
    assert sum(counts) == 27


@pytest.mark.parametrize("mode", [GameMode.TEAMS, GameMode.FFA])
def test_a_full_match_terminates_and_reaches_the_target(mode):
    m = new_match(mode=mode, seed=5)
    m.start_new_hand()
    for _ in range(200):
        play_out(m)
        if m.is_match_over():
            break
        m.start_new_hand()
    assert m.is_match_over()
    assert max(p.score for p in m.players) >= 200
