"""Side-by-side comparison of action_mode={se-corners, north-bias} on empty grids."""

from grid_world_nfa import generate_grid_world_nfa
from plan_automata import automata_based_plan_computation


def run(n: int, mode: str):
    nfa, _ = generate_grid_world_nfa(n=n, action_mode=mode, verbose=False)
    res = automata_based_plan_computation(nfa, verbose=False, enumerate_plans=False)
    return res


def main():
    print(f"{'n':>3}  {'mode':<12}  {'plan?':<6}  {'shortest':>9}  {'NFA_P2 states':>15}")
    print("-" * 60)
    for n in (2, 3, 4, 5, 6):
        for mode in ("se-corners", "north-bias"):
            r = run(n, mode)
            ok = "yes" if r["language_nonempty"] else "NO"
            sh = r["shortest_plan_length"] if r["language_nonempty"] else "-"
            np2 = r["stats"]["nfa_p2_reachable"]
            print(f"{n:>3}  {mode:<12}  {ok:<6}  {str(sh):>9}  {np2:>15}")


if __name__ == "__main__":
    main()
