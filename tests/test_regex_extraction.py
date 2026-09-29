import re

from automata.fa.nfa import NFA

from plan_automata import automata_based_plan_computation, format_nfa_p2, nfa_p2_to_regex


def test_extracts_paper_example_language():
    nfa = NFA(
        states={'s0', 's1', 's2', 's3'}, input_symbols={'a', 'b'},
        transitions={
            's0': {'a': {'s1', 's2'}, 'b': {'s2'}},
            's1': {}, 's2': {'a': {'s3'}}, 's3': {},
        },
        initial_state='s0', final_states={'s2', 's3'},
    )
    for backend in ('explicit', 'compact'):
        result = automata_based_plan_computation(
            nfa, verbose=False, enumerate_plans=False, backend=backend,
        )
        regex = nfa_p2_to_regex(result['nfa_p2'], syntax='python')
        for word in ('', 'a', 'aa', 'b', 'ba', 'bb', 'baa'):
            assert (re.fullmatch(regex, word) is not None) == (word in {'b', 'ba'})


def test_cycles_epsilon_and_escaped_action_labels():
    automaton = {
        'states': {'start', 'final'}, 'initial': 'start', 'finals': {'start', 'final'},
        'transitions': {
            'start': {'a+': {'start'}, 'go.down': {'final'}},
            'final': {'?': {'final'}},
        },
    }
    regex = nfa_p2_to_regex(automaton, syntax='python')
    for word in ('', 'a+', 'a+a+', 'go.down', 'a+go.down??'):
        assert re.fullmatch(regex, word) is not None
    for word in ('a', 'goXdown', '?', 'a+?'):
        assert re.fullmatch(regex, word) is None


def test_empty_language():
    assert re.fullmatch(nfa_p2_to_regex({'initial': None, 'finals': set()}, syntax='python'), '') is None
    assert re.fullmatch(nfa_p2_to_regex({
        'states': {'s', 'f'}, 'initial': 's', 'finals': {'f'}, 'transitions': {},
    }, syntax='python'), 'anything') is None


def test_readable_notation():
    automaton = {
        'states': {'s', 'f'}, 'initial': 's', 'finals': {'s', 'f'},
        'transitions': {'s': {'go.down': {'f'}}},
    }
    assert nfa_p2_to_regex(automaton) == "ε + 'go.down'"
    assert nfa_p2_to_regex({'initial': None, 'finals': set()}) == '∅'


def test_brzozowski_equations_handle_mutual_recursion_and_multiple_finals():
    automaton = {
        'states': {'s', 'left', 'right'},
        'initial': 's',
        'finals': {'left', 'right'},
        'transitions': {
            's': {'a': {'left'}, 'b': {'right'}},
            'left': {'x': {'right'}},
            'right': {'y': {'left'}},
        },
    }
    regex = nfa_p2_to_regex(automaton, syntax='python')
    for word in ('a', 'b', 'ax', 'by', 'axy', 'byx', 'axyx', 'byxy'):
        assert re.fullmatch(regex, word) is not None
    for word in ('', 'x', 'ay', 'bx', 'axyxyy'):
        assert re.fullmatch(regex, word) is None


def test_formats_final_automaton_for_compact_backend():
    nfa = NFA(
        states={'s', 'f'}, input_symbols={'go'},
        transitions={'s': {'go': {'f'}}}, initial_state='s', final_states={'f'},
    )
    result = automata_based_plan_computation(
        nfa, backend='compact', verbose=False, enumerate_plans=False,
    )
    listing = format_nfa_p2(result['nfa_p2'])
    assert 'FINAL NFA_P2' in listing
    assert "--'go'-->" in listing
