"""Turn-by-turn advisor + Monte-Carlo validation for the Yahtzee DP."""
import json
import sys
from pathlib import Path
import numpy as np
from itertools import product

BASE = Path(__file__).resolve().parent
D = np.load(BASE / "tables.npz")
SC, SCI, T, IDX, MASK = D["SC"], D["SCI"], D["T"], D["IDX"], D["MASK"]
V_L, W, probs, pips, counts = D["V_L"], D["W"], D["probs"], D["pips"], D["counts"]
META = json.load(open(BASE / "meta.json"))
NAMES = META["names"]
rolls = [tuple(r) for r in META["rolls"]]
roll_idx = {r: i for i, r in enumerate(rolls)}
keep_list = [tuple(k) for k in META["keep_list"]]
keep_idx = {k: i for i, k in enumerate(keep_list)}
THRESH = 63
STATE = BASE / "state.json"

def bits(m):
    return [b for b in range(6) if m >> b & 1]

def counts_of(dice):
    c = [0] * 6
    for d in dice:
        c[d - 1] += 1
    return tuple(c)

def dice_of(kc):
    return [f + 1 for f in range(6) for _ in range(kc[f])]

def final_parts(ru, s, rl):
    """value of each still-open category, given the final roll"""
    names, parts = [], []
    for b in bits(ru):
        names.append(NAMES[b])
        parts.append(SC[b] + W[ru ^ (1 << b)][np.minimum(THRESH, s + SCI[b]), rl])
    for b in bits(rl):
        names.append(NAMES[6 + b])
        parts.append(SC[6 + b] + W[ru][s, rl ^ (1 << b)])
    return names, np.stack(parts)

def roll_index(dice):
    return roll_idx[counts_of(dice)]

def keep_options(i):
    return [IDX[i, j] for j in range(IDX.shape[1]) if MASK[i, j]]

def continue_values(ru, s, rl):
    """u[k]=E[value|hold keep k, one roll left]; u2[k]=... two rolls left"""
    names, parts = final_parts(ru, s, rl)
    ef = parts.max(axis=0)
    u = T @ ef
    e2 = np.where(MASK, u[IDX], -np.inf).max(axis=1)
    u2 = T @ e2
    return names, parts, u, u2

def advise(ru, s, rl, dice, rolls_left):
    i = roll_index(dice)
    names, parts, u, u2 = continue_values(ru, s, rl)
    if rolls_left == 0:
        k = int(np.argmax(parts[:, i]))
        return {"mode": "score", "cat": names[k],
                "score": int(SC[NAMES.index(names[k]), i]),
                "ev": float(parts[k, i])}
    vals = u2 if rolls_left == 2 else u
    opts = keep_options(i)
    evs = {k: float(vals[k]) for k in opts}
    best = max(evs, key=evs.get)
    ranked = sorted(evs.items(), key=lambda kv: -kv[1])[:4]
    return {"mode": "keep", "keep": dice_of(keep_list[best]),
            "ev": evs[best],
            "alts": [(dice_of(keep_list[k]), v) for k, v in ranked[1:]],
            "all": {tuple(dice_of(keep_list[k])): v for k, v in evs.items()}}

# ------------------------------------------------------------------ scorecard
def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"filled": {}}

def save_state(st):
    json.dump(st, open(STATE, "w"), ensure_ascii=False, indent=1)

def masks_from(st):
    fu = fl = 0
    for n, sc in st["filled"].items():
        b = NAMES.index(n)
        if b < 6:
            fu |= 1 << b
        else:
            fl |= 1 << (b - 6)
    s = sum(sc for n, sc in st["filled"].items() if NAMES.index(n) < 6)
    return (~fu) & 63, min(THRESH, s), (~fl) & 63, s

# ---------------------------------------------------------------- simulation
def simulate(n_games, seed=7, policy=True):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_games):
        fu = fl = 0
        s = 0
        tot = 0
        for _turn in range(12):
            ru, rl = (~fu) & 63, (~fl) & 63
            s_c = min(THRESH, s)
            dice = list(rng.integers(1, 7, 5))
            for r in range(3):
                if r == 2:
                    break
                res = advise(ru, s_c, rl, dice, 2 - r)
                keep = res["keep"] if policy else sorted(dice, reverse=True)[:3]
                need = 5 - len(keep)
                dice = sorted(list(keep) + list(rng.integers(1, 7, need)))
            i = roll_index(dice)
            names, parts = final_parts(ru, s_c, rl)
            if policy:
                b = NAMES.index(names[int(np.argmax(parts[:, i]))])
            else:
                open_b = bits(ru) + [6 + b for b in bits(rl)]
                b = open_b[int(np.argmax(SC[open_b, i]))]
            gain = int(SC[b, i])
            tot += gain
            if b < 6:
                s += gain
                fu |= 1 << b
            else:
                fl |= 1 << (b - 6)
        if s >= THRESH:
            tot += 35
        out.append(tot)
    return np.array(out)

# ----------------------------------------------------------------------- cli
def main():
    cmd = sys.argv[1]
    if cmd == "adv":
        dice = [int(x) for x in sys.argv[2].replace(",", " ").split()]
        left = int(sys.argv[3])
        st = load_state()
        ru, s, rl, sraw = masks_from(st)
        res = advise(ru, s, rl, dice, left)
        if res["mode"] == "score":
            print(f"必须记分 -> {res['cat']} = {res['score']} 分"
                  f"   (此后最优总分 {res['ev']:.1f})")
        else:
            print(f"留: {' '.join(map(str, res['keep']))}"
                  f"   期望总分 {res['ev']:.2f}")
            for k, v in res["alts"]:
                print(f"   次选 留 {' '.join(map(str, k)) or '空'}  "
                      f"({v:.2f}, -{res['ev'] - v:.2f})")
    elif cmd == "take":
        cat, dice = sys.argv[2], [int(x) for x in sys.argv[3].split()]
        i = roll_index(dice)
        sc = int(SC[NAMES.index(cat), i])
        st = load_state()
        st["filled"][cat] = sc
        save_state(st)
        ru, s, rl, sraw = masks_from(st)
        print(f"{cat} = {sc} 分   上区累计 {sraw}"
              f"{' (已过 63)' if sraw >= 63 else f' (还差 {63 - sraw})'}"
              f"   剩余最优期望 {W[ru][min(THRESH, sraw), rl]:.2f}")
        print("已填: " + ", ".join(f"{k}={v}" for k, v in st["filled"].items()))
    elif cmd == "show":
        st = load_state()
        print(json.dumps(st, ensure_ascii=False))
    elif cmd == "reset":
        save_state({"filled": {}})
        print("cleared")
    elif cmd == "sim":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
        r = simulate(n)
        print(f"DP 声称    : {float(W[63, 0, 63]):.3f}")
        print(f"模拟 {n} 局 : {r.mean():.3f}  +/- {r.std() / np.sqrt(n):.3f}"
              f"   (min {r.min()}, max {r.max()})")
        g = simulate(n, seed=99, policy=False)
        print(f"贪心对照   : {g.mean():.3f}")

if __name__ == "__main__":
    main()
