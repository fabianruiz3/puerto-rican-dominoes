import time
import random
from dataclasses import dataclass, field
from typing import Optional
from dominoes.types import Domino, MatchConfig, PlayerState, GameMode
from dominoes.tiles import generate_double_six_set
from dominoes.context import build_bot_context
from dominoes.rules import (
    OPENING_TILE,
    legal_moves_for_hand,
    resolve_blocked_hand,
    next_starter,
)
from dominoes.scoring import compute_hand_scores_teams
from dominoes.bots import BotBase

MAX_HANDS_PER_MATCH = 100


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
    blocker: Optional[int] = None
    next_starter: Optional[int] = None


@dataclass
class MatchRecord:
    match_index: int
    hands: list[HandRecord] = field(default_factory=list)
    final_scores: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    winner_team: int = -1


def _find_double_six_holder(players: list[PlayerState]) -> int:
    for p in players:
        for t in p.hand:
            if t.a == 6 and t.b == 6:
                return p.index
    return 0


def _choose_bot_move(bot: BotBase, hand, ends, context):
    try:
        return bot.choose_move(hand, ends, context)
    except TypeError:
        return bot.choose_move(hand, ends)


def run_single_hand(
    players: list[PlayerState],
    bots: list[BotBase],
    config: MatchConfig,
    start_player: int,
    rng: Optional[random.Random] = None,
    opening_hand: bool = False,
) -> HandRecord:
    """Play one hand to completion.

    `opening_hand` marks the first hand of a match: the double-six holder leads
    and is required to play the 6-6. Pass start_player=-1 to have the holder
    located automatically.
    """
    rng = rng or random
    tiles = generate_double_six_set()
    rng.shuffle(tiles)
    for p in players:
        p.hand.clear()
    for _ in range(7):
        for p in players:
            p.hand.append(tiles.pop())
    if opening_hand or start_player == -1:
        start_player = _find_double_six_holder(players)
    forced = OPENING_TILE if opening_hand else None

    rec = HandRecord(
        starting_hands=[[(t.a, t.b) for t in p.hand] for p in players],
        first_player=start_player,
    )
    layout: list[Domino] = []
    ends = None
    ends_before = None
    passes = 0
    cp = start_player
    winning_tile = None
    move_history: list[dict] = []

    while True:
        if any((len(p.hand) == 0 for p in players)):
            break
        if passes >= 4:
            break
        hand = players[cp].hand
        legal = legal_moves_for_hand(hand, ends, forced if ends is None else None)
        if not legal:
            passes += 1
            rec.moves.append(MoveRecord(cp, -1, -1, "pass"))
            move_history.append(
                {"player": cp, "tile": None, "end": "pass", "ends": ends}
            )
            cp = (cp + 1) % 4
            continue
        context = build_bot_context(
            player_index=cp,
            config=config,
            board=layout,
            ends=ends,
            hand_counts=[len(p.hand) for p in players],
            move_history=move_history,
            forced_tile=forced if ends is None else None,
        )
        result = _choose_bot_move(bots[cp], hand, ends, context)
        if result is None or tuple(result) not in legal:
            # A bot that passes on a playable hand, or names an illegal
            # placement, does not get to corrupt the board -- take its first
            # legal move instead so the match stays valid.
            if result is None:
                passes += 1
                rec.moves.append(MoveRecord(cp, -1, -1, "pass"))
                move_history.append(
                    {"player": cp, "tile": None, "end": "pass", "ends": ends}
                )
                cp = (cp + 1) % 4
                continue
            result = legal[0]
        tile, end = result
        passes = 0
        winning_tile = tile
        ends_before = ends
        forced = None
        if ends is None:
            layout.append(tile)
            ends = (tile.a, tile.b)
        else:
            left, right = ends
            if end == "left":
                if tile.a == left:
                    layout.insert(0, Domino(tile.b, tile.a))
                    ends = (tile.b, right)
                else:
                    layout.insert(0, tile)
                    ends = (tile.a, right)
            elif end == "right":
                if tile.a == right:
                    layout.append(tile)
                    ends = (left, tile.b)
                else:
                    layout.append(Domino(tile.b, tile.a))
                    ends = (left, tile.a)
            else:
                layout.append(tile)
                ends = (tile.a, tile.b)
        hand.remove(tile)
        rec.moves.append(MoveRecord(cp, tile.a, tile.b, end))
        move_history.append(
            {"player": cp, "tile": (tile.a, tile.b), "end": end, "ends": ends_before}
        )
        cp = (cp + 1) % 4

    blocked = passes >= 4
    hands_pips = [p.hand_pips() for p in players]
    if blocked:
        blocker = (cp - 1) % 4
        winner, _ = resolve_blocked_hand(hands_pips, config.mode, blocker)
    else:
        winner = (cp - 1) % 4
        blocker = None
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
    rec.blocker = blocker
    rec.next_starter = next_starter(winner)
    rec.points_earned = deltas
    rec.final_layout = [(t.a, t.b) for t in layout]
    rec.final_ends = ends
    return rec


def run_single_match(
    bots: list[BotBase],
    config: MatchConfig,
    match_idx: int,
    rng: Optional[random.Random] = None,
) -> MatchRecord:
    players = [PlayerState(index=i) for i in range(4)]
    rec = MatchRecord(match_index=match_idx)
    hand_num = 0
    next_start = -1
    while True:
        hand_rec = run_single_hand(
            players,
            bots,
            config,
            next_start,
            rng=rng,
            opening_hand=(hand_num == 0),
        )
        rec.hands.append(hand_rec)
        hand_num += 1
        next_start = hand_rec.next_starter
        t0 = players[0].score
        t1 = players[1].score
        if t0 >= config.target_points or t1 >= config.target_points:
            rec.winner_team = 0 if t0 >= t1 else 1
            break
        if hand_num >= MAX_HANDS_PER_MATCH:
            rec.winner_team = 0 if t0 >= t1 else 1
            break
    rec.final_scores = [p.score for p in players]
    return rec


def run_arena(
    bot_a: BotBase,
    bot_b: BotBase,
    num_matches: int = 1000,
    target_points: int = 200,
    seed: Optional[int] = None,
    swap_seats: bool = False,
) -> dict:
    """Bot A on seats 0+2 against Bot B on seats 1+3.

    `swap_seats` puts A on 1+3 instead; running both halves with the same seed
    cancels the dealing advantage of going first.

    `seed` seeds the global RNG, not just the shuffler, because bots draw from
    `random` directly -- RandomBot most obviously. Seeding only the deal would
    leave the run unreproducible.
    """
    config = MatchConfig(target_points=target_points, mode=GameMode.TEAMS)
    if swap_seats:
        bots_list = [bot_b, bot_a, bot_b, bot_a]
        a_team = 1
    else:
        bots_list = [bot_a, bot_b, bot_a, bot_b]
        a_team = 0
    if seed is not None:
        random.seed(seed)
    rng = random

    records = []
    team_a_wins = 0
    team_b_wins = 0
    total_hands = 0
    total_points_a = 0
    total_points_b = 0
    blocked_hands = 0
    t0 = time.time()
    for i in range(num_matches):
        rec = run_single_match(bots_list, config, i, rng=rng)
        records.append(rec)
        if rec.winner_team == a_team:
            team_a_wins += 1
        else:
            team_b_wins += 1
        total_hands += len(rec.hands)
        total_points_a += rec.final_scores[a_team]
        total_points_b += rec.final_scores[1 - a_team]
        blocked_hands += sum((1 for h in rec.hands if h.blocked))
    elapsed = time.time() - t0
    return {
        "num_matches": num_matches,
        "team_a_wins": team_a_wins,
        "team_b_wins": team_b_wins,
        "team_a_win_rate": team_a_wins / num_matches if num_matches else 0,
        "team_b_win_rate": team_b_wins / num_matches if num_matches else 0,
        "avg_hands_per_match": total_hands / num_matches if num_matches else 0,
        "avg_points_team_a": total_points_a / num_matches if num_matches else 0,
        "avg_points_team_b": total_points_b / num_matches if num_matches else 0,
        "blocked_hand_rate": blocked_hands / total_hands if total_hands else 0,
        "elapsed_seconds": elapsed,
        "matches": [
            {
                "match_index": m.match_index,
                "winner_team": m.winner_team,
                "final_scores": m.final_scores,
                "hands": [
                    {
                        "first_player": h.first_player,
                        "winner": h.winner,
                        "blocked": h.blocked,
                        "blocker": h.blocker,
                        "next_starter": h.next_starter,
                        "points_earned": h.points_earned,
                        "final_ends": h.final_ends,
                        "final_layout": h.final_layout,
                        "starting_hands": h.starting_hands,
                        "moves": [
                            {
                                "player": mv.player,
                                "tile": (
                                    None if mv.end == "pass" else [mv.tile_a, mv.tile_b]
                                ),
                                "end": mv.end,
                            }
                            for mv in h.moves
                        ],
                    }
                    for h in m.hands
                ],
            }
            for m in records
        ],
    }
