from dominoes.scoring import (
    compute_hand_scores_ffa,
    compute_hand_scores_teams,
    is_capicu,
)
from dominoes.types import Domino, GameMode, MatchConfig

TEAMS = MatchConfig(target_points=200, mode=GameMode.TEAMS)
FFA = MatchConfig(target_points=200, mode=GameMode.FFA)


def score_teams(hands_pips, winner, tile=None, blocked=False, before=None, after=None):
    return compute_hand_scores_teams(
        config=TEAMS,
        hands_pips=hands_pips,
        winner_index=winner,
        winning_tile=tile,
        blocked=blocked,
        ends_before=before,
        ends_after=after,
    )


def test_domino_out_pays_the_losing_team_their_pips():
    assert score_teams([0, 10, 5, 12], winner=0) == {0: 22, 1: 0, 2: 22, 3: 0}


def test_capicu_adds_the_bonus():
    # Closing 3|5 onto ends (3, 5) could have gone either way.
    scores = score_teams([0, 10, 5, 12], 0, Domino(3, 5), before=(3, 5), after=(5, 5))
    assert scores[0] == 22 + TEAMS.capicu_bonus


def test_chuchazo_adds_the_bonus():
    scores = score_teams([0, 10, 5, 12], 0, Domino(0, 0), before=(3, 0), after=(3, 0))
    assert scores[0] == 22 + TEAMS.chuchazo_bonus


def test_capicu_and_chuchazo_stack():
    scores = score_teams([0, 10, 5, 12], 0, Domino(0, 0), before=(0, 0), after=(0, 0))
    assert scores[0] == 22 + TEAMS.capicu_bonus + TEAMS.chuchazo_bonus


def test_tranque_pays_the_losing_team_and_awards_no_bonus():
    # Team 1 wins the tranque; the closing tile happens to look like a capicu
    # but a blocked hand pays pips only.
    scores = score_teams([2, 20, 40, 20], 1, Domino(3, 3), blocked=True, before=(3, 3), after=(3, 3))
    assert scores == {0: 0, 1: 42, 2: 0, 3: 42}


def test_scoring_follows_the_winner_seat_so_it_cannot_disagree_with_the_starter():
    # Same pip layout, opposite winner -- the payout flips with it.
    assert score_teams([2, 20, 40, 20], 1, blocked=True)[1] == 42
    assert score_teams([2, 20, 40, 20], 0, blocked=True)[0] == 40


def test_ffa_domino_out_collects_every_other_hand():
    scores = compute_hand_scores_ffa(
        config=FFA,
        hands_pips=[0, 10, 5, 12],
        winner_index=0,
        winning_tile=Domino(3, 4),
        blocked=False,
        ends_before=(3, 5),
        ends_after=(4, 5),
    )
    assert scores == {0: 27, 1: 0, 2: 0, 3: 0}


def test_is_capicu_only_fires_when_both_ends_coincide():
    assert is_capicu((3, 5), (5, 5))
    assert is_capicu((3, 5), (3, 3))
    assert not is_capicu((3, 5), (4, 5))
    assert not is_capicu(None, (5, 5))
