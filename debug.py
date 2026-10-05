"""Bisect the DP-vs-simulation gap by sub-game."""
import numpy as np
from advise import (SC, SCI, T, IDX, MASK, V_L, W, probs, NAMES,
                    roll_index, keep_options, keep_list, dice_of)

THRESH, BONUS = 63, 35

def bits(m):
    return [b for b in range(6) if m >> b & 1]

def keep_decision(vals, i):
    opts = keep_options(i)
    best = max(opts, key=lambda k: vals[k])
    return dice_of(keep_list[best])

def sim_upper(n, seed=1):
    rng = np.random.default_rng(seed)
    tot = np.zeros(n, dtype=int)
    up = np.zeros(n, dtype=int)
    for g in range(n):
        fu, s, t = 0, 0, 0
        for _ in range(6):
            ru = (~fu) & 63
            sc_ = min(THRESH, s)
            dice = list(rng.integers(1, 7, 5))
            for r in range(2):
                parts = np.stack([SC[b] + W[ru ^ (1 << b)][np.minimum(THRESH, sc_ + SCI[b]), 0]
                                  for b in bits(ru)])
                ef = parts.max(axis=0)
                u = T @ ef
                e2 = np.where(MASK, u[IDX], -np.inf).max(axis=1)
                u2 = T @ e2
                vals = u2 if r == 0 else u
                keep = keep_decision(vals, roll_index(dice))
                dice = sorted(list(keep) + list(rng.integers(1, 7, 5 - len(keep))))
            i = roll_index(dice)
            bs = bits(ru)
            gains = [SC[b, i] + W[ru ^ (1 << b)][min(THRESH, sc_ + int(SCI[b, i])), 0]
                     for b in bs]
            b = bs[int(np.argmax(gains))]
            gain = int(SC[b, i])
            t += gain
            s += gain
            fu |= 1 << b
        if s >= THRESH:
            t += BONUS
        tot[g], up[g] = t, s
    return tot, up

def sim_lower(n, seed=2):
    rng = np.random.default_rng(seed)
    tot = np.zeros(n, dtype=int)
    for g in range(n):
        fl, t = 0, 0
        for _ in range(6):
            rl = (~fl) & 63
            dice = list(rng.integers(1, 7, 5))
            for r in range(2):
                parts = np.stack([SC[6 + b] + V_L[rl ^ (1 << b)] for b in bits(rl)])
                ef = parts.max(axis=0)
                u = T @ ef
                e2 = np.where(MASK, u[IDX], -np.inf).max(axis=1)
                u2 = T @ e2
                vals = u2 if r == 0 else u
                keep = keep_decision(vals, roll_index(dice))
                dice = sorted(list(keep) + list(rng.integers(1, 7, 5 - len(keep))))
            i = roll_index(dice)
            bs = bits(rl)
            gains = [SC[6 + b, i] + V_L[rl ^ (1 << b)] for b in bs]
            b = bs[int(np.argmax(gains))]
            gain = int(SC[6 + b, i])
            t += gain
            fl |= 1 << b
        tot[g] = t
    return tot

if __name__ == "__main__":
    n = 4000
    t, up = sim_upper(n)
    print(f"上区单练  DP {W[63,0,0]:.3f}   模拟 {t.mean():.3f} +/- {t.std()/np.sqrt(n):.3f}"
          f"   上区原始均值 {up.mean():.2f}  满63比例 {(up>=63).mean():.3f}")
    t2 = sim_lower(n)
    print(f"下区单练  DP {V_L[63]:.3f}   模拟 {t2.mean():.3f} +/- {t2.std()/np.sqrt(n):.3f}")
