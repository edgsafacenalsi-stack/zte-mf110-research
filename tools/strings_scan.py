#!/usr/bin/env python3
"""
Lista los strings de un binario con su offset.

Útil para localizar mensajes de error de un firmware y de ahí
encontrar las funciones que los usan.

Uso:
    python3 strings_scan.py <archivo> [min_len]
    python3 strings_scan.py <archivo> [min_len] --filter texto
"""
import re
import sys


def scan(path, min_len=5, filtro=None):
    d = open(path, "rb").read()
    pat = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
    out = []
    for m in pat.finditer(d):
        s = m.group().decode("latin1")
        if filtro and filtro.lower() not in s.lower():
            continue
        out.append((m.start(), s))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    min_len = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    filtro = None
    if "--filter" in sys.argv:
        filtro = sys.argv[sys.argv.index("--filter") + 1]

    for off, s in scan(path, min_len, filtro):
        print(f"{off:06x}  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
