"""The HTTP surface, including the rules it has to enforce for the human seat.

The bots go through MatchState.legal_moves, so they cannot break a rule. The
human's move arrives as a tile index and an end over HTTP, and the API is the
only thing standing between that and the board.
"""

import random

import pytest
from fastapi.testclient import TestClient

import main
from bots.registry import available, cfr_available, make, seat_bots
from dominoes.rules import OPENING_TILE


@pytest.fixture
def client():
    return TestClient(main.app)


# ------------------------------------------------------------------- registry


def test_the_registry_lists_the_seatable_bots(client):
    names = {b["name"] for b in client.get("/api/bots").json()["bots"]}
    assert names == {"greedy", "random", "cfr"}


def test_cfr_is_reported_unready_until_a_policy_is_installed():
    entry = next(b for b in available() if b["name"] == "cfr")
    assert entry["ready"] == cfr_available()


def test_asking_for_cfr_without_a_policy_is_a_clear_error():
    if cfr_available():
        pytest.skip("a trained policy is installed")
    with pytest.raises(FileNotFoundError, match="No trained CFR policy"):
        make("cfr")


def test_an_unknown_bot_name_is_rejected():
    with pytest.raises(KeyError):
        make("nope")


def test_seat_bots_leaves_the_human_seat_empty():
    seats = seat_bots("greedy", human_seat=0)
    assert seats[0] is None
    assert all(s is not None for s in seats[1:])


# ----------------------------------------------------------------- match flow


@pytest.mark.parametrize("opponent", ["greedy", "random"])
def test_a_match_starts_with_each_available_opponent(client, opponent):
    r = client.post("/api/match", json={"mode": "teams", "opponent": opponent})
    assert r.status_code == 200
    state = r.json()["state"]
    assert state["hand_number"] == 1
    assert len(state["players"][0]["hand"]) <= 7


def test_requesting_cfr_without_a_policy_returns_a_conflict(client):
    if cfr_available():
        pytest.skip("a trained policy is installed")
    r = client.post("/api/match", json={"opponent": "cfr"})
    assert r.status_code == 409
    assert "cluster/README.md" in r.json()["detail"]


def find_match_where_human_must_lead(client, attempts=60):
    """A match where seat 0 holds the double six and so owes the opening."""
    for seed in range(attempts):
        random.seed(seed)
        r = client.post("/api/match", json={"mode": "teams", "opponent": "greedy"})
        body = r.json()
        hs = body["state"]["hand_state"]
        if hs["forced_tile"] is not None and hs["current_player"] == 0:
            return body["gameId"], body["state"]
    pytest.skip("no seed in range dealt the double six to seat 0")


def test_the_human_cannot_open_with_anything_but_the_double_six(client):
    game_id, state = find_match_where_human_must_lead(client)
    hand = state["players"][0]["hand"]
    wrong = next(
        i for i, t in enumerate(hand) if (t["a"], t["b"]) != (OPENING_TILE.a, OPENING_TILE.b)
    )
    r = client.post(f"/api/match/{game_id}/play", json={"tile_index": wrong, "end": "start"})
    assert r.status_code == 400
    assert "must be the 6|6" in r.json()["detail"]


def test_the_human_can_open_with_the_double_six(client):
    game_id, state = find_match_where_human_must_lead(client)
    hand = state["players"][0]["hand"]
    right = next(
        i for i, t in enumerate(hand) if (t["a"], t["b"]) == (OPENING_TILE.a, OPENING_TILE.b)
    )
    r = client.post(f"/api/match/{game_id}/play", json={"tile_index": right, "end": "start"})
    assert r.status_code == 200
    assert r.json()["state"]["hand_state"]["forced_tile"] is None


def test_an_illegal_placement_is_refused(client):
    random.seed(3)
    body = client.post("/api/match", json={"mode": "teams"}).json()
    game_id, state = body["gameId"], body["state"]
    hs = state["hand_state"]
    if hs["ends"] is None or hs["current_player"] != 0:
        pytest.skip("seed did not leave the human on turn with a board")
    left, right = hs["ends"]["left"], hs["ends"]["right"]
    hand = state["players"][0]["hand"]
    bad = next(
        (i for i, t in enumerate(hand) if left not in (t["a"], t["b"]) and right not in (t["a"], t["b"])),
        None,
    )
    if bad is None:
        pytest.skip("every tile in hand was playable")
    r = client.post(f"/api/match/{game_id}/play", json={"tile_index": bad, "end": "left"})
    assert r.status_code == 400


def test_passing_with_a_legal_move_available_is_refused(client):
    random.seed(1)
    body = client.post("/api/match", json={"mode": "teams"}).json()
    game_id, state = body["gameId"], body["state"]
    if state["hand_state"]["current_player"] != 0:
        pytest.skip("seed did not leave the human on turn")
    hs = state["hand_state"]
    ends = hs["ends"]
    hand = state["players"][0]["hand"]
    if ends is not None:
        playable = any(
            ends["left"] in (t["a"], t["b"]) or ends["right"] in (t["a"], t["b"])
            for t in hand
        )
        if not playable:
            pytest.skip("the human genuinely had to pass")
    r = client.post(f"/api/match/{game_id}/pass")
    assert r.status_code == 400
    assert "cannot pass" in r.json()["detail"]


def test_an_unknown_match_id_is_a_404(client):
    assert client.get("/api/match/does-not-exist").status_code == 404


def test_a_match_starts_against_cfr_once_a_policy_is_installed(client):
    if not cfr_available():
        pytest.skip("no trained policy installed")
    r = client.post("/api/match", json={"mode": "teams", "opponent": "cfr"})
    assert r.status_code == 200
    assert r.json()["state"]["hand_number"] == 1


def test_the_installed_policy_loads_and_plays_the_mode(client):
    if not cfr_available():
        pytest.skip("no trained policy installed")
    bot = make("cfr")
    assert bot.policy.n_infosets > 1000
    assert bot.sample is False


def test_the_three_cfr_seats_share_one_loaded_policy():
    if not cfr_available():
        pytest.skip("no trained policy installed")
    seats = [s for s in seat_bots("cfr") if s is not None]
    assert len(seats) == 3
    assert all(s.policy is seats[0].policy for s in seats)
    # Shared table, independent bots.
    assert len({id(s) for s in seats}) == 3
    assert all(s.hits == 0 for s in seats)
