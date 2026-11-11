"""Command-line demo.

  python -m fa_lab.cli                       accept/reject table for every application
  python -m fa_lab.cli mobile 919876543210   one string, full transition trace
  python -m fa_lab.cli --stats               state counts for every design
"""

import argparse
import sys

from .validators import all_applications, date_levels, plate_with_state_codes_size

GREEN, RED, BOLD, DIM, END = "\033[32m", "\033[31m", "\033[1m", "\033[2m", "\033[0m"


def verdict(ok: bool, colour: bool) -> str:
    word = "ACCEPT" if ok else "REJECT"
    return (GREEN if ok else RED) + word + END if colour else word


def table(colour: bool) -> None:
    for app in all_applications().values():
        print(f"{BOLD if colour else ''}{app.title}{END if colour else ''}  "
              f"({len(app.dfa.states)}-state minimal DFA)")
        for s in app.accepted + app.rejected:
            print(f"   {repr(s):24} {verdict(app.check(s), colour)}")
        print()


def trace(key: str, text: str, colour: bool) -> None:
    app = all_applications()[key]
    steps, ok = app.trace(text)
    print(f"{BOLD if colour else ''}{app.title} (minimal DFA){END if colour else ''} on {text!r}")
    if app.normalise(text) != text:
        print(f"   lexer: {text!r} -> {app.normalise(text)!r}")
    for st in steps:
        print(f"   {st.index:2}. δ({st.src}, {st.char!r} -> {st.symbol}) = {st.dst}")
    final = steps[-1].dst if steps else app.dfa.start
    print(f"   final state {final} -> {verdict(ok, colour)}")


def stats() -> None:
    apps = all_applications()
    p, m = apps["plate"], apps["mobile"]
    a, b = p.extra["parts"]
    print("Vehicle plate")
    print(f"   state-series DFA {len(a.states)}, BH-series DFA {len(b.states)}, "
          f"union NFA {len(p.nfa.states)}, subset DFA {len(p.extra['subset'].states)}, "
          f"minimal {len(p.dfa.states)}")
    print(f"   with the 37 real state/UT codes (raw letters): minimal {plate_with_state_codes_size()}")
    print("Mobile number")
    print(f"   NFA {len(m.nfa.states)}, subset DFA {len(m.extra['subset'].states)}, minimal {len(m.dfa.states)}")
    print("Date of birth (years 1900-2099)")
    print(f"   shape only DD/MM/YYYY over {{D, S, O}}: {len(apps['date'].extra['shape'].states)}")
    for lv, (words, trie, mini, _) in date_levels().items():
        print(f"   {lv:7}: {words:6} valid strings, trie {trie:6} states, minimal {mini}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("app", nargs="?", choices=["plate", "mobile", "date"])
    ap.add_argument("text", nargs="?")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--no-colour", action="store_true")
    args = ap.parse_args(argv)
    colour = sys.stdout.isatty() and not args.no_colour
    if args.stats:
        stats()
    elif args.app and args.text is not None:
        trace(args.app, args.text, colour)
    else:
        table(colour)
    return 0


if __name__ == "__main__":
    sys.exit(main())
