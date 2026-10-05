"""Exact expected-value solver for the Clubhouse Games 51 Yahtzee variant.

Scorecard (12 categories, confirmed by the user):
  upper:  Aces..Sixes      = (face) * count
  lower:  four-of-a-kind   = sum of all 5 dice if max count >= 4
          full house       = sum of all 5 dice if counts are (3,2) or (5,0)
          small straight   = 15 if any 4 consecutive faces present
          large straight   = 30 if 1-5 or 2-6 present
          yacht            = 50 if all 5 equal
          chance           = sum of all 5 dice
  bonus: +35 if the six upper boxes total >= 63
"""
import json
from pathlib import Path
import numpy as np

BASE = Path(__file__).resolve().parent
from itertools import product
from math import factorial

N_CAT = 12
CAT_NAMES = ["1点", "2点", "3点", "4点", "5点", "6点",
             "四条", "葫芦", "小顺", "大顺", "快艇", "机会"]
IDXMAP = {n: i for i, n in enumerate(CAT_NAMES)}
BONUS = 35
THRESH = 63

# ---------------------------------------------------------------- dice space
rolls = [c for c in product(range(6), repeat=6) if sum(c) == 5]
roll_idx = {c: i for i, c in enumerate(rolls)}
N_ROLL = len(rolls)                                   # 252
counts = np.array(rolls, dtype=np.int64)
pips = counts @ np.arange(1, 7)

def multiset_pmf(size):
    out = {}
    for c in product(range(size + 1), repeat=6):
        if sum(c) == size:
            p = factorial(size)
            for x in c:
                p //= factorial(x)
            out[c] = p / 6 ** size
    return out

PMF = {m: multiset_pmf(m) for m in range(6)}
probs = np.array([PMF[5][c] for c in rolls], dtype=np.float64)

face_present = counts > 0
def run_mask(faces):
    return np.all(np.stack([face_present[:, f - 1] for f in faces]), axis=0)

SMALL = run_mask([1, 2, 3, 4]) | run_mask([2, 3, 4, 5]) | run_mask([3, 4, 5, 6])
LARGE = run_mask([1, 2, 3, 4, 5]) | run_mask([2, 3, 4, 5, 6])
MAXC = counts.max(axis=1)

SC = np.zeros((N_CAT, N_ROLL), dtype=np.float64)
for f in range(6):
    SC[f] = (f + 1) * counts[:, f]
SC[6] = np.where(MAXC >= 4, pips, 0)                       # 四条
nzpat = np.array([sorted(x for x in c if x > 0) for c in rolls], dtype=object)
SC[7] = np.where([p == [2, 3] or max(c) == 5 for p, c in zip(nzpat, rolls)],
                 pips, 0)                                  # 葫芦
SC[8] = np.where(SMALL, 15, 0)                             # 小顺
SC[9] = np.where(LARGE, 30, 0)                             # 大顺
SC[10] = np.where(MAXC == 5, 50, 0)                        # 快艇
SC[11] = pips                                              # 机会
SCI = SC.astype(np.int64)

# ------------------------------------------------------------- keep / reroll
keep_list = [c for size in range(6) for c in product(range(size + 1), repeat=6)
             if sum(c) == size]
keep_idx = {c: i for i, c in enumerate(keep_list)}
N_KEEP = len(keep_list)                                # 462

T = np.zeros((N_KEEP, N_ROLL), dtype=np.float64)
for k, kc in enumerate(keep_list):
    m = 5 - sum(kc)
    for dc, p in PMF[m].items():
        T[k, roll_idx[tuple(kc[f] + dc[f] for f in range(6))]] = p

MAX_SUB = 32
IDX = np.zeros((N_ROLL, MAX_SUB), dtype=np.int64)
MASK = np.zeros((N_ROLL, MAX_SUB), dtype=bool)
for i, c in enumerate(rolls):
    subs = [keep_idx[kc] for kc in keep_list if all(kc[f] <= c[f] for f in range(6))]
    for j, s in enumerate(subs):
        IDX[i, j] = s
        MASK[i, j] = True

def turn_value(next_vals):
    ef = next_vals.max(axis=0)                                   # (252,)
    u = T @ ef                                                   # (462,)
    e2 = np.where(MASK, u[IDX], -np.inf).max(axis=1)             # (252,)
    u2 = T @ e2
    e1 = np.where(MASK, u2[IDX], -np.inf).max(axis=1)            # (252,)
    return float(probs @ e1)

def bits(mask):
    return [b for b in range(6) if mask >> b & 1]

def reachable_sums(mask):
    out = {0}
    for v in [f + 1 for f in bits(mask)]:
        out = {min(THRESH, s + v * k) for s in out for k in range(6)}
    return np.array(sorted(out), dtype=np.int64)

RSUM = {m: reachable_sums(m) for m in range(64)}

# --------------------------------------------------- lower-only table (V_L)
V_L = np.zeros(64, dtype=np.float64)
for layer in range(1, 7):
    for rl in range(64):
        if bin(rl).count("1") != layer:
            continue
        V_L[rl] = turn_value(np.stack([SC[6 + b] + V_L[rl ^ (1 << b)]
                                       for b in bits(rl)]))

# ------------------------------------------------ joint table with the bonus
W = np.full((64, 64, 64), np.nan, dtype=np.float64)
for rl in range(64):
    for s in range(64):
        W[0, s, rl] = V_L[rl] + (BONUS if s >= THRESH else 0.0)

for total in range(1, 13):
    for ru in range(1, 64):
        pu = bin(ru).count("1")
        pl = total - pu
        if pl < 0 or pl > 6:
            continue
        s_list = RSUM[(~ru) & 63]
        for rl in range(64):
            if bin(rl).count("1") != pl:
                continue
            parts = []
            for b in bits(ru):
                ns = np.minimum(THRESH, s_list[:, None] + SCI[b][None, :])
                parts.append(SC[b][None, :] + W[ru ^ (1 << b)][ns, rl])
            for b in bits(rl):
                parts.append(SC[6 + b][None, :]
                             + W[ru][s_list, rl ^ (1 << b)][:, None])
            ef = np.maximum.reduce(parts)
            u = ef @ T.T
            e2 = np.where(MASK, u[:, IDX], -np.inf).max(axis=2)
            u2 = e2 @ T.T
            e1 = np.where(MASK, u2[:, IDX], -np.inf).max(axis=2)
            W[ru][s_list, rl] = e1 @ probs

np.savez(BASE / "tables.npz", SC=SC, SCI=SCI, T=T, IDX=IDX,
         MASK=MASK, V_L=V_L, W=W, probs=probs, pips=pips, counts=counts)
with open(BASE / "meta.json", "w") as fh:
    json.dump({"rolls": [list(r) for r in rolls],
               "keep_list": [list(k) for k in keep_list],
               "names": CAT_NAMES, "pips": pips.tolist()}, fh)

print("open 12 categories (lead-off EV):", round(float(W[63, 0, 63]), 3))
print("lower section alone            :", round(float(V_L[63]), 3))
print("upper alone, bonus at risk      :", round(float(W[63, 0, 0]), 3))
print("saved ->", BASE / "tables.npz")
