# yahtzee-solver

An **exact optimal-play solver** for Yahtzee. No heuristics, no lookup tables —
it runs backward induction over the entire game, so it can tell you the
expected-value-optimal move at any point, and your **win probability** from any
pair of scorecards.

> [中文说明](README.md)

Two rulesets ship with it:

| Preset | Rules | Columns | Optimal EV |
|---|---|---|---|
| **`clubhouse`** | *Clubhouse Games: 51 Worldwide Games* | 12 | **191.77** |
| **`standard`** | Standard Yahtzee (Hasbro) | 13 | **245.91** |

The active ruleset lives in `config.json` and is meant to be edited. Adding your
own variant is a matter of writing a few JSON lines.

---

## Quick start

```bash
git clone https://github.com/Macyrate/yahtzee-solver
cd yahtzee-solver
python3 -m venv .venv && ./.venv/bin/pip install numpy
./.venv/bin/python advise.py adv "1 3 3 3 4" 2
```

`tables.npz` is committed, so a fresh clone works immediately — no build step.

> **Requirements:** Python 3.9+ and numpy (`requirements.txt`); nothing else.
> The version only affects build speed — Python 3.12 + numpy 2.5 takes ~4 s,
> Python 3.9 + numpy 2.0 takes ~8 s. Note that numpy < 2.5 on macOS emits
> bogus warnings from BLAS (`divide by zero encountered in matmul` and
> friends). They reproduce on plain random arrays and do not affect results;
> the code silences them at the matmul sites.

---

## Commands

Assumes you ran `source .venv/bin/activate`.

### Inspect the ruleset / start a new game

```bash
python advise.py rules          # print the scorecard rules + three EV baselines
python advise.py reset          # clear the scorecard
```

### Ask what to keep, after each roll

```bash
python advise.py adv "1 3 3 3 4" 2
```

The second argument is the number of **rerolls remaining**: `2` right after the
first roll, `1` after the second, `0` after the third (when you have to score).

You get the optimal keep, the resulting expected final score, and how much each
runner-up would cost you.

### Record a column

```bash
python advise.py take 3点 "1 2 3 3 3"
```

The score is computed from the dice, and the upper-section progress plus the new
optimal expectation are printed.

### Win probability

```bash
python pwin.py 8 6000 "1点=2,2点=8,3点=12,机会=22"
```

| Argument | Meaning |
|---|---|
| 1 | Your turns remaining (= columns you still have open) |
| 2 | Monte-Carlo samples (default 3000; 6000 takes ~3 s, ±0.6%) |
| 3 | **The opponent's full scorecard**, as `name=score,…`; use `""` if empty |

Your own scorecard is read from `state.json`.

> **On the numbers:** if you have just finished your turn and the opponent has
> not rolled yet, the engine is comparing "you have N turns, they have N+1" and
> the result is **pessimistic**. Once they roll too, both sides are on the same
> footing.

### Switch rulesets

```bash
python use.py                   # list presets, mark the active one
python use.py standard          # switch to standard Yahtzee and rebuild (~10 s)
python use.py clubhouse         # switch back (~5 s)
```

### Self-checks

```bash
python verify.py                # independent Monte-Carlo check of the baselines
python verify.py 32 56 20       # check one arbitrary position (ru, s, rl)
python advise.py sim 20000      # whole-game simulation against the DP value
```

---

## Files

| File | Role |
|---|---|
| `rules.py` | ruleset → scoring matrix, dice space, mask helpers |
| `solve.py` | builds the tables (the only slow step) |
| `advise.py` | move advisor + scorecard + whole-game simulation |
| `pwin.py` | win-probability engine |
| `use.py` | preset switcher |
| `verify.py` | independent Monte-Carlo self-check |
| `config.json` | **the active ruleset** — edit this |
| `presets/` | ready-made rulesets (clubhouse / standard) |
| `state.json` | the scorecard for the game in progress |
| `results/` | game logs; `game-1.json` is a 197:188 win |

---

## Custom rulesets

`config.json` *is* the active ruleset. Each column names a **rule** plus that
rule's parameters:

```json
{
  "preset": "my-variant",
  "title": "My variant",
  "bonus": { "threshold": 63, "value": 35 },
  "categories": [
    { "name": "Aces", "kind": "upper", "rule": "upper", "face": 1 },
    { "name": "Four of a Kind", "kind": "lower", "rule": "n_kind",
      "params": { "n": 4, "score": "sum" } },
    { "name": "Full House", "kind": "lower", "rule": "full_house",
      "params": { "score": 25 } }
  ]
}
```

| `rule` | Matches when | Parameters |
|---|---|---|
| `upper` | always | `face` (1–6); score = face × count |
| `n_kind` | at least `n` dice match | `n`, `score` (`"sum"` or a fixed number) |
| `full_house` | 3+2, or all five equal | `score` (`"sum"` or a fixed number) |
| `straight` | `length` consecutive faces present | `length`, `score` |
| `all_same` | all five dice equal | `score` |
| `sum` | always | none; score = total of all five dice |

**One constraint:** columns with `kind: "upper"` must come first — their subtotal
is what the bonus is measured against — and column order is the bit order inside
the solver's masks. After editing, run `python solve.py` to rebuild; if you
forget, the tools will refuse to run against stale tables.

The two files in `presets/` are worked examples. `use.py` just copies one over
`config.json` and rebuilds.

---

## How it works

The state space is

```
(remaining upper mask, current upper subtotal, remaining lower mask)  ×  252 rolls
```

252 is the number of distinct **multisets** of five dice — not 6⁵ = 7776 ordered
outcomes, since the dice are indistinguishable. The three rolls inside a turn are
handled by a single keep→reroll transition tensor.

That is about 176k states and 5 seconds for the 12-column Clubhouse ruleset, and
about 350k states and 10 seconds for standard 13-column Yahtzee.

---

## Does it actually compute the right numbers?

Every baseline is checked against an **independent** Monte-Carlo simulation that
rolls real dice and scores them through a separate code path. That catches the
kind of bug a self-consistent DP hides — wrong transition probabilities, bad mask
arithmetic, a double-counted bonus.

| Ruleset | Check | DP | Simulation |
|---|---|---|---|
| clubhouse | full game | 191.774 | 192.37 ± 0.70 |
| clubhouse | upper section only | 71.952 | 71.82 ± 0.45 |
| clubhouse | lower section only | 88.660 | 87.89 ± 0.47 |
| standard | full game | 245.905 | 245.47 ± 0.72 |
| standard | upper section only | 71.952 | 71.82 ± 0.45 |
| standard | lower section only | 140.030 | 140.07 ± 0.56 |

The refactor that added multi-ruleset support reproduces the old
single-ruleset numbers **bit for bit**. The standard scoring table was also
hand-checked on edge-case rolls — e.g. `5 5 5 5 5` scores 25 as three of a kind,
25 as four of a kind, 25 as a full house, and 50 as a Yahtzee, all at once.

**Known limitation:** standard mode does **not** implement the Yahtzee bonus
(+100 for extra Yahtzees). That needs "has Yahtzee been used yet?" in the state,
which doubles the state space. So 245.91 sits below the published optimum of
254.59 — the 8.68 gap is exactly what the Yahtzee bonus is worth.

---

## Two counterintuitive results

**1. Never spend a high-value column on a cheap score.**

Given `1 2 4 6 6` on the first turn, taking **Sixes for 12** costs you 10 points
of expected value compared to taking **Aces for 1**. Sixes is the biggest box in
the upper section (max 30), and cashing it in for 12 drops your chance of the +35
bonus from **54.2% to 12.1%**. (Both figures measured by simulating the two
resulting positions 8000 times each.)

Same pattern elsewhere: `4 4 4 4 1` should go to Fours for 16, not Four of a Kind
for 17. And `4 6 6 6 6` should go to Four of a Kind for 28, not Chance for 28 —
a 15.1-point difference.

**2. Abandon a column early rather than half-heartedly.**

Facing `2 4 4 6 6`, chasing a large straight succeeds only 16% of the time. You
are better off using that turn to build a big Chance score (~24) and chasing the
large straight from scratch next turn — from scratch it succeeds 26% of the time.

---

## Assumptions and caveats

- Both players are modelled as **expected-score maximisers**. Against a weaker
  opponent your real win probability is **higher** than the number printed.
- The advice is **expected-score optimal, not win-probability optimal**. The two
  coincide almost everywhere, but when you are far behind and need variance, the
  EV-maximising line is not necessarily the one that maximises your chance of
  winning.
- The dice have to be fair. I have no way to check that one.

## License

[MIT](LICENSE)
