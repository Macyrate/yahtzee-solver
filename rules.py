"""Ruleset handling.

A ruleset is a JSON file listing the scorecard columns.  Every column names a
*rule* (how it scores) plus that rule's parameters.  `build_scores()` turns a
ruleset into the (n_categories, 252) score matrix the solver consumes.

Columns come in two kinds:

  kind="upper"  the numbered boxes (Aces..Sixes).  Their subtotal feeds the
                bonus, and the solver tracks it explicitly.
  kind="lower"  everything else.

Column order matters: uppers must come first, and the index of a column is the
bit position used in the solver's masks.

Available rules
---------------
  upper        score = face * count                 params: {}                (uses "face")
  n_kind       n or more of a kind                  params: {"n": 3, "score": "sum" | <int>}
  full_house   3+2 (or all five equal)              params: {"score": "sum" | <int>}
  straight     `length` consecutive faces present   params: {"length": 4, "score": <int>}
  all_same     all five dice equal                  params: {"score": <int>}
  sum          total of all five dice               params: {}
"""
import json
from itertools import product
from math import factorial
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"
PRESETS = BASE / "presets"

# --------------------------------------------------------------- dice space
rolls = [c for c in product(range(6), repeat=6) if sum(c) == 5]      # 252 multisets
roll_idx = {c: i for i, c in enumerate(rolls)}
N_ROLL = len(rolls)
counts = np.array(rolls, dtype=np.int64)
pips = counts @ np.arange(1, 7)
face_present = counts > 0
MAXC = counts.max(axis=1)
NZDISTINCT = np.array([len({f for f in range(6) if c[f]}) for c in rolls])

keep_list = [c for size in range(6) for c in product(range(size + 1), repeat=6)
             if sum(c) == size]
keep_idx = {c: i for i, c in enumerate(keep_list)}
N_KEEP = len(keep_list)                                              # 462


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


# ----------------------------------------------------------- rule evaluators
def _consecutive(length):
    """rolls that contain `length` consecutive distinct faces"""
    m = np.zeros(N_ROLL, dtype=bool)
    for start in range(1, 7 - length + 1):
        faces = list(range(start, start + length))
        m |= np.all(np.stack([face_present[:, f - 1] for f in faces]), axis=0)
    return m


_CONSEC = {n: _consecutive(n) for n in range(1, 7)}
_FULL_HOUSE = np.array([sorted(x for x in c if x > 0) in ([2, 3], [5]) for c in rolls])


def _payoff(spec, mask):
    """`spec` is "sum" or an int; `mask` selects which rolls pay off."""
    if spec == "sum":
        return np.where(mask, pips, 0).astype(np.float64)
    return np.where(mask, float(spec), 0.0)


def build_column(cat):
    rule, p = cat["rule"], cat.get("params", {})
    if rule == "upper":
        f = int(cat["face"]) - 1
        return ((f + 1) * counts[:, f]).astype(np.float64)
    if rule == "n_kind":
        return _payoff(p.get("score", "sum"), MAXC >= int(p.get("n", 3)))
    if rule == "full_house":
        return _payoff(p.get("score", "sum"), _FULL_HOUSE)
    if rule == "straight":
        return _payoff(p.get("score", 0), _CONSEC[int(p.get("length", 4))])
    if rule == "all_same":
        return _payoff(p.get("score", 50), MAXC == 5)
    if rule == "sum":
        return pips.astype(np.float64)
    raise ValueError(f"unknown rule: {rule!r}")


# ------------------------------------------------------------------ ruleset
class Rules:
    def __init__(self, cfg):
        self.cfg = cfg
        self.title = cfg.get("title", cfg.get("preset", "custom"))
        self.preset = cfg.get("preset", "custom")
        self.cats = cfg["categories"]
        self.names = [c["name"] for c in self.cats]
        self.en = [c.get("en", c["name"]) for c in self.cats]
        self.n_cat = len(self.cats)
        self.n_up = sum(1 for c in self.cats if c.get("kind") == "upper")
        self.n_lo = self.n_cat - self.n_up
        if any(c.get("kind") == "upper" for c in self.cats[self.n_up:]):
            raise ValueError("upper columns must come before lower columns")
        bonus = cfg.get("bonus") or {}
        self.bonus_value = int(bonus.get("value", 0)) if self.n_up else 0
        self.bonus_threshold = int(bonus.get("threshold", 63))
        self.up_mask = (1 << self.n_up) - 1
        self.lo_mask = (1 << self.n_lo) - 1
        self.SC = np.stack([build_column(c) for c in self.cats])
        self.SCI = self.SC.astype(np.int64)
        self.SC_UP, self.SC_LO = self.SC[:self.n_up], self.SC[self.n_up:]
        self.SCI_UP = self.SCI[:self.n_up]
        self.SC_LO = self.SC[self.n_up:]
        self.is_upper = [i < self.n_up for i in range(self.n_cat)]
        self.max_total = (float(self.SC.sum(axis=0).max()) + self.bonus_value)

    # a stable fingerprint so stale tables are detected
    def fingerprint(self):
        import hashlib
        blob = json.dumps(self.cfg, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def describe(self):
        lines = [f"{self.title}  ({self.n_cat} 栏 / {self.n_up} 上区 + {self.n_lo} 下区)"]
        for i, c in enumerate(self.cats):
            p = c.get("params", {})
            bits = ", ".join(f"{k}={v}" for k, v in p.items())
            lines.append(f"  [{i:2d}] {c['name']:<6} {c.get('en', ''):<16} "
                         f"{c['rule']}({bits})")
        lines.append(f"  奖励: 上区 >= {self.bonus_threshold} 加 {self.bonus_value}")
        return "\n".join(lines)


def load(path=CONFIG):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"找不到配置文件 {path}；先跑 `python use.py clubhouse`")
    return Rules(json.loads(path.read_text(encoding="utf-8")))


def load_preset(name):
    return Rules(json.loads((PRESETS / f"{name}.json").read_text(encoding="utf-8")))


def bits(mask):
    return [b for b in range(mask.bit_length()) if mask >> b & 1]


def quiet_blas():
    """Silence bogus floating-point warnings raised by BLAS matmul.

    macOS Accelerate sets FP status flags on perfectly finite input, and
    numpy < 2.5 surfaces them as "divide by zero / overflow / invalid value
    encountered in matmul".  Reproducible with plain random arrays; results
    are unaffected (checked against a row-wise dot product).
    """
    return np.errstate(all="ignore")
