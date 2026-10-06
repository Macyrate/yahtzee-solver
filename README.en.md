# yahtzee-solver

A command-line Yahtzee advisor that recommends which dice to keep, reroll, and score to **maximize expected final score**.

The solver enumerates game states with dynamic programming and precomputes their values. A separate Monte Carlo simulator estimates win, draw, and loss probabilities when both players follow the expected-score strategy.

[中文说明](README.md) · [Quick start](#quick-start) · [Usage](#usage) · [Rules and limitations](#rules-and-limitations) · [Development and validation](#development-and-validation)

## Features

- **Advice after each roll:** compare keep choices, expected final scores, and the cost of alternatives.
- **Scorecard tracking:** calculate category scores, upper-section progress, and the bonus.
- **Win probability estimates:** simulate the remaining game from both scorecards.
- **JSON rulesets:** use either included preset or adjust category scoring.

| Preset | Scoring model | Categories | Expected opening score¹ |
| --- | --- | --- | --- |
| `clubhouse` | Yahtzee in *Clubhouse Games: 51 Worldwide Classics* | 12 | 191.774 |
| `standard` | A simplified model based on standard Yahtzee | 13 | 245.905 |

¹ These are the preset values recorded in this repository. The `standard` model omits additional Yahtzee bonuses and Joker rules, so its value is not the optimum for the complete official rules.

## Quick start

Requires **Python 3.9+** and **NumPy >= 1.24**. On macOS or Linux:

```bash
git clone https://github.com/Macyrate/yahtzee-solver.git
cd yahtzee-solver
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python advise.py rules
```

In Windows PowerShell, create the environment with `py -3 -m venv .venv` and activate it with `.\.venv\Scripts\Activate.ps1`.

The repository includes `tables.npz`; no build is needed while it matches the active configuration. It also includes an existing scorecard. **Starting a new game clears `state.json`; back it up first if you want to keep it:**

```bash
python advise.py reset
python advise.py adv "1 3 3 3 4" 2
```

The `2` means two rerolls remain. After each actual roll, enter the new dice and remaining reroll count. Once no rerolls remain, choose a category to score.

## Usage

Run these commands from the project directory with the virtual environment activated.

### Inspect the rules and scorecard

```bash
python advise.py rules
python advise.py show
```

The CLI currently prints Chinese labels. With the `clubhouse` preset, the baseline output includes:

```text
开局最优期望 (全部 12 栏): 191.774
上区单练                     : 71.952
下区单练                     : 88.660
```

These are the expected scores for the full game, upper section alone, and lower section alone.

### Get advice and record a score

```bash
python advise.py adv "1 3 3 3 4" 2
python advise.py adv "1 2 3 3 3" 0
python advise.py take 3点 "1 2 3 3 3"
python advise.py show
```

| Input | Meaning |
| --- | --- |
| `"1 3 3 3 4"` | Five dice, each from 1 to 6, separated by spaces and quoted |
| `2` / `1` / `0` | Rerolls remaining; `0` compares scoring choices |
| `3点` | A category name from the active ruleset; see `rules` output |

The included presets use Chinese category names for commands; `3点` means Threes. `adv` reads the current scorecard, while `take` calculates and writes a score to `state.json`. **Calling `take` again for the same category overwrites its previous score.**

### Estimate win probability

```bash
python pwin.py 8 6000 "1点=2,2点=8,3点=12,机会=22"
```

| Argument | Meaning |
| --- | --- |
| `8` | Expected turns remaining, checked against both scorecards |
| `6000` | Samples per player; defaults to 3000 when omitted |
| `"category=score,…"` | All filled opponent categories, including zeros; use `""` for an empty card |

Your scorecard is read from `state.json`. Omitted opponent categories are treated as unfilled. If the first argument does not match the remaining categories, the program prints a warning and uses **each player's actual number of unfilled categories**. Output includes mean final scores, P10 / P90 percentiles, and win/draw/loss proportions.

These are finite-sample estimates; the program does not report confidence intervals. More samples generally reduce sampling error and increase runtime.

### Switch rules or rebuild tables

```bash
python use.py                 # List presets
python use.py standard        # Replace config.json and rebuild tables.npz
python use.py clubhouse       # Restore the default preset and rebuild
python solve.py --check       # Display the active rules without building
python solve.py               # Rebuild from config.json
```

Save custom configuration and scorecard data before switching. `use.py` does not reset `state.json`; run `python advise.py reset` to start a new game after switching. Build time depends on ruleset size, hardware, and the NumPy / BLAS environment.

## Rules and limitations

The model assumes five fair, independent six-sided dice, up to three rolls per turn, and the option to keep any subset between rolls.

- Advice maximizes **expected final score**, which does not necessarily maximize the chance of winning a particular game.
- Win simulations assume both players follow that strategy. Different opponent behavior can change the actual probability in either direction.
- `standard` omits the +100 bonus for additional Yahtzees and scorecard-dependent Joker scoring. Both presets accept five identical dice as a full house. It is therefore a simplified variant.
- Dynamic programming enumerates states but uses floating-point arithmetic. “Exact” describes the algorithm's lack of strategy heuristics, not an absence of numerical error.
- Keep the custom upper-section bonus threshold at **63** for now: table construction caps the subtotal at 63. Editing JSON alone does not provide support for arbitrary thresholds.

### Customize scoring

Start from a configuration in `presets/`. Each category specifies a `kind`, a `rule`, and any rule parameters. For example:

```json
{
  "name": "四条",
  "kind": "lower",
  "rule": "n_kind",
  "params": { "n": 4, "score": "sum" }
}
```

| `rule` | Scoring condition | Parameters |
| --- | --- | --- |
| `upper` | Sum of dice showing the specified face | Category property `face`: 1–6 |
| `n_kind` | At least n identical dice | `n`, `score`: `"sum"` or a fixed score |
| `full_house` | 3+2 or five identical dice | `score`: `"sum"` or a fixed score |
| `straight` | At least `length` consecutive faces | `length`, `score` |
| `all_same` | Five identical dice | `score` |
| `sum` | Sum of all five dice | None |

Upper categories must precede all lower categories. Category names should be unique, and category order determines mask bit positions. After editing `config.json`, run `python solve.py`. The advisor checks the configuration fingerprint and refuses mismatched tables.

## How it works

The between-turn state is `(remaining upper mask, upper subtotal, remaining lower mask)`. Backward induction computes the optimal expected future score. Within each turn, the solver enumerates 252 unordered dice outcomes and 462 possible keeps, comparing actions through their reroll transition probabilities.

`solve.py` precomputes the value tables. `advise.py` loads them and combines them with the current scorecard. `pwin.py` uses the resulting strategy to simulate both players' remaining games.

## Development and validation

| File | Responsibility |
| --- | --- |
| [rules.py](rules.py) | Configuration, scoring matrices, dice space, and mask helpers |
| [solve.py](solve.py) | Dynamic-programming table construction |
| [advise.py](advise.py) | Advice, scorecards, and full-game simulation |
| [pwin.py](pwin.py) | Final-score and win/draw/loss simulation |
| [use.py](use.py) | Preset switching |
| [verify.py](verify.py) | Statistical checks with separate rolling and scoring paths |
| [config.json](config.json) / [presets/](presets/) | Active configuration / included presets |
| `tables.npz` | Precomputed data with a configuration fingerprint |
| [state.json](state.json) / [results/](results/) | Current scorecard / historical game records |
| [AGENTS.md](AGENTS.md) | Repository collaboration guidelines in Chinese |

Lightweight checks:

```bash
python -m py_compile rules.py solve.py advise.py pwin.py use.py verify.py
python solve.py --check
python advise.py rules
```

After changing scoring or solver logic, rebuild and run statistical validation as appropriate:

```bash
python solve.py
python verify.py                # Defaults to 8000 games per check
python verify.py 32 56 20 1000   # Position (ru, s, rl) and sample count
python advise.py sim 20000      # Full-game simulation
```

Full simulations may take a while. `verify.py` rolls and scores through separate paths, but its action policy still depends on the DP tables. It checks agreement between simulated means and DP expectations; it is not an independent proof of optimality. Statistical checks can fluctuate. Include the ruleset, sample count, and runtime environment when reporting results.

### Contributing

Report problems through [Issues](https://github.com/Macyrate/yahtzee-solver/issues) or submit a pull request. For decision-related bugs, include the configuration, filled scorecard, dice, rerolls remaining, actual output, and expected behavior.

Run checks appropriate to your change. Scoring or solver changes should cover edge-case rolls and both presets. Keep personal scorecards, historical records, and unrelated regenerated tables out of changes. Update both READMEs when CLI or ruleset behavior changes.

## License

[MIT License](LICENSE), Copyright © 2026 Macyrate.
