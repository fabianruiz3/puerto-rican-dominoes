"""Measure a trained policy against the heuristic baselines.

Reports a Wilson interval on the win rate, because a few hundred matches of
dominoes is noisy enough that a bare percentage invites reading signal into
nothing. Every pairing is played twice with the same seed, once with the
policy on seats 0+2 and once on 1+3, so the advantage of opening the match
cancels instead of landing on whoever happens to be Bot A.

Also reports the policy's hit rate: the share of decisions where the trained
table had something usable to say. A strong win rate on a 5% hit rate means
the heuristic fallback is doing the work, not CFR.
"""

import argparse
import math
import sys

from bots.arena import run_arena
from bots.cfr_bot import CFRBot
from bots.greedy_bot import GreedyBot
from bots.random_bot import RandomBot
from cfr.policy import Policy


def wilson(wins: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval -- behaves near 0 and 1, unlike the normal one."""
    if total == 0:
        return (0.0, 0.0)
    p = wins / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def head_to_head(bot_a, bot_b, matches: int, target: int, seed: int) -> dict:
    """Play both seat assignments and pool the result."""
    half = max(1, matches // 2)
    first = run_arena(bot_a, bot_b, half, target, seed=seed)
    second = run_arena(bot_a, bot_b, half, target, seed=seed, swap_seats=True)
    wins = first["team_a_wins"] + second["team_a_wins"]
    total = 2 * half
    lo, hi = wilson(wins, total)
    return {
        "wins": wins,
        "matches": total,
        "rate": wins / total,
        "lo": lo,
        "hi": hi,
        "seat_0_2": first["team_a_win_rate"],
        "seat_1_3": second["team_a_win_rate"],
        "seconds": first["elapsed_seconds"] + second["elapsed_seconds"],
    }


def report(name: str, r: dict) -> str:
    return (
        f"{name:<26} {r['rate']:>6.1%}  [{r['lo']:.1%}, {r['hi']:.1%}]  "
        f"{r['wins']:>5}/{r['matches']:<5}  seats 0+2 {r['seat_0_2']:.1%} / "
        f"1+3 {r['seat_1_3']:.1%}  {r['seconds']:.0f}s"
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--policy", required=True)
    p.add_argument("--matches", type=int, default=2000)
    p.add_argument("--target", type=int, default=200)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument(
        "--sample",
        action="store_true",
        help="draw from the average strategy instead of playing its mode",
    )
    args = p.parse_args(argv)

    policy = Policy.load(args.policy)
    print(
        f"policy {args.policy}\n"
        f"  level {policy.level}  infosets {policy.n_infosets:,}  "
        f"entries {len(policy):,}\n  meta {policy.meta}\n"
    )

    print(f"{'matchup':<26} {'win rate':>6}  {'95% CI':<18} {'record':<11} seats")
    print("-" * 100)

    results = {}
    for name, opponent in (("random", RandomBot()), ("greedy", GreedyBot())):
        bot = CFRBot(policy, sample=args.sample, seed=args.seed)
        r = head_to_head(bot, opponent, args.matches, args.target, args.seed)
        r["hit_rate"] = bot.hit_rate
        r["hits"] = bot.hits
        r["misses"] = bot.misses
        results[name] = r
        print(report(f"cfr vs {name}", r))

    base = head_to_head(GreedyBot(), RandomBot(), args.matches, args.target, args.seed)
    print(report("greedy vs random (base)", base))

    print()
    for name, r in results.items():
        print(
            f"policy hit rate vs {name:<7} {r['hit_rate']:>6.1%}  "
            f"({r['hits']:,} hits / {r['misses']:,} misses)"
        )
    beat = results["greedy"]
    verdict = "beats" if beat["lo"] > 0.5 else ("loses to" if beat["hi"] < 0.5 else "ties")
    print(f"\nverdict: the policy {verdict} greedy at 95% confidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
