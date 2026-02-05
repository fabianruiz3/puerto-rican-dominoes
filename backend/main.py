from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
from dominoes.types import MatchConfig, GameMode
from dominoes.game import MatchState
from session_store import create_match, get_match, save_match


class StartMatchRequest(BaseModel):
    target_points: int = 200
    mode: Literal["ffa", "teams"] = "ffa"


class PlayMoveRequest(BaseModel):
    tile_index: int
    end: Literal["left", "right", "start"]


class PassRequest(BaseModel):
    pass


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_bots(match: MatchState):
    from dominoes.rules import legal_moves_for_hand
    while True:
        hs = match.hand_state
        if hs is None:
            break
        if match.is_hand_over():
            match.resolve_hand()
            if not match.is_match_over():
                match.start_new_hand()
            break
        idx = hs.current_player
        bot = match.bots[idx]
        if bot is None:
            break
        player = match.players[idx]
        legal = legal_moves_for_hand(player.hand, hs.ends)
        if not legal:
            match.pass_turn()
            match.next_player()
            continue
        tile, end = bot.choose_move(player.hand, hs.ends)
        match.play_tile(idx, tile, end)
        match.next_player()


@app.post("/api/match")
def start_match(req: StartMatchRequest):
    mode = GameMode.FFA if req.mode == "ffa" else GameMode.TEAMS
    config = MatchConfig(target_points=req.target_points, mode=mode)
    match = MatchState.new_with_default_bots(config)
    match.start_new_hand()
    run_bots(match)
    game_id = create_match(match)
    return {"gameId": game_id, "state": match.to_dict()}


@app.get("/api/match/{game_id}")
def get_state(game_id: str):
    try:
        match = get_match(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Match not found")
    return {"gameId": game_id, "state": match.to_dict()}


@app.post("/api/match/{game_id}/play")
def play_move(game_id: str, req: PlayMoveRequest):
    try:
        match = get_match(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Match not found")
    hs = match.hand_state
    if hs is None:
        raise HTTPException(status_code=400, detail="No active hand")
    if hs.current_player != 0:
        raise HTTPException(status_code=400, detail="Not human turn")
    player = match.players[0]
    if not (0 <= req.tile_index < len(player.hand)):
        raise HTTPException(status_code=400, detail="Invalid tile index")
    tile = player.hand[req.tile_index]
    match.play_tile(0, tile, req.end)
    match.next_player()
    run_bots(match)
    save_match(game_id, match)
    return {"gameId": game_id, "state": match.to_dict()}


@app.post("/api/match/{game_id}/pass")
def pass_turn(game_id: str):
    try:
        match = get_match(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Match not found")
    hs = match.hand_state
    if hs is None:
        raise HTTPException(status_code=400, detail="No active hand")
    if hs.current_player != 0:
        raise HTTPException(status_code=400, detail="Not human turn")
    match.pass_turn()
    match.next_player()
    run_bots(match)
    save_match(game_id, match)
    return {"gameId": game_id, "state": match.to_dict()}
