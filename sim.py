# sim.py
import random
from collections import Counter

import cards
import events
from environment import Environment, VERDICT_HOLD
from default_ais import BFSAI

POOL = [
    [cards.Stone, 10],
    [cards.Wall, 6],
    [cards.Edge, 3],
]

def run(seed, size=15, rings=(1, 3), max_steps=500, verbose=False):
    env = Environment(size, rings, [BFSAI()], pool=POOL, rng=random.Random(seed))
    env.drain()
    for step in range(max_steps):
        env.aistep()
        evs = env.drain()
        if verbose:
            ai = env.ais[0]
            print(step, (ai.x, ai.y), [type(e).__name__ for e in evs])
        if env.verdict != VERDICT_HOLD:
            return env.verdict, step, env
    return 0, max_steps, env

if __name__ == "__main__":
    run(1, verbose=True)

    results = Counter()
    for seed in range(200):
        v, steps, _ = run(seed)
        results[v] += 1
    print(results)