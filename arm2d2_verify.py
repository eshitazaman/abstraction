"""
Cross-validate the lemma-based result on the small Arm2D2 NFA.

The lemma-based pipeline (plan_automata.automata_based_plan_computation,
implementing Lemma 9 / Algorithm 2) reported that

    L(NFA_P2)  is non-empty
    shortest accepting plan length = 10 moves
    example plan word (from enumeration):
        rl1 rl1 rl1 rl1 rl1 rl2 rl2 rl2 rl2 rl2

Here we re-check the same claim using the *direct* Definition-1 validators in
nfa_.py (check_p1, check_p2), which simulate delta* on the original NFA
without any lemma, product, or fixpoint reasoning.

The two answers must agree. Additionally we exercise a couple of plan words
we KNOW should fail (empty plan, plan with a step too few, plan with an rr1
that pulls back before the goal) so P1/P2 can flag them.
"""

from arm2d2_small_plan import build_nfa


def delta(nfa, state, action):
    """delta(s, a): successor set of s on action a."""
    if state in nfa.transitions and action in nfa.transitions[state]:
        return nfa.transitions[state][action]
    return set()


def delta_star(nfa, state, word):
    """delta*(s, w): states reachable from s after reading word (an iterable of symbols)."""
    current = {state}
    for symbol in word:
        nxt = set()
        for s in current:
            nxt |= delta(nfa, s, symbol)
        current = nxt
    return current


def check_p1_word(nfa, word):
    """P1 for a single-word plan {word}: delta*(s_init, word) subseteq F."""
    reachable = delta_star(nfa, nfa.initial_state, word)
    ok = reachable.issubset(nfa.final_states)
    return ok, reachable


def check_p2_word(nfa, word):
    """
    P2 for a single-word plan {word}: for every proper prefix w[:k]
    and every state s reachable by w[:k], the next symbol w[k] must be
    enabled at s (delta(s, w[k]) non-empty).

    Returns (ok, offending) where offending is (k, state) of first violation,
    or None if plan satisfies P2.
    """
    for k in range(len(word)):
        prefix = word[:k]
        next_sym = word[k]
        reachable = delta_star(nfa, nfa.initial_state, prefix)
        for s in reachable:
            if not delta(nfa, s, next_sym):
                return False, (k, s)
    return True, None


def verify(nfa, word, label):
    print(f"--- {label} ---")
    print(f"plan word ({len(word)} moves): {' '.join(word)}")
    p1_ok, reach = check_p1_word(nfa, word)
    print(f"P1: delta*(s_init, w) has {len(reach)} states, "
          f"all in F? {p1_ok}")
    if not p1_ok:
        outside = sorted(reach - nfa.final_states)[:5]
        print(f"    states outside F (up to 5): {outside}")
    p2_ok, off = check_p2_word(nfa, word)
    print(f"P2: every proper-prefix reachable state has next symbol enabled?"
          f" {p2_ok}")
    if not p2_ok:
        k, s = off
        print(f"    first violation at prefix len {k}, state {s}, "
              f"missing symbol {word[k]}")
    print(f"Valid plan? {p1_ok and p2_ok}\n")
    return p1_ok and p2_ok


if __name__ == "__main__":
    nfa = build_nfa()

    shortest = ("rl1",) * 5 + ("rl2",) * 5
    verify(nfa, shortest, "Shortest plan reported by lemma-based pipeline")

    interleaved = ("rl1", "rl2", "rl1", "rl2", "rl1", "rl2",
                   "rl1", "rl2", "rl1", "rl2")
    verify(nfa, interleaved, "Interleaved rl1/rl2 (same 10 moves, reordered)")

    too_short = ("rl1",) * 5 + ("rl2",) * 4
    verify(nfa, too_short, "One step short (9 moves) - expected P1 to FAIL")

    with_rr1 = ("rl1", "rl1", "rl1", "rl1", "rl1",
                "rr1", "rl2", "rl2", "rl2", "rl2", "rl2")
    verify(nfa, with_rr1, "Includes rr1 that pulls x1 out of goal band "
                          "- expected P1 to FAIL")
