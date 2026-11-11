"""Every automaton is checked against an independently written rule
(a regular expression, or Python's datetime) on large generated input sets."""

import datetime
import itertools
import random
import re

import pytest

from fa_lab.automata import DFA, NFA, dfa_from_words, EPS
from fa_lab.validators import all_applications, date_levels, plate_with_state_codes_size

APPS = all_applications()
PLATE_RE = re.compile(r"[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}|\d{2}BH\d{4}[A-Z]{2}")
MOBILE_RE = re.compile(r"(\+91|91|0)?[6-9]\d{9}")


def plate_rule(s: str) -> bool:
    return PLATE_RE.fullmatch(s.upper().replace(" ", "").replace("-", "")) is not None


def mobile_rule(s: str) -> bool:
    return MOBILE_RE.fullmatch(s.replace(" ", "").replace("-", "")) is not None


def date_rule(s: str) -> bool:
    if not re.fullmatch(r"\d\d/\d\d/\d{4}", s):
        return False
    try:
        d = datetime.datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        return False
    return 1900 <= d.year <= 2099


RULES = {"plate": plate_rule, "mobile": mobile_rule, "date": date_rule}


def mutate(s: str, rng: random.Random, pool: str) -> str:
    s = list(s)
    for _ in range(rng.randint(0, 2)):
        op = rng.choice("sid")
        i = rng.randrange(len(s) + 1)
        if op == "s" and s:
            s[min(i, len(s) - 1)] = rng.choice(pool)
        elif op == "i":
            s.insert(i, rng.choice(pool))
        elif op == "d" and s:
            del s[min(i, len(s) - 1)]
    return "".join(s)


# ----------------------------------------------------------- listed examples
@pytest.mark.parametrize("key", list(APPS))
def test_listed_examples(key):
    app = APPS[key]
    assert len(app.accepted) >= 5 and len(app.rejected) >= 5
    for s in app.accepted:
        assert app.check(s), s
        assert RULES[key](s), s
    for s in app.rejected:
        assert not app.check(s), s
        assert not RULES[key](s), s


# ----------------------------------------------------------- vehicle plate
def test_plate_exhaustive_short_letter_digit_strings():
    """All 1 398 100 strings of length <= 10 over {K, B, H, 7} (one char per class)."""
    app = APPS["plate"]
    n = 0
    for length in range(0, 11):
        for t in itertools.product("KBH7", repeat=length):
            s = "".join(t)
            assert app.check(s) == plate_rule(s), s
            n += 1
    assert n == 1398101


def test_plate_random_mutations():
    rng = random.Random(1)
    app = APPS["plate"]
    pool = "ABHKTNZ0123456789 -#a"
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    for _ in range(40000):
        if rng.random() < 0.5:
            base = (rng.choice(letters) + rng.choice(letters) + f"{rng.randint(0, 99):02d}" +
                    "".join(rng.choice(letters) for _ in range(rng.randint(1, 3))) + f"{rng.randint(0, 9999):04d}")
        else:
            base = f"{rng.randint(21, 30)}BH{rng.randint(0, 9999):04d}" + rng.choice(letters) + rng.choice(letters)
        s = mutate(base, rng, pool)
        assert app.check(s) == plate_rule(s), s


def test_plate_nfa_subset_minimal_agree():
    app = APPS["plate"]
    subset = app.extra["subset"]
    for t in itertools.product(["A", "B", "H", "D"], repeat=10):
        assert app.nfa.accepts(t) == subset.accepts(t) == app.dfa.accepts(t)


# ----------------------------------------------------------- mobile number
def test_mobile_exhaustive_prefix_alphabet():
    """All strings of length <= 13 over {0, 1, 9}, with and without a leading '+'."""
    app = APPS["mobile"]
    n = 0
    for length in range(0, 14):
        for t in itertools.product("019", repeat=length):
            s = "".join(t)
            assert app.check(s) == mobile_rule(s), s
            assert app.check("+" + s) == mobile_rule("+" + s), s
            n += 2
    assert n == 2 * sum(3 ** k for k in range(14))


def test_mobile_random_mutations():
    rng = random.Random(2)
    app = APPS["mobile"]
    pool = "0123456789+ -o"
    for _ in range(60000):
        num = str(rng.randint(5, 9)) + "".join(rng.choice("0123456789") for _ in range(9))
        s = mutate(rng.choice(["", "+91", "91", "0", "+91 ", "+9", "00"]) + num, rng, pool)
        assert app.check(s) == mobile_rule(s), s


def test_mobile_subset_states_track_both_guesses():
    app = APPS["mobile"]
    subsets = app.extra["subsets"]
    assert any({"k2", "n3"} <= set(S) for S in subsets.values())  # after '91'
    assert len(app.nfa.states) == 14 and len(app.extra["subset"].states) == 24
    assert len(app.dfa.states) == 24  # nothing to merge: the blow-up is real


# ----------------------------------------------------------- date of birth
def test_date_every_valid_date_accepted():
    app = APPS["date"]
    d = datetime.date(1900, 1, 1)
    n = 0
    while d.year < 2100:
        assert app.check(d.strftime("%d/%m/%Y"))
        d += datetime.timedelta(days=1)
        n += 1
    assert n == 73049


def test_date_grid_against_datetime():
    """DD 00-39 x MM 00-19 x YYYY 1880-2119 = 192 000 strings."""
    app = APPS["date"]
    for dd in range(40):
        for mm in range(20):
            for yy in range(1880, 2120):
                s = f"{dd:02d}/{mm:02d}/{yy}"
                assert app.check(s) == date_rule(s), s


def test_date_random_mutations():
    rng = random.Random(3)
    app = APPS["date"]
    for _ in range(40000):
        s = mutate(f"{rng.randint(0, 32):02d}/{rng.randint(0, 13):02d}/{rng.randint(1890, 2110)}",
                   rng, "0123456789/-. a")
        assert app.check(s) == date_rule(s), s


def test_date_state_growth():
    sizes = {lv: v[2] for lv, v in date_levels().items()}
    assert sizes == {"ranges": 15, "months": 22, "leap": 35}
    assert len(APPS["date"].extra["shape"].states) == 11


# ----------------------------------------------------------- library itself
def test_minimise_trie_of_finite_language():
    words = ["ab", "aab", "b", "bb"]
    m = dfa_from_words("t", words, ["a", "b"]).minimise()
    for length in range(5):
        for t in itertools.product("ab", repeat=length):
            assert m.accepts(t) == ("".join(t) in words)


def test_subset_construction_textbook_example():
    # strings over {a,b} whose third-from-last symbol is 'a'
    d = {("0", "a"): {"0", "1"}, ("0", "b"): {"0"}, ("1", "a"): {"2"}, ("1", "b"): {"2"},
         ("2", "a"): {"3"}, ("2", "b"): {"3"}}
    nfa = NFA({"0", "1", "2", "3"}, ["a", "b"], d, "0", {"3"})
    dfa, _ = nfa.to_dfa()
    assert len(dfa.minimise().states) == 8  # the classic 2^3 lower bound
    for length in range(8):
        for t in itertools.product("ab", repeat=length):
            assert dfa.accepts(t) == (length >= 3 and t[-3] == "a")


def test_state_codes_cost():
    assert plate_with_state_codes_size() == 37
    assert len(APPS["plate"].dfa.states) == 21
