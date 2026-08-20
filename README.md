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
algorithm behind modern poker bots, adapted to a partnership tile game. A
trained policy ships in the tree, so `cfr` is a selectable opponent on
checkout.

| matchup | win rate | 95% CI |
| --- | --- | --- |
| **cfr vs greedy** | **58.5%** | [56.3%, 60.6%] |
| cfr vs random | 75.0% | [73.0%, 76.8%] |
| greedy vs random | 60.7% | [58.5%, 62.8%] |

2,000 matches to 200, each pairing played twice with the seats swapped so the
advantage of opening the match cancels.

```bash
cd backend
python3 -m cfr.train --out runs/coarse --iters 20000 --rounds 12
python3 -m cfr.evaluate --policy runs/coarse/policy.npz --matches 2000
```

`cluster/README.md` covers training at scale on MIT Engaging. The shipped
policy came from 4.8M traversals on 32 cores for an hour.

### How it works

A hand is solved rather than a whole match: the payoff is the hand's point
swing, which keeps the tree about 22 moves deep instead of chasing score
dependence across a match to 200.

The hard part is that dealing 28 tiles four ways gives 4.7e14 deals, so nothing
can be keyed on the literal position. Positions compress into information sets
built only from what the acting seat can see -- the board, how many tiles each
seat holds, what each has shown void in, and how its own hand relates to the
two open ends. Four levels trade description against coverage.

Where the table has nothing to say, `CFRBot` falls back to `GreedyBot`, so
incomplete coverage costs accuracy rather than the hand. The shipped policy
answers about 90% of the decisions it meets.

The bot plays the highest-probability action rather than sampling from the
distribution, which is worth several points. Mixing is what makes an
equilibrium strategy unexploitable, but that only pays against an opponent
adapting to you; against fixed opponents it adds noise to a decision the table
has already made. Pass `--sample` to compare.

### The abstraction is not a coverage problem

The obvious way to pick an abstraction is to make it coarse enough that
training covers the positions that actually come up. Measured that way the
smallest level looks best by a mile -- it answers 99% of decisions against 55%
for the most detailed one.

It is also the worst bot. Trained at equal compute, 4.8M traversals each:

| level | information sets | decisions answered | vs greedy |
| --- | --- | --- | --- |
| `tiny` | 82,644 | 100% | 42.5% |
| `compact` | 4,283,414 | 99.9% | 48.8% |
| `coarse` | 13,750,671 | 99.7% | **59.4%** |

Coverage ranks them exactly backwards. Once the lookups land at all, what
matters is whether the abstraction can still tell good positions from bad ones,
and `tiny` cannot: it drops pip identity and most of the hand's shape, so
positions with genuinely different values collapse together and the strategy
that is optimal for the merged game is bad in the real one.

### Training a lossy abstraction longer makes it worse

The `tiny` level is a clean demonstration of abstraction pathology. Same code,
same abstraction, same evaluation -- only the amount of training differs:

| traversals | vs greedy |
| --- | --- |
| 384,000 (seed 5) | 56.3% |
| 384,000 (seed 99) | 54.2% |
| 4,800,000 | 42.5% |

Undertrained, it beats the heuristic; converged, it loses badly. Both ends
reproduce across seeds, so this is not a lucky run. CFR is converging correctly
-- to an equilibrium of an abstract game that is not the game being played.

The practical consequence is that a policy cannot be judged by how well it was
solved, only by playing it. `cluster/cfr_sweep.sbatch` trains every level at
equal compute and evaluates each, which is how `coarse` was chosen.

### Pruning

Training keeps every information set it touched -- 232 MB at `coarse`. Most of
that is positions visited a handful of times whose averaged strategy is still
close to noise, and the heuristic fallback handles a miss at least as well:

| kept | size | decisions answered | vs greedy |
| --- | --- | --- | --- |
| all 13.75M | 232 MB | 99.7% | 59.4% |
| 1.35M | 39 MB | 94.4% | 59.3% |
| **688k** | **20 MB** | **89.6%** | **58.8%** |
| 356k | 10 MB | 83.6% | 56.8% |
| 139k | 4 MB | 73.0% | 53.6% |

The shipped policy is the 20 MB row -- 94% of the win-rate edge at under a
tenth of the size. `python3 -m cfr.export --checkpoint ... --scan` prints this
table for any run.

### A caveat

CFR's convergence guarantee is for two-player zero-sum games. This is zero-sum
between two teams, but a team is two seats that cannot see each other's tiles,
so it is not a two-player game and the guarantee does not carry over. CFR is
used here as a strong self-play procedure -- the same way it is used for bridge
and other partnership games -- and the evidence that it works is the arena win
rate, not a theorem.

That makes an independent check on the solver essential, so the same traversal
that trains the bot is run against Rock-Paper-Scissors and Kuhn poker, whose
solutions are known in closed form, and asserted to recover them. The cluster
jobs re-run that gate before training rather than spending hours finding out
afterwards.

---

## License

MIT

