from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import random
from .types import Domino, MatchConfig, PlayerState, GameMode
from .tiles import generate_double_six_set
from .rules import legal_moves_for_hand
from .scoring import compute_hand_scores_ffa, compute_hand_scores_teams
from . import bots


@dataclass
class HandState:
    layout: List[Domino] = field(default_factory=list)
    ends: Optional[Tuple[int, int]] = None
    passes_in_a_row: int = 0
    current_player: int = 0
    winning_tile: Optional[Domino] = None
    ends_before_last_move: Optional[Tuple[int, int]] = None
    last_move_blocked: bool = False


@dataclass
class MatchState:
    config: MatchConfig
    players: List[PlayerState]
    bots: List[Optional[bots.BotBase]]
    hand_state: Optional[HandState] = None

    @classmethod
    def new_with_default_bots(cls, config: MatchConfig) -> "MatchState":
        players = [PlayerState(index=i) for i in range(4)]
        bot_list = [None, bots.GreedyBot(), bots.GreedyBot(), bots.GreedyBot()]
        return cls(config=config, players=players, bots=bot_list)

    def start_new_hand(self):
        tiles = generate_double_six_set()
        random.shuffle(tiles)
        for p in self.players:
            p.hand.clear()
        for _ in range(7):
            for p in self.players:
                p.hand.append(tiles.pop())
        start = random.randint(0, 3)
        self.hand_state = HandState(current_player=start)

    def play_tile(self, player_index: int, tile: Domino, end: str):
        hs = self.hand_state
        assert hs is not None
        hs.ends_before_last_move = hs.ends
        if hs.ends is None:
            hs.layout.append(tile)
            hs.ends = (tile.a, tile.b)
        else:
            left, right = hs.ends
            if end == "left":
                if tile.a == left:
                    hs.layout.insert(0, Domino(tile.b, tile.a))
                    hs.ends = (tile.b, right)
                elif tile.b == left:
                    hs.layout.insert(0, tile)
                    hs.ends = (tile.a, right)
                else:
                    raise ValueError("Illegal move on left")
            elif end == "right":
                if tile.a == right:
                    hs.layout.append(tile)
                    hs.ends = (left, tile.b)
                elif tile.b == right:
                    hs.layout.append(Domino(tile.b, tile.a))
                    hs.ends = (left, tile.a)
                else:
                    raise ValueError("Illegal move on right")
            elif end == "start":
                hs.layout.append(tile)
                hs.ends = (tile.a, tile.b)
            else:
                raise ValueError("Invalid end")
        hs.passes_in_a_row = 0
        hs.winning_tile = tile
        player = self.players[player_index]
        player.hand.remove(tile)

    def pass_turn(self):
        hs = self.hand_state
        assert hs is not None
        hs.passes_in_a_row += 1

    def next_player(self):
        hs = self.hand_state
        assert hs is not None
        hs.current_player = (hs.current_player + 1) % len(self.players)

    def is_blocked(self) -> bool:
        hs = self.hand_state
        assert hs is not None
        return hs.passes_in_a_row >= 4

    def is_hand_over(self) -> bool:
        hs = self.hand_state
        assert hs is not None
        if any(len(p.hand) == 0 for p in self.players):
            return True
        return self.is_blocked()

    def resolve_hand(self):
        hs = self.hand_state
        assert hs is not None
        blocked = self.is_blocked()
        hands_pips = [p.hand_pips() for p in self.players]
        if blocked:
            winner = min(range(4), key=lambda i: hands_pips[i])
        else:
            winner = (hs.current_player - 1) % 4
        if self.config.mode == GameMode.FFA:
            deltas = compute_hand_scores_ffa(
                config=self.config,
                hands_pips=hands_pips,
                winner_index=winner,
                winning_tile=hs.winning_tile,
                blocked=blocked,
                ends_before=hs.ends_before_last_move,
                ends_after=hs.ends,
            )
        else:
            deltas = compute_hand_scores_teams(
                config=self.config,
                hands_pips=hands_pips,
                winner_index=winner,
                winning_tile=hs.winning_tile,
                blocked=blocked,
                ends_before=hs.ends_before_last_move,
                ends_after=hs.ends,
            )
        for i, p in enumerate(self.players):
            p.score += deltas[i]
        hs.last_move_blocked = blocked

    def is_match_over(self) -> bool:
        if self.config.mode == GameMode.FFA:
            return any(p.score >= self.config.target_points for p in self.players)
        team0_score = self.players[0].score + self.players[2].score
        team1_score = self.players[1].score + self.players[3].score
        return team0_score >= self.config.target_points or team1_score >= self.config.target_points

    def to_dict(self) -> Dict[str, Any]:
        hs = self.hand_state
        layout = hs.layout if hs is not None else []
        ends = hs.ends if hs is not None else None
        current_player = hs.current_player if hs is not None else 0
        passes = hs.passes_in_a_row if hs is not None else 0
        last_blocked = hs.last_move_blocked if hs is not None else False
        return {
            "config": {
                "target_points": self.config.target_points,
                "mode": self.config.mode.name,
                "capicu_bonus": self.config.capicu_bonus,
                "chuchazo_bonus": self.config.chuchazo_bonus,
            },
            "players": [
                {
                    "index": p.index,
                    "score": p.score,
                    "hand": [{"a": t.a, "b": t.b} for t in p.hand],
                }
                for p in self.players
            ],
            "hand_state": {
                "layout": [{"a": t.a, "b": t.b} for t in layout],
                "ends": {"left": ends[0], "right": ends[1]} if ends is not None else None,
                "current_player": current_player,
                "passes_in_a_row": passes,
                "last_move_blocked": last_blocked,
            },
        }
