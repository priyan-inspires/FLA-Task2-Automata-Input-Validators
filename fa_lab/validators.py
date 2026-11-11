"""The three validation applications for Task 2.

1. Indian vehicle registration number  - union of two DFAs (state series + BH series)
2. Indian mobile number for OTP login   - hand-written NFA (guesses the '91' prefix),
                                          subset construction, minimisation
3. Date of birth DD/MM/YYYY             - a finite language, so the full calendar is
                                          regular; we measure what that costs in states
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Dict, List, Optional

from .automata import DFA, NFA, EPS, chain_dfa, dfa_from_words, union_nfa


@dataclass
class Application:
    key: str
    title: str
    normalise: Callable[[str], str]
    classify: Callable[[str], str]
    dfa: DFA
    accepted: List[str]
    rejected: List[str]
    syntax_only_note: str
    nfa: Optional[NFA] = None
    extra: Dict[str, object] = field(default_factory=dict)

    def symbols(self, text: str) -> List[str]:
        return [self.classify(c) for c in self.normalise(text)]

    def check(self, text: str) -> bool:
        return self.dfa.accepts(self.symbols(text))

    def trace(self, text: str):
        return self.dfa.trace(self.normalise(text), self.classify)


# =====================================================================
# 1. Vehicle registration number
#    State series : TN 45 AB 1234  -> LL DD L{1,3} DDDD
#    BH series    : 22 BH 1234 AA  -> DD B H DDDD LL
# =====================================================================
PLATE_SIGMA = ["A", "B", "H", "D", "O"]  # A = any other letter
LETTER = ["A", "B", "H"]


def plate_classify(c: str) -> str:
    if c == "B":
        return "B"
    if c == "H":
        return "H"
    if "A" <= c <= "Z":
        return "A"
    if c.isdigit() and c.isascii():
        return "D"
    return "O"


def plate_normalise(s: str) -> str:
    """Lexer step (not part of the automaton): upper-case, drop spaces and hyphens."""
    return s.upper().replace(" ", "").replace("-", "")


def _state_series_dfa() -> DFA:
    delta = {}
    for a in LETTER:
        delta[("p0", a)] = "p1"
        delta[("p1", a)] = "p2"
        delta[("p4", a)] = "p5"
        delta[("p5", a)] = "p6"
        delta[("p6", a)] = "p7"
    delta[("p2", "D")] = "p3"
    delta[("p3", "D")] = "p4"
    for q in ("p5", "p6", "p7"):
        delta[(q, "D")] = "p8"
    delta[("p8", "D")] = "p9"
    delta[("p9", "D")] = "p10"
    delta[("p10", "D")] = "p11"
    return DFA({f"p{i}" for i in range(12)}, PLATE_SIGMA, delta, "p0", {"p11"}, "State series")


def _bh_series_dfa() -> DFA:
    pattern = [["D"], ["D"], ["B"], ["H"], ["D"], ["D"], ["D"], ["D"], LETTER, LETTER]
    return chain_dfa("BH series", pattern, PLATE_SIGMA, prefix="b")


def build_plate() -> Application:
    parts = [_state_series_dfa(), _bh_series_dfa()]
    nfa = union_nfa("Vehicle plate", parts, start="s")
    subset, _ = nfa.to_dfa(prefix="d")
    dfa = subset.minimise(prefix="v")
    dfa.name = "Vehicle plate (minimal DFA)"
    return Application(
        key="plate",
        title="Vehicle registration number",
        normalise=plate_normalise,
        classify=plate_classify,
        dfa=dfa,
        nfa=nfa,
        accepted=["TN45AB1234", "TN 37 CK 0007", "KA01A9999", "MH-12-DEF-4521",
                  "22 BH 1234 AA", "25BH0001ZZ"],
        rejected=["TN45AB123", "TN4AB1234", "TN45ABCD1234", "T545AB1234",
                  "22 BX 1234 AA", "22BH1234A", "TN45AB12_4", ""],
        syntax_only_note="Shape only: whether TN 45 is a real RTO or the plate is "
                         "registered needs the VAHAN database.",
        extra={"parts": parts, "subset": subset},
    )


# Valid state / UT codes, used only for the 'regular but costly' measurement.
STATE_CODES = sorted("AN AP AR AS BR CG CH DD DL GA GJ HP HR JH JK KA KL LA LD MH ML MN MP "
                     "MZ NL OD PB PY RJ SK TN TR TS UK UP WB".split())


def plate_with_state_codes_size() -> int:
    """Minimal DFA size when the first two letters must be a real state code.

    The class 'A' no longer suffices: the machine must see raw letters A-Z.
    """
    letters = [chr(c) for c in range(65, 91)]
    sigma = letters + ["D", "O"]
    delta = {}
    for code in STATE_CODES:
        delta[("r0", code[0])] = f"r_{code[0]}"
        delta[(f"r_{code[0]}", code[1])] = "p2"
    delta[("p2", "D")] = "p3"
    delta[("p3", "D")] = "p4"
    for a in letters:
        delta[("p4", a)] = "p5"
        delta[("p5", a)] = "p6"
        delta[("p6", a)] = "p7"
    for q in ("p5", "p6", "p7"):
        delta[(q, "D")] = "p8"
    delta[("p8", "D")] = "p9"
    delta[("p9", "D")] = "p10"
    delta[("p10", "D")] = "p11"
    states = {q for k, v in delta.items() for q in (k[0], v)}
    d = DFA(states, sigma, delta, "r0", {"p11"}, "plate+codes")
    # BH branch over the raw alphabet, joined by union
    bh = [["D"], ["D"], ["B"], ["H"], ["D"], ["D"], ["D"], ["D"], letters, letters]
    b = chain_dfa("bh", bh, sigma, prefix="b")
    m = union_nfa("u", [d, b]).to_dfa()[0].minimise()
    return len(m.states)


# =====================================================================
# 2. Indian mobile number (OTP login field)
#    optional prefix  +91 | 91 | 0   then [6-9] then 9 more digits
# =====================================================================
MOB_SIGMA = ["P", "Z", "N1", "N9", "M", "R", "O"]
# P='+'  Z='0'  N1='1'  N9='9'  M='6','7','8'  R='2'-'5'  O=other
ANY_DIGIT = ["Z", "N1", "N9", "M", "R"]
FIRST_DIGIT = ["N9", "M"]  # 6, 7, 8, 9


def mobile_classify(c: str) -> str:
    return {"+": "P", "0": "Z", "1": "N1", "9": "N9", "6": "M", "7": "M", "8": "M",
            "2": "R", "3": "R", "4": "R", "5": "R"}.get(c, "O")


def mobile_normalise(s: str) -> str:
    return s.replace(" ", "").replace("-", "")


def build_mobile_nfa() -> NFA:
    d: Dict[tuple, set] = {}

    def add(q, syms, r):
        for a in syms:
            d.setdefault((q, a), set()).add(r)

    add("n0", ["P"], "n1")          # '+'
    add("n1", ["N9"], "n2")         # '+9'
    add("n0", ["N9"], "n2")         # guess: this '9' starts the prefix '91'
    add("n2", ["N1"], "n3")         # prefix '91' complete
    add("n0", ["Z"], "n3")          # prefix '0'
    add("n0", FIRST_DIGIT, "k1")    # guess: no prefix, number starts here
    add("n3", FIRST_DIGIT, "k1")
    for i in range(1, 10):
        add(f"k{i}", ANY_DIGIT, f"k{i + 1}")
    states = {"n0", "n1", "n2", "n3"} | {f"k{i}" for i in range(1, 11)}
    return NFA(states, MOB_SIGMA, d, "n0", {"k10"}, "Mobile number")


def build_mobile() -> Application:
    nfa = build_mobile_nfa()
    subset, subsets = nfa.to_dfa(prefix="d")
    dfa = subset.minimise(prefix="u")
    dfa.name = "Mobile number (minimal DFA)"
    return Application(
        key="mobile",
        title="Mobile number (OTP login)",
        normalise=mobile_normalise,
        classify=mobile_classify,
        dfa=dfa,
        nfa=nfa,
        accepted=["9876543210", "+91 98765 43210", "919876543210", "09876543210",
                  "6000000000", "9198765432"],
        rejected=["5876543210", "987654321", "98765432101", "+9198765432",
                  "+91-58765-43210", "00 9876543210", "98765o4321", ""],
        syntax_only_note="Shape only: whether the SIM is active, and whether the OTP "
                         "typed next matches, needs the telecom/OTP server.",
        extra={"subset": subset, "subsets": subsets},
    )


# =====================================================================
# 3. Date of birth DD/MM/YYYY, years 1900-2099
# =====================================================================
DATE_SIGMA = [str(i) for i in range(10)] + ["/", "O"]
YEARS = range(1900, 2100)


def date_classify(c: str) -> str:
    if c in "0123456789/" and c:
        return c
    return "O"


def date_shape_classify(c: str) -> str:
    if c.isdigit() and c.isascii():
        return "D"
    if c == "/":
        return "S"
    return "O"


def date_shape_dfa() -> DFA:
    D, S = ["D"], ["S"]
    return chain_dfa("Date shape", [D, D, S, D, D, S, D, D, D, D], ["D", "S", "O"], prefix="q")


def _dates(level: str):
    for y in YEARS:
        for m in range(1, 13):
            if level == "ranges":
                last = 31
            elif level == "months":
                last = 29 if m == 2 else calendar.monthrange(2001, m)[1]
            else:  # "leap"
                last = calendar.monthrange(y, m)[1]
            for dd in range(1, last + 1):
                yield f"{dd:02d}/{m:02d}/{y}"


@lru_cache(maxsize=None)
def date_levels():
    """Build the calendar DFA at increasing levels of 'semantics'.

    Returns {level: (number of words, trie states, minimal states, minimal DFA)}.
    """
    out = {}
    for level in ("ranges", "months", "leap"):
        words = list(_dates(level))
        trie = dfa_from_words(f"Date ({level})", words, DATE_SIGMA)
        mini = trie.minimise(prefix="c")
        out[level] = (len(words), len(trie.states), len(mini.states), mini)
    return out


def build_date() -> Application:
    dfa = date_levels()["leap"][3]
    dfa.name = "Date of birth (minimal DFA, full calendar)"
    return Application(
        key="date",
        title="Date of birth DD/MM/YYYY",
        normalise=lambda s: s,
        classify=date_classify,
        dfa=dfa,
        accepted=["11/11/2026", "29/02/2004", "29/02/2000", "31/12/1999",
                  "01/01/1900", "30/04/2006"],
        rejected=["29/02/1900", "29/02/2026", "31/04/2006", "00/01/2005",
                  "15/13/2005", "1/1/2005", "15-08-1947", "15/08/1899"],
        syntax_only_note="The calendar itself is checked by the DFA; 'not in the "
                         "future' or 'age at least 18' needs today's date.",
        extra={"shape": date_shape_dfa()},
    )


@lru_cache(maxsize=None)
def all_applications() -> Dict[str, Application]:
    return {a.key: a for a in (build_plate(), build_mobile(), build_date())}
