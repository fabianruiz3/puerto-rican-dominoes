from .types import Domino, MatchConfig
from .rules import team_for_player, team_players


def is_capicu(ends_before, ends_after) -> bool:
    """True when the closing tile could have been played on either end.

    Equivalent to checking that the two ends coincide afterwards: playing tile
    (x, y) onto ends (L, R) leaves equal ends exactly when {x, y} == {L, R}.
    """
    if ends_before is None or ends_after is None:
        return False
    left_after, right_after = ends_after
    return left_after == right_after


def _bonus(config: MatchConfig, winning_tile: Domino, ends_before, ends_after) -> int:
    bonus = 0
    if is_capicu(ends_before, ends_after):
        bonus += config.capicu_bonus
    if winning_tile is not None and winning_tile.is_double_blank():
        bonus += config.chuchazo_bonus
    return bonus


def compute_hand_scores_ffa(
    config: MatchConfig,
    hands_pips: list[int],
    winner_index: int,
    winning_tile: Domino,
    blocked: bool,
    ends_before,
    ends_after,
) -> dict[int, int]:
    scores = {i: 0 for i in range(4)}
    if blocked:
        total_pips = sum(hands_pips)
        scores[winner_index] += total_pips - hands_pips[winner_index]
        return scores
    base_points = sum((hands_pips[i] for i in range(4) if i != winner_index))
    scores[winner_index] += base_points + _bonus(
        config, winning_tile, ends_before, ends_after
    )
    return scores


def compute_hand_scores_teams(
    config: MatchConfig,
    hands_pips: list[int],
    winner_index: int,
    winning_tile: Domino,
    blocked: bool,
    ends_before,
    ends_after,
) -> dict[int, int]:
    """Points for the winning team.

    `winner_index` must already be the player who won the hand -- the one who
    went out, or the one resolve_blocked_hand named on a tranque. The winning
    team is read off that player rather than recomputed, so scoring and the
    next-hand starter can never disagree about who won.
    """
    scores = {i: 0 for i in range(4)}
    winner_team = team_for_player(winner_index)
    winners = team_players(winner_team)
    losers = team_players(1 - winner_team)
    if blocked:
        total = sum((hands_pips[i] for i in losers))
    else:
        total = sum((hands_pips[i] for i in losers)) + _bonus(
            config, winning_tile, ends_before, ends_after
        )
    for i in winners:
        scores[i] += total
    return scores
