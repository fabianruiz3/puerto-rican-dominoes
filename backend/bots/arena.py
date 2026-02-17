"""
Arena engine for bot-vs-bot simulation in 2v2 teams format.

Team A consists of players 0 and 2, Team B consists of players 1 and 3.
Records all moves for later replay and analysis.
"""
import time
import random
import traceback
from dataclasses import dataclass, field
from typing import Optional

from dominoes.types import Domino, MatchConfig, PlayerState, GameMode
from dominoes.tiles import generate_double_six_set
from dominoes.rules import legal_moves_for_hand
from dominoes.scoring import compute_hand_scores_teams
from dominoes.bots import BotBase


@dataclass
class MoveRecord:
    player: int
    tile_a: int
    tile_b: int
    end: str


@dataclass
class HandRecord:
    starting_hands: list[list[tuple[int, int]]]
    first_player: int
    moves: list[MoveRecord] = field(default_factory=list)
    winner: int = -1
    blocked: bool = False
    points_earned: dict[int, int] = field(default_factory=dict)
    final_layout: list[tuple[int, int]] = field(default_factory=list)
    final_ends: Optional[tuple[int, int]] = None


@dataclass
class MatchRecord:
    match_index: int
    hands: list[HandRecord] = field(default_factory=list)
    final_scores: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    winner_team: int = -1


def run_single_hand(
    players: list[PlayerState],
    bots: list[BotBase],
    config: MatchConfig,
    start_player: int,
) -> HandRecord:
    """Execute a single hand and return the hand record."""
    tiles = generate_double_six_set()
    random.shuffle(tiles)
    for p in players:
        p.hand.clear()
    for _ in range(7):
        for p in players:
            p.hand.append(tiles.pop())

    rec = HandRecord(
        starting_hands=[[(t.a, t.b) for t in p.hand] for p in players],
        first_player=start_player,
    )

    layout = []
    ends = None
    ends_before = None
    passes = 0
    cp = start_player
    winning_tile = None

    while True:
        if any(len(p.hand) == 0 for p in players):
            break
        if passes >= 4:
            break

        hand = players[cp].hand
        legal = legal_moves_for_hand(hand, ends)

        if not legal:
            passes += 1
            rec.moves.append(MoveRecord(cp, -1, -1, "pass"))
            cp = (cp + 1) % 4
            continue

        result = bots[cp].choose_move(hand, ends)
        if result is None:
            passes += 1
            rec.moves.append(MoveRecord(cp, -1, -1, "pass"))
            cp = (cp + 1) % 4
            continue

        tile, end = result
        passes = 0
        winning_tile = tile
        ends_before = ends
        if ends is None:
            layout.append(tile)
            ends = (tile.a, tile.b)
        else:
            left, right = ends
            if end == "left":
                if tile.a == left:
                    layout.insert(0, Domino(tile.b, tile.a))
                    ends = (tile.b, right)
                elif tile.b == left:
                    layout.insert(0, tile)
                    ends = (tile.a, right)
            elif end == "right":
                if tile.a == right:
                    layout.append(tile)
                    ends = (left, tile.b)
                elif tile.b == right:
                    layout.append(Domino(tile.b, tile.a))
                    ends = (left, tile.a)
            elif end == "start":
                layout.append(tile)
                ends = (tile.a, tile.b)

        hand.remove(tile)
        rec.moves.append(MoveRecord(cp, tile.a, tile.b, end))
        cp = (cp + 1) % 4

    blocked = passes >= 4
    hands_pips = [p.hand_pips() for p in players]

    if blocked:
        winner = min(range(4), key=lambda i: hands_pips[i])
    else:
        winner = (cp - 1) % 4  # last player who moved

    deltas = compute_hand_scores_teams(
        config=config,
        hands_pips=hands_pips,
        winner_index=winner,
        winning_tile=winning_tile,
        blocked=blocked,
        ends_before=ends_before,
        ends_after=ends,
    )

    for i, p in enumerate(players):
        p.score += deltas[i]

    rec.winner = winner
    rec.blocked = blocked
    rec.points_earned = deltas
    rec.final_layout = [(t.a, t.b) for t in layout]
    rec.final_ends = ends
    return rec


def run_single_match(
    bots: list[BotBase],
    config: MatchConfig,
    match_idx: int,
) -> MatchRecord:
    """Execute a complete match up to target points."""
    players = [PlayerState(index=i) for i in range(4)]
    rec = MatchRecord(match_index=match_idx)

    hand_num = 0
    while True:
        start = random.randint(0, 3)
        hand_rec = run_single_hand(players, bots, config, start)
        rec.hands.append(hand_rec)
        hand_num += 1

        t0 = players[0].score
        t1 = players[1].score
        if t0 >= config.target_points or t1 >= config.target_points:
            rec.winner_team = 0 if t0 >= t1 else 1
            break

        if hand_num >= 100:
            rec.winner_team = 0 if t0 >= t1 else 1
            break

    rec.final_scores = [p.score for p in players]
    return rec


def run_arena(
    bot_a: BotBase,
    bot_b: BotBase,
    num_matches: int = 1000,
    target_points: int = 200,
) -> dict[str, any]:
    """
    Run multiple matches between two bots in teams format.

    Bot A uses players 0 and 2, Bot B uses players 1 and 3.
    Returns comprehensive statistics and match records.
    """
    config = MatchConfig(target_points=target_points, mode=GameMode.TEAMS)
    bots_list = [bot_a, bot_b, bot_a, bot_b]

    records = []
    team_a_wins = 0
    team_b_wins = 0
    total_hands = 0
    total_points_a = 0
    total_points_b = 0
    blocked_hands = 0

    t0 = time.time()

    for i in range(num_matches):
        rec = run_single_match(bots_list, config, i)
        records.append(rec)

        if rec.winner_team == 0:
            team_a_wins += 1
        else:
            team_b_wins += 1

        total_hands += len(rec.hands)
        total_points_a += rec.final_scores[0]
        total_points_b += rec.final_scores[1]
        blocked_hands += sum(1 for h in rec.hands if h.blocked)

    elapsed = time.time() - t0

    return {
        "num_matches": num_matches,
        "target_points": target_points,
        "elapsed_seconds": round(elapsed, 2),
        "team_a_wins": team_a_wins,
        "team_b_wins": team_b_wins,
        "team_a_win_pct": round(team_a_wins / num_matches * 100, 1),
        "team_b_win_pct": round(team_b_wins / num_matches * 100, 1),
        "total_hands": total_hands,
        "avg_hands_per_match": round(total_hands / num_matches, 1),
        "avg_points_a": round(total_points_a / num_matches, 1),
        "avg_points_b": round(total_points_b / num_matches, 1),
        "blocked_hands": blocked_hands,
        "blocked_pct": round(blocked_hands / total_hands * 100, 1) if total_hands else 0,
        "matches": [match_to_dict(r) for r in records],
    }


def match_to_dict(rec: MatchRecord) -> dict:
    return {
        "match_index": rec.match_index,
        "winner_team": rec.winner_team,
        "final_scores": rec.final_scores,
        "num_hands": len(rec.hands),
        "hands": [hand_to_dict(h) for h in rec.hands],
    }


def hand_to_dict(rec: HandRecord) -> dict:
    return {
        "starting_hands": rec.starting_hands,
        "first_player": rec.first_player,
        "moves": [
            {"player": m.player, "tile": [m.tile_a, m.tile_b], "end": m.end}
            for m in rec.moves
        ],
        "winner": rec.winner,
        "blocked": rec.blocked,
        "points_earned": rec.points_earned,
        "final_layout": rec.final_layout,
        "final_ends": rec.final_ends,
    }
