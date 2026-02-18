# Puerto Rican Dominoes

A full-stack Puerto Rican dominoes game with a human-playable UI and a bot arena. Built with a **FastAPI** backend and a **JavaScript** frontend.

📖 **New to Puerto Rican Dominoes?** Read the rules [here](https://www.pagat.com/tile/wdom/puerto_rico.html).

---

## Features

- Play Puerto Rican dominoes against bots or other players
- Bot arena: pit bots against each other and watch them play
- Modular bot interface, drop in your own strategy with minimal boilerplate

---

## Prerequisites

Make sure you have the following installed:

- **Python 3.9+**
- **Node.js 18+** and **npm**
- **Make** (optional, but recommended)

---

## Setup & Running

### Option 1: Using Make (Recommended)

From the project root, run both the backend and frontend in one command:

```bash
make dev
```

### Option 2: Manual Setup

**Backend**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Once both are running, open your browser and navigate to the URL shown in the frontend terminal (typically `http://localhost:5173`).

---


## Implementing Your Own Bot

Bots live in `backend/bots/`. To create a new bot, create a new Python file in that directory and implement the base bot interface.

### Step 1: Create your bot file

```python
# backend/bots/my_bot.py

from .base_bot import BaseBot

class MyBot(BaseBot):
    """
    A custom Puerto Rican Dominoes bot.
    """

    def choose_move(self, game_state: dict) -> dict:
        """
        Given the current game state, return the move to make.

        Args:
            game_state: A dictionary containing:
                - "hand":          List of dominoes in your hand, e.g. [[3,5], [6,6], ...]
                - "board":         The current board state (left end, right end, full chain)
                - "valid_moves":   List of valid moves you can make
                - "scores":        Current scores for both teams
                - "player_id":     Your player index (0–3)
                - "team":          Your team (0 or 1)
                - "pass_required": Boolean — True if you must pass this turn

        Returns:
            A move dict from valid_moves, e.g.:
                {"domino": [3, 5], "side": "left"}   # play [3|5] on the left end
            Or to pass:
                {"pass": True}
        """

        valid_moves = game_state["valid_moves"]

        if not valid_moves:
            return {"pass": True}

        # --- Your strategy goes here ---
        # Example: just pick the first valid move
        return valid_moves[0]
```

### Step 2: Register your bot

Open `backend/bots/__init__.py` and add your bot to the registry:

```python
from .random_bot import RandomBot
from .my_bot import MyBot   # <-- add this

BOT_REGISTRY = {
    "random": RandomBot,
    "my_bot": MyBot,        # <-- and this
}
```

### Step 3: Use your bot in the arena

Once registered, your bot's key (`"my_bot"`) will appear as an option in the bot arena UI, where you can select it for any of the four player slots.

### Tips for writing a stronger bot

- **Count suits**: Track which numbers have been played to infer what opponents are holding.
- **Block opponents**: Play to cut off the numbers your opponents need to connect.
- **Prioritize doubles**: Doubles can only be played on one number; get rid of them early.
- **Team awareness**: Players 0 & 2 are one team, players 1 & 3 are the other. Use `game_state["team"]` to coordinate strategy.

## License

MIT
