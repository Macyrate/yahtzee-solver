"""Independent Monte-Carlo checks of whatever DP tables are on disk.

The simulation uses real random dice and its own scoring path, so it catches
policy-independent mistakes (wrong transition probabilities, bad mask maths,
mishandled bonus) that a self-consistent DP would hide.

    python verify.py                  full game / upper only / lower only
    python verify.py 32 56 20         one arbitrary position (ru, s, rl)
    python verify.py 32 56 20 20000   ... with more samples
"""
import sys

import numpy as np

import rules as R
from advise import (SC, W, V_L, NAMES, advise, final_parts, roll_index, IDXMAP,
                    N_UP, THRESH, BONUS, UP_MASK, LO_MASK)


def sim_state(ru0, s0, rl0, n=8000, seed=3):
    """sample the rest of the game from one position, using the DP policy"""
    rng = np.random.default_rng(seed)
    tot = np.zeros(n, dtype=float)
    turns = bin(ru0).count("1") + bin(rl0).count("1")
    for g in range(n):
        ru, s, rl = ru0, s0, rl0
        t = 0
        for _ in range(turns):
            dice = list(rng.integers(1, 7, 5))
            for r in range(2):
                keep = advise(ru, min(THRESH, s), rl, dice, 2 - r)["keep"]
                dice = sorted(list(keep) + list(rng.integers(1, 7, 5 - len(keep))))
            i = roll_index(dice)
            names, parts = final_parts(ru, min(THRESH, s), rl)
            b = IDXMAP[names[int(np.argmax(parts[:, i]))]]
            gain = int(SC[b, i])
            t += gain
            if b < N_UP:
                s += gain
                ru ^= 1 << b
            else:
                rl ^= 1 << (b - N_UP)
        if N_UP and s >= THRESH:
            t += BONUS
        tot[g] = t
    return tot


def check(label, ru, s, rl, n):
    claim = float(W[ru][s][rl])
    r = sim_state(ru, s, rl, n=n)
    se = r.std() / np.sqrt(len(r))
    ok = abs(r.mean() - claim) < 3 * se + 1e-9
    print(f"  {'OK ' if ok else 'BAD'} {label:<34} DP {claim:8.2f}   "
          f"模拟 {r.mean():8.2f} +/- {se:.2f}")
    return ok


def main():
    if len(sys.argv) > 3:
        ru, s, rl = (int(x) for x in sys.argv[1:4])
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 8000
        print(f"{R.load().title}   position ru={ru} s={s} rl={rl}")
        ok = check("specified position", ru, s, rl, n)
        raise SystemExit(0 if ok else 1)

    rs = R.load()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"{rs.title}  ({rs.n_cat} 栏, {n} 局/项)\n")
    ok = [check("全局", UP_MASK, 0, LO_MASK, n)]
    if N_UP:
        ok.append(check("上区单练", UP_MASK, 0, 0, n))
    if rs.n_lo:
        r = sim_state(0, 0, LO_MASK, n=n)
        claim = float(V_L[LO_MASK])
        se = r.std() / np.sqrt(n)
        good = abs(r.mean() - claim) < 3 * se + 1e-9
        ok.append(good)
        print(f"  {'OK ' if good else 'BAD'} {'下区单练':<34} DP {claim:8.2f}   "
              f"模拟 {r.mean():8.2f} +/- {se:.2f}")
    print()
    print("全部通过" if all(ok) else "!! 有不一致，检查 solve.py")
    raise SystemExit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
