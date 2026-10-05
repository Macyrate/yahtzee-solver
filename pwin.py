"""Win-probability engine.

Both sides are modelled as expected-score-maximising (the DP policy already
stored in tables.npz).  Because the two players' dice are independent, each
side's remaining-game score distribution can be sampled separately, and the
finals compared.

usage:  pwin.py <turns_left> [n] [opp="1点=3,2点=8"]
        my own scorecard is read from state.json
"""
import json
import sys
import numpy as np
from advise import (SC, T, IDX, MASK, W, NAMES, probs, bits,
                    final_parts, load_state, masks_from)

CUM_P = np.cumsum(probs)
CUM_T = np.cumsum(T, axis=1)
CACHE = {}

def tables(ru, s, rl):
    """optimal action per roll for one state: (names, category, keep[2left], keep[1left])"""
    key = (ru, s, rl)
    hit = CACHE.get(key)
    if hit is not None:
        return hit
    names, parts = final_parts(ru, s, rl)
    cat = parts.argmax(axis=0)
    rows = np.arange(252)
    u = T @ parts.max(axis=0)
    m1 = np.where(MASK, u[IDX], -np.inf)
    keep1 = IDX[rows, m1.argmax(axis=1)]          # column -> keep id
    u2 = T @ m1.max(axis=1)
    m2 = np.where(MASK, u2[IDX], -np.inf)
    keep2 = IDX[rows, m2.argmax(axis=1)]
    CACHE[key] = (names, cat, keep1, keep2)
    return CACHE[key]

def parse(text):
    out = {}
    for part in text.replace(" ", "").split(","):
        if not part or "=" not in part:
            continue
        k, v = part.split("=")
        out[k] = int(v)
    return out

def masks_of(filled):
    fu = fl = 0
    for n, v in filled.items():
        b = NAMES.index(n)
        if b < 6:
            fu |= 1 << b
        else:
            fl |= 1 << (b - 6)
    s = sum(v for n, v in filled.items() if NAMES.index(n) < 6)
    return (~fu) & 63, s, (~fl) & 63

def total_of(filled):
    up = sum(v for n, v in filled.items() if NAMES.index(n) < 6)
    low = sum(v for n, v in filled.items() if NAMES.index(n) >= 6)
    return up + low + (35 if up >= 63 else 0), up

def sim(ru, s, rl, turns, n, rng, bonus_pending):
    out = np.zeros(n, dtype=np.int64)
    for g in range(n):
        ru_, s_, rl_ = ru, s, rl
        t = 0
        for _ in range(turns):
            names, cat, keep1, keep2 = tables(ru_, min(63, s_), rl_)
            i = int(np.searchsorted(CUM_P, rng.random()))
            k = keep2[i]
            i = int(np.searchsorted(CUM_T[k], rng.random()))
            k = keep1[i]
            i = int(np.searchsorted(CUM_T[k], rng.random()))
            b = NAMES.index(names[int(cat[i])])
            gain = int(SC[b, i])
            t += gain
            if b < 6:
                s_ += gain
                ru_ ^= 1 << b
            else:
                rl_ ^= 1 << (b - 6)
        if bonus_pending and s_ >= 63:
            t += 35
        out[g] = t
    return out

def main():
    turns = int(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    opp_txt = sys.argv[3] if len(sys.argv) > 3 else ""
    me = load_state()["filled"]
    opp = parse(opp_txt)

    my_ru, my_s, my_rl = masks_of(me)
    op_ru, op_s, op_rl = masks_of(opp)
    mt, mu = total_of(me)
    ot, ou = total_of(opp)

    # how many categories each side still has to fill, from the masks
    my_turns = bin(my_ru).count("1") + bin(my_rl).count("1")
    op_turns = bin(op_ru).count("1") + bin(op_rl).count("1")
    if my_turns != turns or op_turns != turns:
        print(f"!! 记分卡还剩 {my_turns} 栏(我) / {op_turns} 栏(对方) 未填,"
              f" 与传入的 turns={turns} 不一致", file=sys.stderr)

    # remaining rolls are independent -> sample each side separately
    rng = np.random.default_rng(20240607)
    mine = sim(my_ru, my_s, my_rl, my_turns, n, rng, my_s < 63) if my_turns else np.zeros(n, np.int64)
    theirs = sim(op_ru, op_s, op_rl, op_turns, n, rng, op_s < 63) if op_turns else np.zeros(n, np.int64)
    mine += mt
    theirs += ot

    win = float((mine > theirs).mean())
    tie = float((mine == theirs).mean())
    print(f"我   {mt:>3} 分 + 剩余{my_turns}栏   上区{mu}/63"
          f"{'  (+35)' if mu >= 63 else ''}")
    print(f"对方 {ot:>3} 分 + 剩余{op_turns}栏   上区{ou}/63"
          f"{'  (+35)' if ou >= 63 else ''}")
    print()
    print(f"我的终局预期 {mine.mean():7.1f}   P10 {np.percentile(mine,10):.0f}"
          f"  P90 {np.percentile(mine,90):.0f}")
    print(f"对方终局预期 {theirs.mean():7.1f}   P10 {np.percentile(theirs,10):.0f}"
          f"  P90 {np.percentile(theirs,90):.0f}")
    print()
    print(f"胜 {win*100:6.2f}%    平 {tie*100:5.2f}%    负 {(1-win-tie)*100:6.2f}%")

if __name__ == "__main__":
    main()
