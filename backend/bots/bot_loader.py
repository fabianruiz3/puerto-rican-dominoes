"""Loading a bot from uploaded source.

The arena runs whatever class an uploaded file defines. Working out *which*
class that is has to be done carefully: picking the first BotBase subclass that
turns up in dir() sorts alphabetically and does not distinguish a class the
file defines from one it imported, so a file that does

    from bots.greedy_bot import GreedyBot   # to compare against

silently ran GreedyBot instead of the author's bot, and the arena benchmarked
greedy against itself with no indication anything was wrong.

Only classes defined in the uploaded file count. If a file defines more than
one, it says so and asks for `BOT = YourBot` rather than guessing.
"""

import importlib.util
import os
import sys
import tempfile

from dominoes.bots import BotBase


def _defined_here(module, module_name: str) -> list[type]:
    """BotBase subclasses the module defines itself, in source order."""
    found = []
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, BotBase)
            and attr is not BotBase
            and getattr(attr, "__module__", None) == module_name
        ):
            found.append(attr)
    # dir() is alphabetical; sort by where the class appears in the file so the
    # message reads in the order the author wrote them. __firstlineno__ is 3.13+,
    # so fall back to the name to stay deterministic on older interpreters.
    return sorted(found, key=lambda c: (getattr(c, "__firstlineno__", 0), c.__name__))


def _select(module, module_name: str) -> type:
    explicit = getattr(module, "BOT", None)
    if explicit is not None:
        if isinstance(explicit, type) and issubclass(explicit, BotBase):
            return explicit
        raise ValueError("BOT must be a class inheriting from BotBase.")

    defined = _defined_here(module, module_name)
    if len(defined) == 1:
        return defined[0]
    if not defined:
        raise ValueError(
            "No bot class found. Your file must define a class that inherits "
            "from BotBase and implements choose_move(hand, ends, context=None). "
            "Classes imported from elsewhere do not count."
        )
    names = ", ".join(c.__name__ for c in defined)
    raise ValueError(
        f"Your file defines more than one bot class ({names}). Add a line "
        f"naming the one to run, for example: BOT = {defined[-1].__name__}"
    )


def load_bot_from_source(source_code: str, name: str = "user_bot") -> BotBase:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix=f"bot_{name}_", delete=False
    ) as f:
        f.write(source_code)
        tmp_path = f.name
    module_name = f"_arena_bot_{name}_{id(source_code)}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, tmp_path)
        if spec is None or spec.loader is None:
            raise ValueError("Could not load bot module from source")
        module = importlib.util.module_from_spec(spec)
        module.__dict__["BotBase"] = BotBase
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return _select(module, module_name)()
    finally:
        os.unlink(tmp_path)
        sys.modules.pop(module_name, None)
