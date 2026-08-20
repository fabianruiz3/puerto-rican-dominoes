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

Bots implement one method. Upload a `.py` file in the arena UI, or drop it in
`backend/bots/` -- there is no registry to edit; the arena loads whatever class
in your file subclasses `BotBase`.

```python
# backend/bots/my_bot.py

from dominoes.bots import BotBase
from dominoes.rules import legal_moves_for_hand


class MyBot(BotBase):
    def choose_move(self, hand, ends, context=None):
        legal = legal_moves_for_hand(hand, ends)
        if not legal:
            return None            # you have nothing playable; you must pass
        return legal[0]            # your strategy goes here
```

`choose_move` returns a `(tile, end)` pair from `legal`, or `None` to pass.

| argument | what it is |
| --- | --- |
| `hand` | `list[Domino]`, each with `.a`, `.b`, `.pips()`, `.is_double()` |
| `ends` | `(left, right)`, or `None` when the board is empty |
| `context` | the public view of the hand (below) |

`context` is everything you are allowed to see. Both styles work --
`context.board` and `context["board"]` are the same thing:

| field | what it is |
| --- | --- |
| `player_id` | your seat, 0-3 |
| `teammate_index` | your partner's seat in teams mode, `None` in FFA |
| `board` | `list[Domino]` already played, in chain order |
| `ends` | the same `(left, right)` you were passed |
| `hand_counts` | tiles remaining per seat |
| `pass_counts` | how many times each seat has passed |
| `known_voids` | numbers each seat has proven not to hold |
| `played_numbers` | pip-slots of each number already on the board |
| `teammate_played_numbers` | the same, restricted to your partner |
| `opponent_played_numbers` | the same, restricted to your opponents |
| `move_history` | every move so far, with the ends each seat faced |
| `forced_tile` | the tile you are required to lead, or `None` |
| `capicu_bonus`, `chuchazo_bonus` | the bonuses in play |

`known_voids` is the one worth dwelling on. A seat that passes against ends
`(3, 5)` has proven it holds no threes and no fives, and that inference is
most of what separates a strong dominoes player from a greedy one.

### Tips for a stronger bot

- **Count the numbers.** `played_numbers` plus your own hand bounds what is
  still out there.
- **Watch the passes.** `known_voids` tells you which numbers to keep feeding.
- **Play to your partner.** Feed numbers your partner has played; starve the
  ones your opponents keep answering.
- **Shed weight before a tranque.** A blocked hand is settled on pips, so heavy
  tiles left in hand cost you the hand.
- **Doubles are stiff.** A double only attaches on one number; strand one and
  you pass all night.

---

## The CFR Bot

`backend/cfr/` trains a bot with external-sampling Monte Carlo CFR, the
algorithm behind modern poker bots, adapted to a partnership tile game.

```bash
cd backend
python3 -m cfr.train --out runs/tiny --level tiny --iters 20000 --rounds 8
python3 -m cfr.evaluate --policy runs/tiny/policy.npz --matches 2000
```

`cluster/README.md` covers training it properly on MIT Engaging; a laptop run
is for checking the pipeline, not for producing a strong policy.

### How it works

A hand is solved rather than a whole match: the payoff is the hand's point
swing, which keeps the tree about 22 moves deep instead of chasing score
dependence across a match to 200.

The real problem is that dealing 28 tiles four ways gives 4.7e14 deals, so no
table can be keyed on the literal position. Positions are compressed into
information sets built only from what the acting seat can see -- the board, how
many tiles each seat holds, what each has shown void in, and how its own hand
relates to the two open ends. Four levels trade description against coverage:

| level | information sets | decisions the table can answer |
| --- | --- | --- |
| `standard` | 1.94M | 55% |
| `coarse` | 934k | 85% |
| `compact` | 361k | 90% |
| `tiny` | 34.8k | 99% |

Measured at equal training. A finer level describes each position better but
spreads the run across so many information sets that the ones arising in play
are never visited; `tiny` is nearly always able to say something. Which point
on that curve actually plays best is settled by `cluster/cfr_sweep.sbatch`,
which trains all four at equal compute and evaluates each.

Where the table has nothing usable, `CFRBot` falls back to `GreedyBot`, so
incomplete coverage costs accuracy rather than the hand.

### A caveat worth stating

CFR's convergence guarantee is for two-player zero-sum games. Teams dominoes is
zero-sum between the two teams, but a team is two seats that cannot see each
other's tiles, so it is not a two-player game and the guarantee does not carry
over. CFR is used here as a strong self-play procedure -- the same way it is
used for bridge and other partnership games -- and the evidence that it works
is the arena win rate, not a theorem.

That makes an independent check on the solver essential, so the same traversal
that trains the bot is run against Rock-Paper-Scissors and Kuhn poker, whose
solutions are known in closed form, and asserted to recover them. The cluster
jobs re-run that gate before training rather than spending twelve hours finding
out afterwards.

---

## License

MIT

