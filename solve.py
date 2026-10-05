"""Build the exact DP tables for the ruleset in config.json.

Solves the whole game by backward induction over
    (remaining upper mask, current upper subtotal, remaining lower mask)
for every one of the 252 distinct five-dice multisets.  Roughly 5 s for the
12-column Clubhouse ruleset, ~10 s for standard 13-column Yahtzee.

    python solve.py            # build from config.json
    python solve.py --check    # just report what would be built
"""
import sys
import time
from pathlib import Path

import numpy as np

import rules as R

BASE = Path(__file__).resolve().parent
TABLES = BASE / "tables.npz"
THRESH_CAP = 63


def build(rs, verbose=True):
    n_up, n_lo = rs.n_up, rs.n_lo
    UP_MASK = rs.up_mask
    SC_UP, SCI_UP, SC_LO = rs.SC_UP, rs.SCI_UP, rs.SC_LO
    THRESH, BONUS = rs.bonus_threshold, rs.bonus_value

    # ---- reroll transition tensor: T[keep, resulting roll] ----
    T = np.zeros((R.N_KEEP, R.N_ROLL), dtype=np.float64)
    for k, kc in enumerate(R.keep_list):
        m = 5 - sum(kc)
        for dc, p in R.PMF[m].items():
            T[k, R.roll_idx[tuple(kc[f] + dc[f] for f in range(6))]] = p

    # ---- which keeps are subsets of which roll ----
    MAX_SUB = 32
    IDX = np.zeros((R.N_ROLL, MAX_SUB), dtype=np.int64)
    MASK = np.zeros((R.N_ROLL, MAX_SUB), dtype=bool)
    for i, c in enumerate(R.rolls):
        subs = [R.keep_idx[kc] for kc in R.keep_list
                if all(kc[f] <= c[f] for f in range(6))]
        for j, s in enumerate(subs):
            IDX[i, j] = s
            MASK[i, j] = True

    def turn_value(next_vals):
        ef = next_vals.max(axis=0)
        u = T @ ef
        e2 = np.where(MASK, u[IDX], -np.inf).max(axis=1)
        u2 = T @ e2
        e1 = np.where(MASK, u2[IDX], -np.inf).max(axis=1)
        return float(R.probs @ e1)

    # ---- lower-only value table ----
    V_L = np.zeros(1 << n_lo, dtype=np.float64)
    for layer in range(1, n_lo + 1):
        for rl in range(1 << n_lo):
            if bin(rl).count("1") != layer:
                continue
            V_L[rl] = turn_value(np.stack([SC_LO[b] + V_L[rl ^ (1 << b)]
                                           for b in R.bits(rl)]))

    # ---- reachable upper subtotals, per filled-upper mask ----
    up_faces = [int(c["face"]) for c in rs.cats[:n_up]]

    def reachable(mask):
        out = {0}
        for v in [up_faces[b] for b in R.bits(mask)]:
            out = {min(THRESH_CAP, s + v * k) for s in out for k in range(6)}
        return np.array(sorted(out), dtype=np.int64)

    RSUM = {m: reachable(m) for m in range(1 << n_up)}

    # ---- joint table ----
    s_dim = 64 if n_up else 1
    W = np.full((1 << n_up, s_dim, 1 << n_lo), np.nan, dtype=np.float64)
    for rl in range(1 << n_lo):
        for s in range(s_dim):
            W[0, s, rl] = V_L[rl] + (BONUS if n_up and s >= THRESH else 0.0)

    t0 = time.time()
    done = 0
    for total in range(1, rs.n_cat + 1):
        for ru in range(1, 1 << n_up):
            pu = bin(ru).count("1")
            pl = total - pu
            if pl < 0 or pl > n_lo:
                continue
            s_list = RSUM[(~ru) & UP_MASK]
            for rl in range(1 << n_lo):
                if bin(rl).count("1") != pl:
                    continue
                parts = []
                for b in R.bits(ru):
                    ns = np.minimum(THRESH, s_list[:, None] + SCI_UP[b][None, :])
                    parts.append(SC_UP[b][None, :] + W[ru ^ (1 << b)][ns, rl])
                for b in R.bits(rl):
                    parts.append(SC_LO[b][None, :]
                                 + W[ru][s_list, rl ^ (1 << b)][:, None])
                ef = np.maximum.reduce(parts)
                u = ef @ T.T
                e2 = np.where(MASK, u[:, IDX], -np.inf).max(axis=2)
                u2 = e2 @ T.T
                e1 = np.where(MASK, u2[:, IDX], -np.inf).max(axis=2)
                W[ru][s_list, rl] = e1 @ R.probs
                done += 1
        if verbose:
            print(f"  layer {total:2d}/{rs.n_cat}  ({done} states, "
                  f"{time.time() - t0:.1f}s)", flush=True)

    return dict(SC=rs.SC, SCI=rs.SCI, T=T, IDX=IDX, MASK=MASK,
                V_L=V_L, W=W, probs=R.probs, pips=R.pips, counts=R.counts,
                n_up=np.array([n_up]), n_lo=np.array([n_lo]),
                n_cat=np.array([rs.n_cat]),
                fingerprint=np.array([rs.fingerprint()]))


def main():
    rs = R.load()
    print(rs.describe())
    print()
    if "--check" in sys.argv:
        return
    out = build(rs)
    np.savez(TABLES, **out)
    full = out["W"][rs.up_mask, 0, rs.lo_mask]
    print()
    print(f"开局最优期望 (全部 {rs.n_cat} 栏): {full:.3f}")
    print(f"上区单练                        : {out['W'][rs.up_mask, 0, 0]:.3f}")
    print(f"下区单练                        : {out['V_L'][rs.lo_mask]:.3f}")
    print(f"saved -> {TABLES}")


if __name__ == "__main__":
    main()
