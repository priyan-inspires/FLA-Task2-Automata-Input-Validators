"""A small finite-automata toolkit written for 21CSC301T (FLA), CLA-2 Task 2.

It provides
  * DFA  - run with a trace, complete with a trap state, trim, minimise (Moore)
  * NFA  - epsilon moves, subset construction
  * helpers - DFA from a finite word list (trie), union of DFAs, Graphviz export

Symbols are short strings (e.g. "D" for digit). Each application supplies a
classifier that maps a raw character to one symbol, so diagrams stay small.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, Hashable, Iterable, List, Optional, Set, Tuple

State = Hashable
TRAP = "qT"
EPS = "ε"


@dataclass
class Step:
    index: int
    char: str
    symbol: str
    src: State
    dst: State


@dataclass
class DFA:
    states: Set[State]
    alphabet: List[str]
    delta: Dict[Tuple[State, str], State]
    start: State
    accept: Set[State]
    name: str = "DFA"
    labels: Dict[State, str] = field(default_factory=dict)

    # ------------------------------------------------------------ running
    def step(self, q: State, sym: str) -> State:
        return self.delta.get((q, sym), TRAP)

    def run(self, symbols: Iterable[str]) -> State:
        q = self.start
        for s in symbols:
            q = self.step(q, s)
            if q == TRAP:
                return TRAP
        return q

    def accepts(self, symbols: Iterable[str]) -> bool:
        return self.run(symbols) in self.accept

    def trace(self, text: str, classify: Callable[[str], str]) -> Tuple[List[Step], bool]:
        steps, q = [], self.start
        for i, ch in enumerate(text, 1):
            sym = classify(ch)
            nq = self.step(q, sym) if q != TRAP else TRAP
            steps.append(Step(i, ch, sym, q, nq))
            q = nq
        return steps, q in self.accept

    # ------------------------------------------------------------ structure
    def live_states(self) -> Set[State]:
        return {q for q in self.states if q != TRAP}

    def reachable(self) -> Set[State]:
        seen, todo = {self.start}, deque([self.start])
        while todo:
            q = todo.popleft()
            for a in self.alphabet:
                r = self.delta.get((q, a))
                if r is not None and r not in seen:
                    seen.add(r)
                    todo.append(r)
        return seen

    def trim(self) -> "DFA":
        """Keep states that are reachable AND can still reach acceptance."""
        reach = self.reachable()
        rev: Dict[State, Set[State]] = {}
        for (q, _a), r in self.delta.items():
            rev.setdefault(r, set()).add(q)
        co, todo = set(self.accept & reach), deque(self.accept & reach)
        while todo:
            q = todo.popleft()
            for p in rev.get(q, ()):
                if p not in co:
                    co.add(p)
                    todo.append(p)
        keep = reach & co
        delta = {(q, a): r for (q, a), r in self.delta.items() if q in keep and r in keep}
        return DFA(keep, self.alphabet, delta, self.start, self.accept & keep, self.name,
                   {q: l for q, l in self.labels.items() if q in keep})

    def minimise(self, prefix: str = "m") -> "DFA":
        """Moore partition refinement on the trimmed machine.

        Missing transitions mean 'go to the trap state', so the trap is the
        implicit extra block and never needs to be stored.
        """
        d = self.trim()
        if not d.states:
            return DFA(set(), self.alphabet, {}, TRAP, set(), self.name)
        block = {q: (q in d.accept) for q in d.states}
        n_blocks = len(set(block.values()))
        while True:
            sig = {q: (block[q],) + tuple(block.get(d.delta.get((q, a)), None) for a in d.alphabet)
                   for q in d.states}
            ids: Dict[tuple, int] = {}
            new = {q: ids.setdefault(sig[q], len(ids)) for q in sorted(d.states, key=_order_key)}
            if len(ids) == n_blocks:
                block = new
                break
            block, n_blocks = new, len(ids)
        # renumber blocks in BFS order from the start, so names are stable
        order: Dict[int, str] = {}
        todo = deque([d.start])
        seen = {d.start}
        while todo:
            q = todo.popleft()
            order.setdefault(block[q], f"{prefix}{len(order)}")
            for a in d.alphabet:
                r = d.delta.get((q, a))
                if r is not None and r not in seen:
                    seen.add(r)
                    todo.append(r)
        name = {q: order[block[q]] for q in d.states}
        delta = {(name[q], a): name[r] for (q, a), r in d.delta.items()}
        return DFA(set(name.values()), d.alphabet, delta, name[d.start],
                   {name[q] for q in d.accept}, self.name)

    # ------------------------------------------------------------ output
    def to_dot(self, rankdir: str = "LR", label_fn: Optional[Callable[[List[str]], str]] = None,
               graph_attrs: str = "") -> str:
        label_fn = label_fn or (lambda syms: ", ".join(syms))
        edges: Dict[Tuple[State, State], List[str]] = {}
        for (q, a), r in sorted(self.delta.items(), key=lambda kv: (_order_key(kv[0][0]), kv[0][1])):
            edges.setdefault((q, r), []).append(a)
        out = [f'digraph "{self.name}" {{', f"  rankdir={rankdir};",
               '  node [shape=circle fontname="DejaVu Sans" fontsize=11 width=0.45 fixedsize=false];',
               '  edge [fontname="DejaVu Sans" fontsize=9 arrowsize=0.7];',
               '  __start [shape=point width=0.07];']
        if graph_attrs:
            out.insert(2, "  " + graph_attrs)
        for q in sorted(self.states, key=_order_key):
            shape = "doublecircle" if q in self.accept else "circle"
            label = self.labels.get(q, str(q))
            out.append(f'  "{q}" [id="{q}" shape={shape} label="{label}"];')
        out.append(f'  __start -> "{self.start}";')
        for (q, r), syms in edges.items():
            out.append(f'  "{q}" -> "{r}" [label="{label_fn(syms)}"];')
        out.append("}")
        return "\n".join(out)


@dataclass
class NFA:
    states: Set[State]
    alphabet: List[str]
    delta: Dict[Tuple[State, str], Set[State]]  # symbol may be EPS
    start: State
    accept: Set[State]
    name: str = "NFA"

    def closure(self, qs: Iterable[State]) -> FrozenSet[State]:
        seen, todo = set(qs), list(qs)
        while todo:
            q = todo.pop()
            for r in self.delta.get((q, EPS), ()):
                if r not in seen:
                    seen.add(r)
                    todo.append(r)
        return frozenset(seen)

    def move(self, qs: Iterable[State], sym: str) -> FrozenSet[State]:
        out: Set[State] = set()
        for q in qs:
            out |= self.delta.get((q, sym), set())
        return self.closure(out)

    def accepts(self, symbols: Iterable[str]) -> bool:
        cur = self.closure([self.start])
        for s in symbols:
            cur = self.move(cur, s)
            if not cur:
                return False
        return bool(cur & self.accept)

    def to_dfa(self, prefix: str = "d") -> Tuple[DFA, Dict[str, FrozenSet[State]]]:
        """Subset construction. Returns the DFA and the subset behind each state."""
        s0 = self.closure([self.start])
        names = {s0: f"{prefix}0"}
        todo, delta = deque([s0]), {}
        while todo:
            S = todo.popleft()
            for a in self.alphabet:
                T = self.move(S, a)
                if not T:
                    continue  # empty subset = trap
                if T not in names:
                    names[T] = f"{prefix}{len(names)}"
                    todo.append(T)
                delta[(names[S], a)] = names[T]
        accept = {n for S, n in names.items() if S & self.accept}
        dfa = DFA(set(names.values()), self.alphabet, delta, names[s0], accept, self.name + " (subset)")
        return dfa, {n: S for S, n in names.items()}

    def to_dot(self, rankdir: str = "LR", label_fn: Optional[Callable[[List[str]], str]] = None,
               graph_attrs: str = "") -> str:
        label_fn = label_fn or (lambda syms: ", ".join(sorted(syms)))
        edges: Dict[Tuple[State, State], List[str]] = {}
        for (q, a), rs in self.delta.items():
            for r in rs:
                edges.setdefault((q, r), []).append(a)
        out = [f'digraph "{self.name}" {{', f"  rankdir={rankdir};",
               '  node [shape=circle fontname="DejaVu Sans" fontsize=11 width=0.45];',
               '  edge [fontname="DejaVu Sans" fontsize=9 arrowsize=0.7];',
               '  __start [shape=point width=0.07];']
        if graph_attrs:
            out.insert(2, "  " + graph_attrs)
        for q in sorted(self.states, key=_order_key):
            shape = "doublecircle" if q in self.accept else "circle"
            out.append(f'  "{q}" [id="{q}" shape={shape}];')
        out.append(f'  __start -> "{self.start}";')
        for (q, r), syms in sorted(edges.items(), key=lambda kv: (_order_key(kv[0][0]), _order_key(kv[0][1]))):
            style = ' style=dashed' if syms == [EPS] else ''
            lab = EPS if syms == [EPS] else label_fn(syms)
            out.append(f'  "{q}" -> "{r}" [label="{lab}"{style}];')
        out.append("}")
        return "\n".join(out)


# ---------------------------------------------------------------- helpers
def chain_dfa(name: str, pattern: List[List[str]], alphabet: List[str], prefix: str = "q") -> DFA:
    """DFA for a fixed-length pattern: pattern[i] = symbols allowed at position i."""
    states = {f"{prefix}{i}" for i in range(len(pattern) + 1)}
    delta = {}
    for i, allowed in enumerate(pattern):
        for a in allowed:
            delta[(f"{prefix}{i}", a)] = f"{prefix}{i + 1}"
    return DFA(states, alphabet, delta, f"{prefix}0", {f"{prefix}{len(pattern)}"}, name)


def dfa_from_words(name: str, words: Iterable[str], alphabet: List[str]) -> DFA:
    """Trie of a finite language: the most direct (and largest) DFA for it."""
    delta: Dict[Tuple[int, str], int] = {}
    accept: Set[int] = set()
    n = 1
    for w in words:
        q = 0
        for ch in w:
            nxt = delta.get((q, ch))
            if nxt is None:
                nxt = n
                n += 1
                delta[(q, ch)] = nxt
            q = nxt
        accept.add(q)
    return DFA(set(range(n)), alphabet, delta, 0, accept, name)


def union_nfa(name: str, parts: List[DFA], start: str = "s") -> NFA:
    """Thompson-style union: a new start with an ε-move into every part."""
    alphabet = sorted({a for p in parts for a in p.alphabet})
    delta: Dict[Tuple[State, str], Set[State]] = {(start, EPS): set()}
    states: Set[State] = {start}
    accept: Set[State] = set()
    for p in parts:
        states |= p.states
        accept |= p.accept
        delta[(start, EPS)].add(p.start)
        for (q, a), r in p.delta.items():
            delta.setdefault((q, a), set()).add(r)
    return NFA(states, alphabet, delta, start, accept, name)


def _order_key(q: State):
    s = str(q)
    head = s.rstrip("0123456789")
    tail = s[len(head):]
    return (head, int(tail) if tail else -1)
