from flask import Blueprint, render_template, request, redirect, url_for
from dominoes.types import MatchConfig, GameMode, PlayerState
from dominoes.game import MatchState
from dominoes import bots
from .session_store import create_match, get_match, save_match

bp = Blueprint("game", __name__)


@bp.app_template_filter()
def tile_image(tile):
    """Generate image filename for a tile (0-0.png format)"""
    a, b = tile.a, tile.b
    return f"{min(a, b)}-{max(a, b)}.png"

@bp.app_template_filter()
def tile_needs_flip(tile):
    """Check if tile needs to be flipped horizontally for display"""
    # If a > b, the tile is stored backwards compared to the filename
    return tile.a > tile.b


@bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@bp.route("/start", methods=["POST"])
def start():
    target = int(request.form.get("target_points", "200"))
    mode_str = request.form.get("mode", "ffa")
    mode = GameMode.FFA if mode_str == "ffa" else GameMode.TEAMS

    config = MatchConfig(target_points=target, mode=mode)

    # players: P0 is human, P1-3 bots
    players = [PlayerState(index=i) for i in range(4)]
    bot_list = [None, bots.GreedyBot(), bots.GreedyBot(), bots.GreedyBot()]

    match = MatchState(config=config, players=players, bots=bot_list)
    match.start_new_hand()
    game_id = create_match(match)
    return redirect(url_for("game.view_game", game_id=game_id))


@bp.route("/game/<game_id>", methods=["GET"])
def view_game(game_id):
    match = get_match(game_id)

    # auto-play bots until it's human's turn or hand ends
    from dominoes.rules import legal_moves

    while True:
        hs = match.hand_state
        player_idx = hs.current_player_idx
        bot = match.bots[player_idx]

        # break if it's human or hand ended
        if match.is_hand_over() or bot is None:
            break

        player = match.players[player_idx]
        legal = legal_moves(player.hand, hs.ends)

        if not legal:
            match.pass_turn()
            match.next_player()
            continue

        tile, end = bot.choose_move(player.hand, hs.ends)
        if tile is None:
            match.pass_turn()
            match.next_player()
            continue
        match.play_tile(player_idx, tile, end)
        match.next_player()

    # check if hand over
    if match.is_hand_over():
        match.resolve_hand()
        if not match.is_match_over():
            match.start_new_hand()
        save_match(game_id, match)

    return render_template(
        "game.html",
        game_id=game_id,
        match=match,
    )


@bp.route("/play/<game_id>", methods=["POST"])
def play(game_id):
    match = get_match(game_id)
    hs = match.hand_state
    player_idx = hs.current_player_idx
    assert player_idx == 0  # human is player 0

    tile_index = int(request.form["tile_index"])
    end = request.form["end"]  # "left" or "right"

    tile = match.players[0].hand[tile_index]
    
    # Validate move is legal
    from dominoes.rules import legal_moves
    legal = legal_moves(match.players[0].hand, hs.ends)
    if tile not in legal:
        # Invalid move, redirect back
        return redirect(url_for("game.view_game", game_id=game_id))
    
    # Validate can play on this end
    if not match.can_play_on_end(tile, end):
        # Can't play on this specific end, reject the move
        return redirect(url_for("game.view_game", game_id=game_id))
    
    match.play_tile(player_idx, tile, end)
    match.next_player()
    save_match(game_id, match)
    return redirect(url_for("game.view_game", game_id=game_id))


@bp.route("/pass/<game_id>", methods=["POST"])
def pass_turn(game_id):
    match = get_match(game_id)
    hs = match.hand_state
    player_idx = hs.current_player_idx
    assert player_idx == 0  # human is player 0
    
    match.pass_turn()
    match.next_player()
    save_match(game_id, match)
    return redirect(url_for("game.view_game", game_id=game_id))