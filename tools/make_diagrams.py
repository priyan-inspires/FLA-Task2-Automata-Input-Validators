"""Rebuild every diagram (docs/diagrams) and the browser demo data (docs/automata.json).

Needs Graphviz (`dot`) on PATH.   Run:  python tools/make_diagrams.py
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fa_lab.labels import date_label, mobile_label, plate_label  # noqa: E402
from fa_lab.validators import all_applications  # noqa: E402

OUT = ROOT / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)


def render(name: str, dot: str) -> None:
    (OUT / f"{name}.dot").write_text(dot, encoding="utf-8")
    for fmt in ("svg", "png"):
        args = ["dot", f"-T{fmt}", str(OUT / f"{name}.dot"), "-o", str(OUT / f"{name}.{fmt}")]
        if fmt == "png":
            args.insert(1, "-Gdpi=200")
        subprocess.run(args, check=True)


def main() -> None:
    apps = all_applications()
    plate, mobile, date = apps["plate"], apps["mobile"], apps["date"]

    state_part, bh_part = plate.extra["parts"]
    render("plate_state_series", state_part.to_dot(label_fn=plate_label))
    render("plate_bh_series", bh_part.to_dot(label_fn=plate_label))
    render("plate_union_nfa", plate.nfa.to_dot(label_fn=plate_label, graph_attrs="nodesep=0.25; ranksep=0.35;"))
    render("plate_dfa", plate.dfa.to_dot(label_fn=plate_label, graph_attrs="nodesep=0.3; ranksep=0.3;"))

    render("mobile_nfa", mobile.nfa.to_dot(label_fn=mobile_label, graph_attrs="nodesep=0.3; ranksep=0.32;"))
    render("mobile_dfa", mobile.dfa.to_dot(label_fn=mobile_label, graph_attrs="nodesep=0.22; ranksep=0.3;"))

    render("date_shape", date.extra["shape"].to_dot(label_fn=lambda s: ", ".join(s)))
    render("date_calendar_dfa", date.dfa.to_dot(label_fn=date_label,
                                                graph_attrs="nodesep=0.18; ranksep=0.42;"))

    # ---- browser demo data -------------------------------------------------
    demo = {}
    diagrams = {"plate": "plate_dfa", "mobile": "mobile_dfa", "date": "date_calendar_dfa"}
    for key, app in apps.items():
        d = app.dfa
        demo[key] = {
            "title": app.title,
            "start": d.start,
            "accept": sorted(d.accept),
            "delta": {f"{q}|{a}": r for (q, a), r in d.delta.items()},
            "svg": (OUT / f"{diagrams[key]}.svg").read_text(encoding="utf-8"),
            "accepted": app.accepted,
            "rejected": app.rejected,
            "states": len(d.states),
            "note": app.syntax_only_note,
        }
    (ROOT / "docs" / "automata.json").write_text(json.dumps(demo), encoding="utf-8")
    template = (ROOT / "tools" / "demo_template.html").read_text(encoding="utf-8")
    (ROOT / "docs" / "index.html").write_text(template.replace("/*__DATA__*/null", json.dumps(demo)),
                                            encoding="utf-8")
    print("diagrams and docs/index.html rebuilt")


if __name__ == "__main__":
    main()
