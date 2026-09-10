# Abstraction — planning with nondeterministic actions (NFA tooling)

This repository implements **automata-based plan synthesis**: build **DFA\(_{P1}\)** (P1-determinization), the product **NFA \(\times\) DFA\(_{P1}\)**, then **NFA\(_{P2}\)** by the iterative P2 restriction (**Lemma 9 / Algorithm 2** from the paper). Valid plans correspond to **L(NFA\(_{P2}\))**.

Run all commands from the **repository root** so Python can resolve local modules (`plan_automata`, `plts_to_nfa`, `grid_world_nfa`).

## Requirements

- **Python** 3.10 or newer (tested with 3.10+; a 3.14 venv works in this project).
- **automata-lib** — provides `automata.fa.nfa.NFA` used throughout.

Install into a virtual environment (recommended):

```bash
cd /path/to/abstraction
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install automata-lib
```

Minimal dependency for the core planning code:

| Package      | Role                              |
|-------------|------------------------------------|
| `automata-lib` | NFAs, state/transition structures |

Standard library only besides that: `argparse`, `collections`, `re`, etc.

Optional (only if you use PRISM export):

- No extra Python package is required; output is a `.prism` text file for [PRISM](https://www.prismmodelchecker.org/).

## `plan_automata.py` — demo / PLTS-driven planning

### Built-in example NFA

Runs a small hard-coded NFA (see `--example` block in the file), then prints DFA\(_{P1}\), product, NFA\(_{P2}\), and enumerated valid plan words (length \(\leq 10\) by default in `enumerate_valid_plans`).

```bash
python plan_automata.py --example
```

### Load an NFA from a `.kr` PLTS file

Default file name is `salon-4-0.25.kr` in the current directory. Override with `--file`:

```bash
python plan_automata.py --file example.kr
python plan_automata.py --file tests/hotel/example-fig-2.kr
```

### Deterministic reading of the PLTS (optional)

```bash
python plan_automata.py --file example.kr --deterministic
# short form
python plan_automata.py --file example.kr -d
```

### CLI summary

| Option | Meaning |
|--------|---------|
| `--example` | Use the fixed toy NFA in the script (no `.kr` file). |
| `--file PATH` | Path to a `.kr` file (default: `salon-4-0.25.kr`). |
| `-d`, `--deterministic` | Build a deterministic NFA from the PLTS when applicable. |

### Use as a library

```python
from automata.fa.nfa import NFA
from plan_automata import automata_based_plan_computation

nfa = NFA(...)  # your model
result = automata_based_plan_computation(nfa, verbose=True, enumerate_plans=True)
# result["nfa_p2"], result["valid_plans"], result["language_nonempty"], ...
```

## `grid_world_nfa.py` — grid robot benchmarks

Builds an NFA for an \(n \times n\) grid (robot at bottom-left style coordinates), then runs the same **P1 \(\land\) P2** pipeline (or only existence / NP2 construction).

### Basic run (default \(4\times4\), goal top-right, `se-corners` actions)

```bash
python grid_world_nfa.py
```

### Grid size, start, goal, obstacles

```bash
python grid_world_nfa.py -n 5 --robot-start 1,1 --goal 5,5 \
  --obstacles "2,2;3,1"
```

Multiple goals (semicolon-separated):

```bash
python grid_world_nfa.py -n 6 --goal "5,5;6,6"
```

### Action semantics (`--action-mode`)

| Mode | Description |
|------|-------------|
| `se-corners` (default) | **A** = W\(\cup\)N, **B** = E\(\cup\)S (nondeterministic legs). |
| `north-bias` | **A** = W\(\cup\)N, **B** = E\(\cup\)N. |
| `cardinal` | Deterministic **U** / **D** / **L** / **R** moves. |

```bash
python grid_world_nfa.py -n 4 --action-mode north-bias
python grid_world_nfa.py -n 4 --action-mode cardinal
```

### Faster: only check if *some* valid plan exists

Skips enumerating all words up to the default cap (much faster on large products).

```bash
python grid_world_nfa.py -n 5 --exists-only
```

### Build and inspect NP2 only (optional DFA\(_{P1}\) dump / PRISM)

```bash
python grid_world_nfa.py -n 4 --np2-only
```

Dump DFA\(_{P1}\) transitions (can be huge) or write them to a file:

```bash
python grid_world_nfa.py -n 4 --np2-only --list-dfa-p1-transitions --dfa-p1-max-lines 50
python grid_world_nfa.py -n 5 --np2-only --dfa-p1-out dfa_p1.txt
```

Export NFA\(_{P2}\) as a PRISM dtmc (uniform resolution of nondeterminism per state/action):

```bash
python grid_world_nfa.py -n 4 --np2-only --prism-out robot.prism
```

### Random obstacles (reproducible with `--seed`)

```bash
python grid_world_nfa.py -n 5 --random-obstacles 8 --seed 42
```

### Dead-cell diagnostic

Prints cells where an action has no legal successor (often correlates with empty **L(NFA\(_{P2}\))**):

```bash
python grid_world_nfa.py -n 5 --check-dead-cells --obstacles "2,2;3,3"
```

### End of `grid_world_nfa.py` entry point

The script calls `main()` only when executed as `__main__`:

```bash
python grid_world_nfa.py [options]
```

## FOND / IPPC chain examples (lemma pipeline)

These are **chain encodings** of Tireworld, beam-walk, doors, and first-responders (probability / `oneof` → nondeterministic branches, dead-ends replaced by a total reset so a finite P1∧P2 *word* exists). They are **not** the official PDDL instances; a FOND *policy* planner would run those instead.

The lemma-based algorithm is always `automata_based_plan_computation` in `plan_automata.py` (DFA\(_{P_1}\) → product → NFA\(_{P_2}\) / Lemma 9).

### Single instance

From the repo root (activate `.venv` if you use one):

```python
from tireworld import build_tireworld_nfa
from plan_automata import automata_based_plan_computation

nfa = build_tireworld_nfa(5)  # N = number of cities
result = automata_based_plan_computation(nfa, verbose=True, enumerate_plans=False)
print(result["language_nonempty"], result["shortest_plan_length"])  # True, 8
```

Same pipeline, other domains (`N` is chain length: beam positions, rooms, or fire sites):

```python
from beam_walk import build_beam_walk_nfa
from doors import build_doors_nfa
from first_responders import build_first_responders_nfa

nfa = build_beam_walk_nfa(5)           # k* = 12
# nfa = build_doors_nfa(5)
# nfa = build_first_responders_nfa(5)
result = automata_based_plan_computation(nfa, verbose=True, enumerate_plans=False)
```

On-the-fly product (same lemmas, fused subset + product BFS):

```python
from plan_automata import automata_based_plan_on_the_fly
result = automata_based_plan_on_the_fly(nfa, verbose=True, enumerate_plans=False)
```

| Domain | Builder | \(N=5\) shortest plan \(k^{*}\) |
|--------|---------|--------------------------------|
| Tireworld | `build_tireworld_nfa(N)` | \(2N-2 = 8\) |
| Beam-walk | `build_beam_walk_nfa(N)` | \(3N-3 = 12\) |
| Doors | `build_doors_nfa(N)` | \(3N-3 = 12\) |
| First-responders | `build_first_responders_nfa(N)` | \(3N-3 = 12\) |

`python tireworld.py --n 5` only **prints NFA sizes**; it does not run DFA\(_{P_1}\) / NFA\(_{P_2}\).

### Scaling sweeps

```bash
# Tireworld only (variants: short-circuit, pure, otf)
python scale_tireworld.py --scales 5 10 50 --variant short-circuit --verbose

# One domain or all four; append metrics to CSV
python scale_fond.py --domain tireworld --scales 5 10 50
python scale_fond.py --domain beam-walk --scales 5 20 100
python scale_fond.py --domain doors --scales 5 20 100
python scale_fond.py --domain first-responders --scales 5 20 100
python scale_fond.py --domain all --scales 5 50 100 --csv fond_scaling.csv
```

`--variant short-circuit` (default on `scale_tireworld.py`) is the lemma two-stage pipeline with an early exit if DFA\(_{P_1}\) has no accepting macros (does not fire on these nonempty instances).

## Optional: `nfa_p2_to_prism.py`

Builds a grid NFA and writes **NFA\(_{P2}\)** as PRISM:

```bash
python nfa_p2_to_prism.py -n 4 --robot-start 1,1 --obstacles "2,2" -o out.prism
```

## `scripts/tab_exp_grid_abs_benchmark.py`

Experiment driver for grid statistics (see script help):

```bash
python scripts/tab_exp_grid_abs_benchmark.py --help
```

## Troubleshooting

- **`ModuleNotFoundError: automata`** — Install `automata-lib` (`pip install automata-lib`).
- **`ModuleNotFoundError` for `plan_automata` / `plts_to_nfa`** — Run from the repo root, or set `PYTHONPATH` to the repo root.
- **Timeouts or huge DFA\(_{P1}\)** — On larger grids with nondeterministic action modes, subset construction can explode; use `--exists-only`, smaller `-n`, or `--np2-only` with counts only.
