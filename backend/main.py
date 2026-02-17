from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
    if req.end != "start" and hs.ends is not None:
        left, right = hs.ends
        if req.end == "left" and tile.a != left and tile.b != left:
            raise HTTPException(status_code=400, detail=f"Tile {tile.a}|{tile.b} cannot play on left end {left}")
        if req.end == "right" and tile.a != right and tile.b != right:
            raise HTTPException(status_code=400, detail=f"Tile {tile.a}|{tile.b} cannot play on right end {right}")

    try:
        match.play_tile(0, tile, req.end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    match.next_player()
    run_bots(match)
    save_match(game_id, match)
    return {"gameId": game_id, "state": match.to_dict()}


@app.post("/api/match/{game_id}/pass")
def pass_turn(game_id: str):
    from dominoes.rules import legal_moves_for_hand
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
    legal = legal_moves_for_hand(player.hand, hs.ends)
    if legal:
        raise HTTPException(status_code=400, detail="You have legal moves and cannot pass")
    match.pass_turn()
    match.next_player()
    run_bots(match)
    save_match(game_id, match)
    return {"gameId": game_id, "state": match.to_dict()}


@app.post("/api/match/{game_id}/next_hand")
def next_hand(game_id: str):
    try:
        match = get_match(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.is_match_over():
        raise HTTPException(status_code=400, detail="Match is over")
    if match.last_hand_result is None:
        raise HTTPException(status_code=400, detail="No hand result to continue from")
    match.start_new_hand()
    run_bots(match)
    save_match(game_id, match)
    return {"gameId": game_id, "state": match.to_dict()}


_arena_results = {}

@app.post("/api/arena/run")
async def run_arena_endpoint(
    bot_a: UploadFile = File(...),
    bot_b: UploadFile = File(...),
    num_matches: int = Form(default=1000),
    target_points: int = Form(default=200),
):
    from bots.bot_loader import load_bot_from_source
    from bots.arena import run_arena
    from uuid import uuid4

    try:
        src_a = (await bot_a.read()).decode("utf-8")
        src_b = (await bot_b.read()).decode("utf-8")
    except Exception as e:
        print(f"Error reading files: {e}")
        raise HTTPException(status_code=400, detail="Could not read uploaded files")

    try:
        bot_a_inst = load_bot_from_source(src_a, "bot_a")
    except Exception as e:
        print(f"Error loading Bot A: {e}")
        raise HTTPException(status_code=400, detail=f"Error loading Bot A: {str(e)}")

    try:
        bot_b_inst = load_bot_from_source(src_b, "bot_b")
    except Exception as e:
        print(f"Error loading Bot B: {e}")
        raise HTTPException(status_code=400, detail=f"Error loading Bot B: {str(e)}")

    num_matches = min(num_matches, 5000)
    target_points = max(50, min(target_points, 1000))

    try:
        results = run_arena(
            bot_a=bot_a_inst,
            bot_b=bot_b_inst,
            num_matches=num_matches,
            target_points=target_points,
        )
    except Exception as e:
        print(f"Arena execution error: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Arena error: {str(e)}")

    arena_id = str(uuid4())
    results["arena_id"] = arena_id
    results["bot_a_name"] = bot_a.filename or "Bot A"
    results["bot_b_name"] = bot_b.filename or "Bot B"

    stored = {**results}
    stored["matches"] = results["matches"][:50]
    stored["total_matches_stored"] = len(stored["matches"])
    _arena_results[arena_id] = stored

    summary = {k: v for k, v in results.items() if k != "matches"}
    summary["matches_stored"] = min(50, num_matches)
    return summary


@app.get("/api/arena/{arena_id}")
def get_arena_results(arena_id: str):
    if arena_id not in _arena_results:
        raise HTTPException(status_code=404, detail="Arena results not found")
    return _arena_results[arena_id]


@app.get("/api/arena/{arena_id}/match/{match_idx}")
def get_arena_match(arena_id: str, match_idx: int):
    if arena_id not in _arena_results:
        raise HTTPException(status_code=404, detail="Arena results not found")
    results = _arena_results[arena_id]
    if match_idx < 0 or match_idx >= len(results["matches"]):
        raise HTTPException(status_code=404, detail="Match not found")
    return results["matches"][match_idx]
