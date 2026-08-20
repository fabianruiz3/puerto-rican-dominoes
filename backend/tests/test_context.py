from dominoes.context import BotContext, build_bot_context
from dominoes.types import Domino, GameMode, MatchConfig

TEAMS = MatchConfig(target_points=200, mode=GameMode.TEAMS)

HISTORY = [
    {"player": 0, "tile": (6, 6), "end": "start", "ends": None},
    {"player": 1, "tile": None, "end": "pass", "ends": (6, 6)},
    {"player": 2, "tile": (6, 3), "end": "left", "ends": (6, 6)},
    {"player": 3, "tile": None, "end": "pass", "ends": (3, 6)},
]


def ctx(player=0):
    return build_bot_context(
        player_index=player,
        config=TEAMS,
        board=[Domino(3, 6), Domino(6, 6)],
        ends=(3, 6),
        hand_counts=[6, 7, 6, 7],
        move_history=HISTORY,
    )


def test_context_supports_attribute_access():
    c = ctx()
    assert c.player_id == 0
    assert c.ends == (3, 6)
    assert c.hand_counts == [6, 7, 6, 7]


def test_context_still_behaves_like_the_old_dict():
    c = ctx()
    assert isinstance(c, BotContext)
    assert c["player_index"] == 0
    assert c.get("capicu_bonus") == 100
    assert c.get("not_a_field", "default") == "default"
    assert "teammate_played_numbers" in c


def test_a_pass_records_a_void_in_both_ends_it_faced():
    c = ctx()
    assert c.known_voids[1] == [6]  # passed against (6, 6)
    assert c.known_voids[3] == [3, 6]  # passed against (3, 6)
    assert c.known_voids[0] == []


def test_pass_counts_are_per_player_totals():
    assert ctx().pass_counts == [0, 1, 0, 1]


def test_teammate_and_opponent_plays_are_split_by_seat():
    c = ctx(player=0)
    assert c.teammate_index == 2
    assert c.teammate_played_numbers[3] == 1  # partner played 6|3
    assert c.teammate_played_numbers[6] == 1
    assert c.opponent_played_numbers[6] == 0  # neither opponent has played


def test_own_tiles_are_excluded_from_the_opponent_counts():
    c = ctx(player=0)
    # Seat 0 opened with 6|6 -- that is not opponent information.
    assert c.opponent_played_numbers[6] == 0
    assert c.played_numbers[6] == 3  # 6|6 twice, plus the 6 of 6|3


def test_ffa_has_no_teammate():
    c = build_bot_context(
        player_index=0,
        config=MatchConfig(target_points=200, mode=GameMode.FFA),
        board=[],
        ends=None,
        hand_counts=[7, 7, 7, 7],
        move_history=HISTORY,
    )
    assert c.teammate_index is None
    assert sum(c.teammate_played_numbers.values()) == 0
