# Arm2D2 model specification

Two-joint planar robotic arm modelled as a nondeterministic finite automaton
(NFA). All angles are in degrees.

## 1. State variables

| Variable | Meaning              | Range           | Convention                                    |
| -------- | -------------------- | --------------- | --------------------------------------------- |
| `x1`     | Shoulder joint angle | `[0°, 180°]`    | Absolute angle                                |
| `x2`     | Elbow joint angle    | `[-120°, 120°]` | `0°` = arm fully extended; `±120°` = max bend |

## 2. Discretization

Angles are discretized on a uniform grid with step `h = 10°`:

- `X1 = { 0°, 10°, 20°, …, 180° }`         (19 values)
- `X2 = { −120°, −110°, …, 110°, 120° }`   (25 values)

State set `S = X1 × X2`, so `|S| = 475`.

State name convention: `q_{x1}_{x2}` with an `m` prefix for negative values
(e.g. `q_60_m30`).

## 3. Actions

Alphabet `Σ = { rl1, rr1, rl2, rr2 }`.

| Action | Joint          | Nominal displacement | Error tolerance |
| ------ | -------------- | -------------------: | --------------: |
| `rl1`  | shoulder (`x1`) |                `+30°` |          `±10°` |
| `rr1`  | shoulder (`x1`) |                `−30°` |          `±10°` |
| `rl2`  | elbow    (`x2`) |                `+30°` |          `±10°` |
| `rr2`  | elbow    (`x2`) |                `−30°` |          `±10°` |

Each action is modelled with the **two endpoints of its tolerance band**
(`nominal ± error`), yielding two nondeterministic legs per action:

```
rl1:  x1 → x1 + 20°   OR   x1 → x1 + 40°
rr1:  x1 → x1 − 20°   OR   x1 → x1 − 40°
rl2:  x2 → x2 + 20°   OR   x2 → x2 + 40°
rr2:  x2 → x2 − 20°   OR   x2 → x2 − 40°
```

## 4. Saturation (joint-limit clamping)

Any successor that would leave its joint range is clamped to the nearest
boundary:

- `sat1(v) = min(180°, max(0°, v))`
- `sat2(v) = min(120°, max(−120°, v))`

## 5. Transition relation

For every `⟨x1, x2⟩ ∈ S`, `δ : S × Σ → 2^S` is defined by:

```
δ(⟨x1, x2⟩, rl1) = { ⟨sat1(x1 + 20), x2⟩ , ⟨sat1(x1 + 40), x2⟩ }
δ(⟨x1, x2⟩, rr1) = { ⟨sat1(x1 − 20), x2⟩ , ⟨sat1(x1 − 40), x2⟩ }
δ(⟨x1, x2⟩, rl2) = { ⟨x1, sat2(x2 + 20)⟩ , ⟨x1, sat2(x2 + 40)⟩ }
δ(⟨x1, x2⟩, rr2) = { ⟨x1, sat2(x2 − 20)⟩ , ⟨x1, sat2(x2 − 40)⟩ }
```

Every action is enabled at every state, so `|δ| = 4 · |S| · 2 = 3,536`.

## 6. Initial and accepting states

- **Initial state:** `s₀ = ⟨60°, 30°⟩`  (i.e. `q_60_30`)
- **Goal region:**

  ```
  F = { ⟨x1, x2⟩ ∈ S :  85° ≤ x1 ≤ 100°  AND  40° ≤ x2 ≤ 60° }
  ```

  With the `10°` grid, `|F| = 6`:
  `{ (90,40), (90,50), (90,60), (100,40), (100,50), (100,60) }`.

## 7. Plan validity (P1 ∧ P2 universal semantics)

A plan is a finite word `w ∈ Σ*`. It is **valid** iff:

- **P1 (universal reachability of goal).** Every NFA run consuming `w` from
  `s₀` ends in a state in `F`, i.e. `δ*(s₀, w) ⊆ F`.
- **P2 (universal action availability).** For every proper prefix `v` of `w`
  and every state `p ∈ δ*(s₀, v)`, the next action after `v` is applicable and
  the remaining suffix is still a valid plan from `p`.

The set of all valid plans is the language `L(NFA_P2)`.

## 8. Instance summary

```
|S|               = 475
|δ|               = 3,536
|F|               = 6
|Σ|               = 4
s₀                = q_60_30
grid step h       = 10°
leg magnitudes    = {20°, 40°}   (nominal 30° ± error 10°)
```

## 9. Observation

Under the acceptance semantics of §7, this instance yields
`L(NFA_P2) = ∅` (verified by all three pipeline variants: pure two-stage,
short-circuit two-stage, and on-the-fly product). The reason is structural:

- Each action's two legs differ by `20°`, so every reachable P1 macro-state
  has width `≥ 20°` in the axis it just moved along (until it hits a
  saturation wall).
- Universal P1 requires the **entire macro** to lie inside `F`.
- The shoulder goal window `x1 ∈ [85°, 100°]` is only `15°` wide, so no
  reachable macro can fit within it.

To obtain a non-empty `L(NFA_P2)` while keeping the same action / error
structure, the goal region must be either
(i) at least `40°` wide in each axis, or
(ii) positioned against a saturation wall (which collapses macro width there).
