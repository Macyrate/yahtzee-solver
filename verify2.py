"""Monte-Carlo a specific sub-position to validate W entries."""
import numpy as np
from advise import (SC, NAMES, advise, final_parts, roll_index, bits, masks_from)

def sim_state(ru0, s0, rl0, n=20000, seed=3):
    rng = np.random.default_rng(seed)
    tot = np.zeros(n, dtype=float)
    for g in range(n):
        ru, s, rl = ru0, s0, rl0
        turns = bin(ru).count("1") + bin(rl).count("1")
        t = 0
        for _ in range(turns):
            dice = list(rng.integers(1, 7, 5))
            for r in range(2):
                res = advise(ru, min(63, s), rl, dice, 2 - r)
                keep = res["keep"]
                dice = sorted(list(keep) + list(rng.integers(1, 7, 5 - len(keep))))
            i = roll_index(dice)
            names, parts = final_parts(ru, min(63, s), rl)
            k = int(np.argmax(parts[:, i]))
            cat = names[k]
            b = NAMES.index(cat)
            t += int(SC[b, i])
            if b < 6:
                ru ^= 1 << b
            else:
                rl ^= 1 << (b - 6)
            s = min(63, s + (int(SC[b, i]) if b < 6 else 0))
        if s >= 63:
            t += 35
        tot[g] = t
    return tot

if __name__ == "__main__":
    from advise import W
    for ru, s, rl, lab in ((32, 56, 20, "6点(差7) + 小顺 + 快艇, 3回合"),
                           (0, 63, 22, "葫芦 + 小顺 + 快艇, 3回合 [奖励已锁]")):
        r = sim_state(ru, s, rl)
        print(f"{lab}")
        print(f"   DP W[{ru},{s},{rl}] = {W[ru][s][rl]:7.2f}    "
              f"模拟 = {r.mean():7.2f} +/- {r.std()/np.sqrt(len(r)):.2f}")
