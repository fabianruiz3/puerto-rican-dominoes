from dataclasses import dataclass, field
from enum import Enum, auto

class GameMode(Enum):
    FFA = auto()
    TEAMS = auto()

@dataclass(frozen=True)
class Domino:
    a: int
    b: int

    def is_double(self) -> bool:
        return self.a == self.b

    def is_double_blank(self) -> bool:
        return self.a == 0 and self.b == 0

    def pips(self) -> int:
        return self.a + self.b

    def __str__(self) -> str:
        return f"[{self.a}|{self.b}]"

@dataclass
class Move:
    player_idx: int
    tile: Domino
    end: str
    passed: bool = False

@dataclass
class MatchConfig:
    target_points: int
    mode: GameMode
    capicu_bonus: int = 100
    chuchazo_bonus: int = 100

@dataclass
class PlayerState:
    index: int
    hand: list[Domino] = field(default_factory=list)
    score: int = 0
    hand_score: int = 0

    def hand_pips(self) -> int:
        return sum(tile.pips() for tile in self.hand)