import inspect
from typing import Optional
from .types import Domino
from .rules import legal_moves_for_hand


class BotBase:
    def choose_move(
        self,
        hand: list[Domino],
        ends,
        context: Optional[dict] = None,
    ) -> Optional[tuple[Domino, str]]:
        raise NotImplementedError


_ACCEPTS_CONTEXT: dict[type, bool] = {}


def accepts_context(bot: "BotBase") -> bool:
    """Whether this bot's choose_move takes the context argument.

    Worked out from the signature once per class, not by calling with three
    arguments and retrying on TypeError. That retry could not tell "this bot
    only takes two arguments" from "this bot raised TypeError in its own code",
    so a bot with a type error inside it was quietly run a second time without
    its context -- executing the author's logic twice and reporting the failure
    from the wrong call.
    """
    cls = type(bot)
    known = _ACCEPTS_CONTEXT.get(cls)
    if known is None:
        try:
            params = inspect.signature(bot.choose_move).parameters
        except (TypeError, ValueError):
            known = True  # unintrospectable; assume the documented signature
        else:
            known = len(params) >= 3 or any(
                p.kind is inspect.Parameter.VAR_KEYWORD
                or p.kind is inspect.Parameter.VAR_POSITIONAL
                for p in params.values()
            )
        _ACCEPTS_CONTEXT[cls] = known
    return known


def call_bot(bot: "BotBase", hand, ends, context=None):
    """Ask a bot for its move, passing context only if it takes one."""
    if accepts_context(bot):
        return bot.choose_move(hand, ends, context)
    return bot.choose_move(hand, ends)


def coerce_move(result, legal):
    """Turn whatever a bot returned into something safe to play.

    Uploaded bots return whatever they return. Returns (move, complaint):
    `move` is a legal (tile, end) or None to pass, and `complaint` describes
    what was wrong so the caller can report it rather than silently playing
    something else. A bot that names an illegal move forfeits the choice --
    it gets the first legal one -- instead of corrupting the board.
    """
    if result is None:
        if not legal:
            return None, None
        # A pass is only legal with nothing to play. Callers ask a bot for a
        # move only when there is one, so a None here would otherwise let an
        # uploaded bot manufacture a tranque by refusing to play.
        return legal[0], "passed with legal moves available"
    try:
        move = tuple(result)
    except TypeError:
        move = None
    if move is None or len(move) != 2:
        kind = type(result).__name__
        return (legal[0] if legal else None), f"returned {kind}, expected (tile, end)"
    if move not in legal:
        return (legal[0] if legal else None), f"returned an illegal move {move}"
    return move, None


class GreedyBot(BotBase):
    def choose_move(self, hand: list[Domino], ends, context: Optional[dict] = None):
        legal = legal_moves_for_hand(hand, ends)
        if not legal:
            return None

        def score(move):
            tile, end = move
            s = tile.pips()
            if tile.is_double():
                s -= 0.5
            return s

        return max(legal, key=score)
