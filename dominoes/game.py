from dataclasses import dataclass, field
import random

from .types import Domino, GameMode, PlayerState, MatchConfig
from .rules import legal_moves
from .tiles import generate_full_set
from .scoring import compute_hand_scores_ffa, compute_hand_scores_teams

from . import bots

@dataclass
class HandSate:
    layout: list[Domino] = field(default_factory=list)
    ends: tuple[int, int] = None  # (left_end, right_end)
    passes_in_row: int = 0
    current_player_idx: int = 0
    winning_tile: Domino = None
    ends_before_last_move: tuple[int, int] = None
    last_move_blocked: bool = False

@dataclass
class GameState:
    players: list[PlayerState]
    hand: HandSate = None
    config: MatchConfig
    bot_classes: list[bots.BotBase]

    def start_new_hand(self):
        full_tiles = generate_full_set()
        random.shuffle(full_tiles)

        num_players = len(self.players)
        hand_size = len(full_tiles) // num_players

        for i, player in enumerate(self.players):
            player.hand = full_tiles[i*hand_size:(i+1)*hand_size]

        # for starting a new hand, the starting player is the winner of the last hand fix later 
        # and for the first round its the one with the double six
        self.hand = HandSate(current_player_idx=random.randint(0, 3))

    def play_tile(self, player_idx: int, tile: Domino, end: str):
        hs = self.hand
        assert hs is not None

        hs.ends_before_last_move = hs.ends
        
        if hs.ends is None:
            hs.layout.append(tile)
            hs.ends = (tile.left, tile.right)
        else:
            left_end, right_end = hs.ends
            if end == 'left':
                if tile.right == left_end:
                    hs.layout.insert(0, tile)
                    hs.ends = (tile.left, right_end)
                elif tile.left == left_end:
                    hs.layout.insert(0, Domino(tile.right, tile.left))
                    hs.ends = (tile.right, right_end)
            elif end == 'right':
                if tile.left == right_end:
                    hs.layout.append(tile)
                    hs.ends = (left_end, tile.right)
                elif tile.right == right_end:
                    hs.layout.append(Domino(tile.right, tile.left))
                    hs.ends = (left_end, tile.left)
        
        hs.passes_in_row = 0
        hs.winning_tile = tile

        player = self.players[player_idx]
        player.hand.remove(tile)

    def pass_turn(self):
        hs = self.hand
        assert hs is not None

        hs.passes_in_row += 1
    
    def next_player(self):
        hs = self.hand
        assert hs is not None

        hs.current_player_idx = (hs.current_player_idx + 1) % len(self.players)
    
    def is_blocked(self) -> bool:
        hs = self.hand
        assert hs is not None

        return hs.passes_in_row >= len(self.players)
    
    def is_hand_over(self) -> bool:
        hs = self.hand
        assert hs is not None

        if any(len(player.hand) == 0 for player in self.players):
            return True
        if self.is_blocked():
            return True
        return self.is_blocked()
    
    def resolve_hand(self):
        hs = self.hand
        assert hs is not None

        hands_pips = [player.hand_pips() for player in self.players]
        winner_index = next((i for i, player in enumerate(self.players) if len(player.hand) == 0), -1)
        blocked = self.is_blocked()
        config = self.config

        if config.mode == GameMode.FFA:
            delta_scores = compute_hand_scores_ffa(
                config,
                hands_pips,
                winner_index,
                hs.winning_tile,
                blocked,
                hs.ends_before_last_move,
                hs.ends
            )
        else:
            delta_scores = compute_hand_scores_teams(
                config,
                hands_pips,
                winner_index,
                hs.winning_tile,
                blocked,
                hs.ends_before_last_move,
                hs.ends
            )
        
        for i, player in enumerate(self.players):
            player.score += delta_scores[i]
        
        hs.last_move_blocked = blocked
    
    def is_game_over(self) -> bool:
        return any(player.score >= self.config.target_score for player in self.players)