"""Readable edge labels for diagrams: turn a list of symbols into '0-2, 9' style text."""

from typing import Iterable, List

MOBILE_CHARS = {"P": "+", "Z": "0", "N1": "1", "N9": "9", "M": "678", "R": "2345", "O": ""}


def compress_digits(chars: Iterable[str]) -> str:
    digits = sorted({c for c in chars if c.isdigit()})
    others = sorted({c for c in chars if not c.isdigit()})
    parts: List[str] = []
    i = 0
    while i < len(digits):
        j = i
        while j + 1 < len(digits) and int(digits[j + 1]) == int(digits[j]) + 1:
            j += 1
        if j == i:
            parts.append(digits[i])
        elif j == i + 1:
            parts += [digits[i], digits[j]]
        else:
            parts.append(f"{digits[i]}-{digits[j]}")
        i = j + 1
    if parts == ["0-9"]:
        parts = ["D"]
    return ", ".join(others + parts)


def plate_label(syms: List[str]) -> str:
    s = set(syms)
    out = []
    if {"A", "B", "H"} <= s:
        out.append("L")
        s -= {"A", "B", "H"}
    out += [x for x in ["A", "B", "H", "D", "O"] if x in s]
    return ", ".join(out)


def mobile_label(syms: List[str]) -> str:
    return compress_digits("".join(MOBILE_CHARS[s] for s in syms))


def date_label(syms: List[str]) -> str:
    return compress_digits(syms)
