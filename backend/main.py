from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from collections import OrderedDict
from typing import Literal
from dominoes.types import MatchConfig, GameMode
from dominoes.bots import call_bot, coerce_move
from dominoes.game import MatchState
from session_store import create_match, get_match, save_match


class StartMatchRequest(BaseModel):
    target_points: int = 200
    mode: Literal["ffa", "teams"] = "ffa"
    opponent: Literal["greedy", "random", "cfr"] = "greedy"


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
        legal = match.legal_moves(idx)
        if not legal:
            match.pass_turn()
            match.next_player()
            continue
        context = match.get_bot_context(idx)
        chosen, _ = coerce_move(
            call_bot(bot, match.players[idx].hand, hs.ends, context), legal
        )
        if chosen is None:
            match.pass_turn()
            match.next_player()
            continue
        match.play_tile(idx, *chosen)
        match.next_player()


@app.get("/api/bots")
def list_bots():
    from bots.registry import available

    return {"bots": available()}


def _active_hand(match, game_id: str):
    """The hand in progress, or a 400 explaining why there is not one.

    run_bots resolves a finished hand and stops, and if the seat it stops on is
    the human's, hand_state still says it is their turn. Without this check a
    play or a pass at that point runs run_bots again, which finds the hand
    still over and resolves it a second time -- paying the winning team twice
    for one hand, once per click.
    """
    hs = match.hand_state
    if hs is None:
        raise HTTPException(status_code=400, detail="No active hand")
    if match.last_hand_result is not None:
        raise HTTPException(
            status_code=400, detail="This hand is over; start the next one"
        )
    if match.is_match_over():
        raise HTTPException(status_code=400, detail="Match is over")
    if hs.current_player != 0:
        raise HTTPException(status_code=400, detail="Not human turn")
    return hs


@app.post("/api/match")
def start_match(req: StartMatchRequest):
    from bots.registry import seat_bots

    mode = GameMode.FFA if req.mode == "ffa" else GameMode.TEAMS
    config = MatchConfig(target_points=req.target_points, mode=mode)
    try:
        seats = seat_bots(req.opponent)
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    match = MatchState.new_with_bots(config, seats)
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
    hs = _active_hand(match, game_id)
    player = match.players[0]
    if not 0 <= req.tile_index < len(player.hand):
        raise HTTPException(status_code=400, detail="Invalid tile index")
    tile = player.hand[req.tile_index]
    legal = match.legal_moves(0)
    if (tile, req.end) not in legal:
        forced = hs.forced_tile if hs.ends is None else None
        if forced is not None:
            raise HTTPException(
                status_code=400,
                detail=f"The opening lead must be the {forced.a}|{forced.b}",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Tile {tile.a}|{tile.b} cannot play on the {req.end} end",
        )
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
    try:
        match = get_match(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Match not found")
    _active_hand(match, game_id)
    legal = match.legal_moves(0)
    if legal:
        raise HTTPException(
            status_code=400, detail="You have legal moves and cannot pass"
        )
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


# Arena results are held in memory for the replay viewer. Each run keeps 50
# matches with every hand and move, so an unbounded dict grows for as long as
# the server is up; keep the most recent handful and drop the rest.
_MAX_ARENA_RESULTS = 8
_arena_results: "OrderedDict[str, dict]" = OrderedDict()


def _remember_arena(arena_id: str, stored: dict) -> None:
    _arena_results[arena_id] = stored
    while len(_arena_results) > _MAX_ARENA_RESULTS:
        _arena_results.popitem(last=False)


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
    num_matches = max(1, min(num_matches, 5000))
    target_points = max(50, min(target_points, 1000))
    try:
        # An arena of a few thousand matches is tens of seconds of straight CPU.
        # Running it inline in an async endpoint holds the event loop for the
        # whole time, so every other request -- including a game in progress --
        # stalls until it finishes. Hand it to the threadpool instead.
        results = await run_in_threadpool(
            run_arena,
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
    _remember_arena(arena_id, stored)
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
