"""Turn-by-turn advisor.

    python advise.py rules                     show the active ruleset + EV baselines
    python advise.py reset                     clear the scorecard
    python advise.py adv "1 3 3 3 4" 2         what to keep (2 rerolls left)
    python advise.py take 3点 "1 2 3 3 3"      record a column
    python advise.py show                      print the scorecard
    python advise.py sim 20000                 Monte-Carlo the optimal policy

The scorecard lives in state.json; the ruleset in config.json.
"""
import json
import sys

import numpy as np

import rules as R

BASE = R.BASE
TABLES = BASE / "tables.npz"
STATE = BASE / "state.json"

RS = R.load()
NAMES = RS.names
N_UP, N_LO, N_CAT = RS.n_up, RS.n_lo, RS.n_cat
UP_MASK, LO_MASK = RS.up_mask, RS.lo_mask
THRESH, BONUS = RS.bonus_threshold, RS.bonus_value
IDXMAP = {n: i for i, n in enumerate(NAMES)}

if not TABLES.exists():
    raise SystemExit("缺少 tables.npz；先跑 `python solve.py`")
D = np.load(TABLES)
if len(D["fingerprint"]) and str(D["fingerprint"][0]) != RS.fingerprint():
    raise SystemExit("tables.npz 是用另一套规则建的，和 config.json 不匹配；"
                     "先跑 `python solve.py` 重建")
SC, SCI, T, IDX, MASK = D["SC"], D["SCI"], D["T"], D["IDX"], D["MASK"]
V_L, W, probs = D["V_L"], D["W"], D["probs"]
SC_UP, SCI_UP, SC_LO = RS.SC_UP, RS.SCI_UP, RS.SC_LO
roll_idx = R.roll_idx
keep_list, keep_idx = R.keep_list, R.keep_idx

bits = R.bits


def counts_of(dice):
    c = [0] * 6
    for d in dice:
        c[d - 1] += 1
    return tuple(c)


def dice_of(kc):
    return [f + 1 for f in range(6) for _ in range(kc[f])]


def roll_index(dice):
    return roll_idx[counts_of(dice)]


def keep_options(i):
    return [IDX[i, j] for j in range(IDX.shape[1]) if MASK[i, j]]


def final_parts(ru, s, rl):
    """value of every still-open column, for each of the 252 final rolls"""
    names, parts = [], []
    for b in bits(ru):
        names.append(NAMES[b])
        parts.append(SC_UP[b]
                     + W[ru ^ (1 << b)][np.minimum(THRESH, s + SCI_UP[b]), rl])
    for b in bits(rl):
        names.append(NAMES[N_UP + b])
        parts.append(SC_LO[b] + W[ru][s, rl ^ (1 << b)])
    return names, np.stack(parts)


def continue_values(ru, s, rl):
    """u[k] / u2[k] = value of holding keep k with 1 / 2 rerolls left"""
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
    return {"mode": "keep", "keep": dice_of(keep_list[best]), "ev": evs[best],
            "alts": [(dice_of(keep_list[k]), v) for k, v in ranked[1:]]}


# --------------------------------------------------------------- scorecard
def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"filled": {}}


def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def masks_from(st):
    fu = fl = 0
    for n, sc in st["filled"].items():
        b = IDXMAP[n]
        if b < N_UP:
            fu |= 1 << b
        else:
            fl |= 1 << (b - N_UP)
    s = sum(sc for n, sc in st["filled"].items() if IDXMAP[n] < N_UP)
    return (~fu) & UP_MASK, min(THRESH, s), (~fl) & LO_MASK, s


def totals(st):
    up = sum(v for n, v in st["filled"].items() if IDXMAP[n] < N_UP)
    lo = sum(v for n, v in st["filled"].items() if IDXMAP[n] >= N_UP)
    return up, lo, up + lo + (BONUS if N_UP and up >= THRESH else 0)


# -------------------------------------------------------------- simulation
def simulate(n_games, seed=7):
    rng = np.random.default_rng(seed)
    out = np.zeros(n_games, dtype=np.int64)
    for g in range(n_games):
        fu = fl = s = 0
        tot = 0
        for _ in range(N_CAT):
            ru, rl = (~fu) & UP_MASK, (~fl) & LO_MASK
            s_c = min(THRESH, s)
            dice = list(rng.integers(1, 7, 5))
            for r in range(2):
                keep = advise(ru, s_c, rl, dice, 2 - r)["keep"]
                dice = sorted(list(keep) + list(rng.integers(1, 7, 5 - len(keep))))
            i = roll_index(dice)
            names, parts = final_parts(ru, s_c, rl)
            b = IDXMAP[names[int(np.argmax(parts[:, i]))]]
            gain = int(SC[b, i])
            tot += gain
            if b < N_UP:
                s += gain
                fu |= 1 << b
            else:
                fl |= 1 << (b - N_UP)
        if N_UP and s >= THRESH:
            tot += BONUS
        out[g] = tot
    return out


# --------------------------------------------------------------------- cli
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"

    if cmd == "rules":
        print(RS.describe())
        print()
        print(f"开局最优期望 (全部 {N_CAT} 栏): {float(W[UP_MASK, 0, LO_MASK]):.3f}")
        print(f"上区单练                     : {float(W[UP_MASK, 0, 0]):.3f}")
        print(f"下区单练                     : {float(V_L[LO_MASK]):.3f}")

    elif cmd == "adv":
        dice = [int(x) for x in sys.argv[2].replace(",", " ").split()]
        left = int(sys.argv[3])
        st = load_state()
        ru, s, rl, sraw = masks_from(st)
        res = advise(ru, s, rl, dice, left)
        if res["mode"] == "score":
            print(f"必须记分 -> {res['cat']} = {res['score']} 分"
                  f"   (此后最优总分 {res['ev']:.1f})")
        else:
            print(f"留: {' '.join(map(str, res['keep']))}   期望总分 {res['ev']:.2f}")
            for k, v in res["alts"]:
                print(f"   次选 留 {' '.join(map(str, k)) or '空'}  "
                      f"({v:.2f}, -{res['ev'] - v:.2f})")

    elif cmd == "take":
        cat, dice = sys.argv[2], [int(x) for x in sys.argv[3].split()]
        if cat not in IDXMAP:
            raise SystemExit(f"没有 '{cat}' 这一栏；本规则集: {', '.join(NAMES)}")
        i = roll_index(dice)
        sc = int(SC[IDXMAP[cat], i])
        st = load_state()
        st["filled"][cat] = sc
        save_state(st)
        ru, s, rl, sraw = masks_from(st)
        note = ""
        if N_UP:
            note = (f" (已过 {THRESH})" if sraw >= THRESH
                    else f" (还差 {THRESH - sraw})")
        print(f"{cat} = {sc} 分   上区累计 {sraw}{note}"
              f"   剩余最优期望 {float(W[ru][min(THRESH, sraw), rl]):.2f}")
        print("已填: " + ", ".join(f"{k}={v}" for k, v in st["filled"].items()))

    elif cmd == "show":
        st = load_state()
        up, lo, tot = totals(st)
        print(f"规则: {RS.title}")
        for i, n in enumerate(NAMES):
            mark = "  " if i < N_UP else "| "
            got = st["filled"].get(n)
            print(f" {mark}{n:<6} {'' if got is None else got}")
        bonus = f"  (+{BONUS} 奖励)" if N_UP and up >= THRESH else ""
        print(f"\n上区小计 {up}{bonus}   下区小计 {lo}")
        print(f"总计 {tot}")

    elif cmd == "reset":
        save_state({"filled": {}})
        print("记分卡已清空")

    elif cmd == "sim":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
        r = simulate(n)
        claim = float(W[UP_MASK, 0, LO_MASK])
        print(f"DP 声称    : {claim:.3f}")
        print(f"模拟 {n} 局 : {r.mean():.3f} +/- {r.std() / np.sqrt(n):.3f}"
              f"   (min {r.min()}, max {r.max()})")

    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
