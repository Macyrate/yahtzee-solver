"""Win-probability engine.

Both sides are modelled as expected-score-maximising (the policy stored in
tables.npz).  The two players' dice are independent, so each side's
remaining-game score distribution is sampled separately and the finals compared.

usage:  python pwin.py <turns_left> [n] [opp="1点=3,2点=8,机会=22"]
        my own scorecard is read from state.json
        opp="" (or omitted) means the opponent has an empty scorecard
"""
import sys

import numpy as np

from advise import (SC, T, IDX, MASK, W, NAMES, probs, IDXMAP, N_UP, N_CAT,
                    THRESH, BONUS, UP_MASK, LO_MASK, RS,
                    final_parts, load_state, masks_from)

CUM_P = np.cumsum(probs)
CUM_T = np.cumsum(T, axis=1)
CACHE = {}


def tables(ru, s, rl):
    """optimal action per roll: (open column names, best column, keep², keep¹)"""
    key = (ru, s, rl)
    hit = CACHE.get(key)
    if hit is not None:
        return hit
    names, parts = final_parts(ru, s, rl)
    cat = parts.argmax(axis=0)
    rows = np.arange(len(probs))
    u = T @ parts.max(axis=0)
    m1 = np.where(MASK, u[IDX], -np.inf)
    keep1 = IDX[rows, m1.argmax(axis=1)]
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
        if k not in IDXMAP:
            raise SystemExit(f"对方记分卡里有未知栏位 '{k}'；本规则集: {', '.join(NAMES)}")
        out[k] = int(v)
    return out


def masks_of(filled):
    fu = fl = 0
    for n, v in filled.items():
        b = IDXMAP[n]
        if b < N_UP:
            fu |= 1 << b
        else:
            fl |= 1 << (b - N_UP)
    s = sum(v for n, v in filled.items() if IDXMAP[n] < N_UP)
    return (~fu) & UP_MASK, s, (~fl) & LO_MASK


def total_of(filled):
    up = sum(v for n, v in filled.items() if IDXMAP[n] < N_UP)
    lo = sum(v for n, v in filled.items() if IDXMAP[n] >= N_UP)
    return up + lo + (BONUS if N_UP and up >= THRESH else 0), up


def sim(ru, s, rl, turns, n, rng, bonus_pending):
    out = np.zeros(n, dtype=np.int64)
    for g in range(n):
        ru_, s_, rl_ = ru, s, rl
        t = 0
        for _ in range(turns):
            names, cat, keep1, keep2 = tables(ru_, min(THRESH, s_), rl_)
            i = int(np.searchsorted(CUM_P, rng.random()))
            i = int(np.searchsorted(CUM_T[keep2[i]], rng.random()))
            i = int(np.searchsorted(CUM_T[keep1[i]], rng.random()))
            b = IDXMAP[names[int(cat[i])]]
            gain = int(SC[b, i])
            t += gain
            if b < N_UP:
                s_ += gain
                ru_ ^= 1 << b
            else:
                rl_ ^= 1 << (b - N_UP)
        if bonus_pending and s_ >= THRESH:
            t += BONUS
        out[g] = t
    return out


def main():
    turns = int(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    opp = parse(sys.argv[3]) if len(sys.argv) > 3 else {}

    me = load_state()["filled"]
    my_ru, my_s, my_rl = masks_of(me)
    op_ru, op_s, op_rl = masks_of(opp)
    mt, mu = total_of(me)
    ot, ou = total_of(opp)

    my_turns = bin(my_ru).count("1") + bin(my_rl).count("1")
    op_turns = bin(op_ru).count("1") + bin(op_rl).count("1")
    if my_turns != turns or op_turns != turns:
        print(f"!! 我剩 {my_turns} 栏 / 对方剩 {op_turns} 栏，与传入的 turns={turns} "
              f"不一致（按各自实际剩余栏数计算）", file=sys.stderr)

    rng = np.random.default_rng(20240607)
    mine = sim(my_ru, my_s, my_rl, my_turns, n, rng, my_s < THRESH) + mt
    theirs = sim(op_ru, op_s, op_rl, op_turns, n, rng, op_s < THRESH) + ot

    win = float((mine > theirs).mean())
    tie = float((mine == theirs).mean())
    print(f"规则: {RS.title}")
    print(f"我   {mt:>3} 分 + 剩余{my_turns}栏   上区{mu}/{THRESH}"
          + (f"  (+{BONUS})" if N_UP and mu >= THRESH else ""))
    print(f"对方 {ot:>3} 分 + 剩余{op_turns}栏   上区{ou}/{THRESH}"
          + (f"  (+{BONUS})" if N_UP and ou >= THRESH else ""))
    print()
    print(f"我的终局预期 {mine.mean():7.1f}   P10 {np.percentile(mine, 10):.0f}"
          f"  P90 {np.percentile(mine, 90):.0f}")
    print(f"对方终局预期 {theirs.mean():7.1f}   P10 {np.percentile(theirs, 10):.0f}"
          f"  P90 {np.percentile(theirs, 90):.0f}")
    print()
    print(f"胜 {win * 100:6.2f}%    平 {tie * 100:5.2f}%    负 {(1 - win - tie) * 100:6.2f}%")


if __name__ == "__main__":
    main()
