from .types import Domino, MatchConfig

def compute_hand_scores_ffa(
    config: MatchConfig,
    hands_pips: list[int],   # len 4, pips left in each player's hand
    winner_index: int,
    winning_tile: Domino,
    blocked: bool,
    ends_before: tuple[int, int],
    ends_after: tuple[int, int]
) -> dict[int, int]:
    """
    Returns delta scores for each player (len 4).
    """
    scores = {i: 0 for i in range(4)}

    if blocked:
        total_pips = sum(hands_pips)
        winner = min(range(4), key=lambda i: hands_pips[i])
        base_points = total_pips - hands_pips[winner]
        scores[winner] += base_points
        return scores

    base_points = sum(hands_pips[i] for i in range(4) if i != winner_index)
    bonus = 0

    if is_capicu(winning_tile, ends_before):
        bonus += config.capicu_bonus

    if winning_tile.is_double_blank():
        bonus += config.chuchazo_bonus

    scores[winner_index] += base_points + bonus
    return scores

def compute_hand_scores_teams(
    config: MatchConfig,
    hands_pips: list[int],
    winner_index: int,
    winning_tile: Domino,
    blocked: bool,
    ends_before: tuple[int, int],
    ends_after: tuple[int, int]
) -> dict[int, int]:
    """
    Returns delta scores for each player (len 4).
    Players 0 and 2 are on one team, players 1 and 3 on the other.
    """
    scores = {i: 0 for i in range(4)}

    if blocked:
        total_pips = sum(hands_pips)
        team_pips = [hands_pips[0] + hands_pips[2], hands_pips[1] + hands_pips[3]]
        winning_team = 0 if team_pips[0] < team_pips[1] else 1
        base_points = total_pips - team_pips[winning_team]
        for i in range(4):
            if i % 2 == winning_team:
                scores[i] += base_points
        return scores

    base_points = sum(hands_pips[i] for i in range(4) if i % 2 != winner_index % 2)
    bonus = 0

    if is_capicu(winning_tile, ends_before):
        bonus += config.capicu_bonus

    if winning_tile.is_double_blank():
        bonus += config.chuchazo_bonus

    for i in range(4):
        if i % 2 == winner_index % 2:
            scores[i] += base_points + bonus
    return scores

def is_capicu(winning_tile: Domino, ends_before: tuple[int, int]) -> bool:
    """
    Determine if the move resulted in a capicu.
    A capicu occurs when the winning tile can play on both board ends,
    meaning the player could have won from either side.
    """ 
    return (winning_tile.a in ends_before and winning_tile.b in ends_before)