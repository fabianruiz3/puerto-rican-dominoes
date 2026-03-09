import importlib.util
import sys
import os
import tempfile
from dominoes.bots import BotBase

def load_bot_from_source(source_code: str, name: str='user_bot') -> BotBase:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', prefix=f'bot_{name}_', delete=False) as f:
        f.write(source_code)
        tmp_path = f.name
    try:
        module_name = f'_arena_bot_{name}_{id(source_code)}'
        spec = importlib.util.spec_from_file_location(module_name, tmp_path)
        if spec is None or spec.loader is None:
            raise ValueError(f'Could not load bot module from source')
        module = importlib.util.module_from_spec(spec)
        module.__dict__['BotBase'] = BotBase
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        bot_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BotBase) and (attr is not BotBase):
                bot_class = attr
                break
        if bot_class is None:
            raise ValueError(f'No BotBase subclass found in uploaded file. Your bot must define a class that inherits from BotBase and implements choose_move(hand, ends).')
        return bot_class()
    finally:
        os.unlink(tmp_path)
        if module_name in sys.modules:
            del sys.modules[module_name]