from typing import Dict, List
from .types import Domino, MatchConfig


def is_capicu(ends_before, ends_after) -> bool:
    if ends_before is None or ends_after is None:
        return False
    left_after, right_after = ends_after
    return left_after == right_after


def compute_hand_scores_ffa(
    config: MatchConfig,
    hands_pips: List[int],
    winner_index: int,
    winning_tile: Domino,
    blocked: bool,
    ends_before,
    ends_after,
) -> Dict[int, int]:
    scores = {i: 0 for i in range(4)}
    if blocked:
        total_pips = sum(hands_pips)
        winner = min(range(4), key=lambda i: hands_pips[i])
        base_points = total_pips - hands_pips[winner]
        scores[winner] += base_points
        return scores
    base_points = sum(hands_pips[i] for i in range(4) if i != winner_index)
    bonus = 0
    if is_capicu(ends_before, ends_after):
        bonus += config.capicu_bonus
    if winning_tile is not None and winning_tile.is_double_blank():
        bonus += config.chuchazo_bonus
    scores[winner_index] += base_points + bonus
    return scores


def compute_hand_scores_teams(
    config: MatchConfig,
    hands_pips: List[int],
    winner_index: int,
    winning_tile: Domino,
    blocked: bool,
    ends_before,
    ends_after,
) -> Dict[int, int]:
    scores = {i: 0 for i in range(4)}
    team0 = [0, 2]
    team1 = [1, 3]
    team_for_player = 0 if winner_index in team0 else 1
    team0_pips = hands_pips[0] + hands_pips[2]
    team1_pips = hands_pips[1] + hands_pips[3]
    total_pips = sum(hands_pips)
    if blocked:
        winner_team = 0 if team0_pips < team1_pips else 1
        winner_pips = team0_pips if winner_team == 0 else team1_pips
        base_points = total_pips - winner_pips
        if winner_team == 0:
            for i in team0:
                scores[i] += base_points
        else:
            for i in team1:
                scores[i] += base_points
        return scores
    if team_for_player == 0:
        loser_pips = team1_pips
        winner_team_players = team0
    else:
        loser_pips = team0_pips
        winner_team_players = team1
    base_points = loser_pips
    bonus = 0
    if is_capicu(ends_before, ends_after):
        bonus += config.capicu_bonus
    if winning_tile is not None and winning_tile.is_double_blank():
        bonus += config.chuchazo_bonus
    total = base_points + bonus
    for i in winner_team_players:
        scores[i] += total
    return scores
