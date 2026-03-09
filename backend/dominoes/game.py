from dataclasses import dataclass, field
from typing import Optional
import random
from .types import Domino, MatchConfig, PlayerState, GameMode
from .tiles import generate_double_six_set
from .scoring import compute_hand_scores_ffa, compute_hand_scores_teams
from . import bots

@dataclass
class HandState:
    layout: list[Domino] = field(default_factory=list)
    ends: Optional[tuple[int, int]] = None
    passes_in_a_row: int = 0
    current_player: int = 0
    winning_tile: Optional[Domino] = None
    ends_before_last_move: Optional[tuple[int, int]] = None
    last_move_blocked: bool = False
    starter_index: int = 0
    move_history: list[dict] = field(default_factory=list)

@dataclass
class MatchState:
    config: MatchConfig
    players: list[PlayerState]
    bots: list[Optional[bots.BotBase]]
    hand_state: Optional[HandState] = None
    last_hand_result: Optional[dict] = None
    hand_number: int = 0

    @classmethod
    def new_with_default_bots(cls, config: MatchConfig) -> 'MatchState':
        players = [PlayerState(index=i) for i in range(4)]
        bot_list = [None, bots.GreedyBot(), bots.GreedyBot(), bots.GreedyBot()]
        return cls(config=config, players=players, bots=bot_list)

    def _find_double_six_holder(self) -> int:
        for p in self.players:
            for t in p.hand:
                if t.a == 6 and t.b == 6:
                    return p.index
        return 0

    def _team_for_player(self, player_index: int) -> int:
        return 0 if player_index in (0, 2) else 1

    def _lowest_pip_player(self, candidates: list[int]) -> int:
        return min(candidates, key=lambda idx: (self.players[idx].hand_pips(), idx))

    def _determine_next_starter_from_last_hand(self) -> int:
        result = self.last_hand_result
        if not result:
            return self._find_double_six_holder()
        if not result['blocked']:
            return result['winner']
        blocker = result.get('blocker')
        winner = result['winner']
        if self.config.mode == GameMode.FFA:
            return winner
        if blocker is None:
            return winner
        blocker_team = self._team_for_player(blocker)
        winner_team = self._team_for_player(winner)
        if blocker_team == winner_team:
            return blocker
        winning_team_players = [0, 2] if winner_team == 0 else [1, 3]
        return self._lowest_pip_player(winning_team_players)

    def start_new_hand(self):
        tiles = generate_double_six_set()
        random.shuffle(tiles)
        for p in self.players:
            p.hand.clear()
        for _ in range(7):
            for p in self.players:
                p.hand.append(tiles.pop())
        if self.hand_number == 0:
            start = self._find_double_six_holder()
        else:
            start = self._determine_next_starter_from_last_hand()
        self.hand_state = HandState(current_player=start, starter_index=start)
        self.last_hand_result = None
        self.hand_number += 1

    def get_bot_context(self, player_index: int) -> dict:
        hs = self.hand_state
        teammate_played = {i: 0 for i in range(7)}
        opponent_played = {i: 0 for i in range(7)}
        if hs is not None:
            if self.config.mode == GameMode.TEAMS:
                teammate = (player_index + 2) % 4
            else:
                teammate = None
            for move in hs.move_history:
                if move['tile'] is None:
                    continue
                a, b = move['tile']
                bucket = None
                if teammate is not None and move['player'] == teammate:
                    bucket = teammate_played
                elif move['player'] != player_index:
                    bucket = opponent_played
                if bucket is not None:
                    bucket[a] += 1
                    bucket[b] += 1
        return {'player_index': player_index, 'mode': self.config.mode.name, 'teammate_index': (player_index + 2) % 4 if self.config.mode == GameMode.TEAMS else None, 'teammate_played_numbers': teammate_played, 'opponent_played_numbers': opponent_played, 'capicu_bonus': self.config.capicu_bonus, 'chuchazo_bonus': self.config.chuchazo_bonus}

    def play_tile(self, player_index: int, tile: Domino, end: str):
        hs = self.hand_state
        assert hs is not None
        hs.ends_before_last_move = hs.ends
        if hs.ends is None:
            hs.layout.append(tile)
            hs.ends = (tile.a, tile.b)
        else:
            left, right = hs.ends
            if end == 'left':
                if tile.a == left:
                    hs.layout.insert(0, Domino(tile.b, tile.a))
                    hs.ends = (tile.b, right)
                elif tile.b == left:
                    hs.layout.insert(0, tile)
                    hs.ends = (tile.a, right)
                else:
                    raise ValueError('Illegal move on left')
            elif end == 'right':
                if tile.a == right:
                    hs.layout.append(tile)
                    hs.ends = (left, tile.b)
                elif tile.b == right:
                    hs.layout.append(Domino(tile.b, tile.a))
                    hs.ends = (left, tile.a)
                else:
                    raise ValueError('Illegal move on right')
            elif end == 'start':
                hs.layout.append(tile)
                hs.ends = (tile.a, tile.b)
            else:
                raise ValueError('Invalid end')
        hs.passes_in_a_row = 0
        hs.winning_tile = tile
        hs.move_history.append({'player': player_index, 'tile': (tile.a, tile.b), 'end': end})
        player = self.players[player_index]
        player.hand.remove(tile)

    def pass_turn(self):
        hs = self.hand_state
        assert hs is not None
        hs.passes_in_a_row += 1
        hs.move_history.append({'player': hs.current_player, 'tile': None, 'end': 'pass'})

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
        if any((len(p.hand) == 0 for p in self.players)):
            return True
        return self.is_blocked()

    def resolve_hand(self):
        hs = self.hand_state
        assert hs is not None
        blocked = self.is_blocked()
        hands_pips = [p.hand_pips() for p in self.players]
        remaining = [{'index': p.index, 'hand': [{'a': t.a, 'b': t.b} for t in p.hand], 'pips': p.hand_pips()} for p in self.players]
        blocker = (hs.current_player - 1) % 4 if blocked else None
        if blocked:
            winner = min(range(4), key=lambda i: hands_pips[i])
        else:
            winner = (hs.current_player - 1) % 4
        if self.config.mode == GameMode.FFA:
            deltas = compute_hand_scores_ffa(config=self.config, hands_pips=hands_pips, winner_index=winner, winning_tile=hs.winning_tile, blocked=blocked, ends_before=hs.ends_before_last_move, ends_after=hs.ends)
        else:
            deltas = compute_hand_scores_teams(config=self.config, hands_pips=hands_pips, winner_index=winner, winning_tile=hs.winning_tile, blocked=blocked, ends_before=hs.ends_before_last_move, ends_after=hs.ends)
        for i, p in enumerate(self.players):
            p.score += deltas[i]
        hs.last_move_blocked = blocked
        if blocked and self.config.mode == GameMode.TEAMS:
            winner_team = self._team_for_player(winner)
            next_starter = blocker if blocker is not None and self._team_for_player(blocker) == winner_team else self._lowest_pip_player([0, 2] if winner_team == 0 else [1, 3])
        elif blocked:
            next_starter = winner
        else:
            next_starter = winner
        self.last_hand_result = {'winner': winner, 'blocked': blocked, 'blocker': blocker, 'next_starter': next_starter, 'remaining': remaining, 'points_earned': deltas}

    def is_match_over(self) -> bool:
        if self.config.mode == GameMode.FFA:
            return any((p.score >= self.config.target_points for p in self.players))
        team0_score = self.players[0].score
        team1_score = self.players[1].score
        return team0_score >= self.config.target_points or team1_score >= self.config.target_points

    def to_dict(self) -> dict:
        hs = self.hand_state
        layout = hs.layout if hs is not None else []
        ends = hs.ends if hs is not None else None
        current_player = hs.current_player if hs is not None else 0
        passes = hs.passes_in_a_row if hs is not None else 0
        last_blocked = hs.last_move_blocked if hs is not None else False
        return {'config': {'target_points': self.config.target_points, 'mode': self.config.mode.name, 'capicu_bonus': self.config.capicu_bonus, 'chuchazo_bonus': self.config.chuchazo_bonus}, 'players': [{'index': p.index, 'score': p.score, 'hand': [{'a': t.a, 'b': t.b} for t in p.hand]} for p in self.players], 'hand_state': {'layout': [{'a': t.a, 'b': t.b} for t in layout], 'ends': {'left': ends[0], 'right': ends[1]} if ends is not None else None, 'current_player': current_player, 'passes_in_a_row': passes, 'last_move_blocked': last_blocked, 'starter_index': hs.starter_index if hs is not None else 0}, 'last_hand_result': self.last_hand_result, 'match_over': self.is_match_over()}