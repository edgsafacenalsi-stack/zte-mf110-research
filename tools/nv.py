#!/usr/bin/env python3
"""
Volcado y lectura de NV items por DIAG.

Uso:
    python3 nv.py dump 0 999 salida.json
    python3 nv.py read 5000
    python3 nv.py write 5000 datos.hex
"""
import json
import sys

from diag import Diag


def dump(start, end, path, delay=0.02):
    import time
    d = Diag().open()
    out = {}
    try:
        d.spc()
        for item in range(start, end + 1):
            try:
                data = d.nv_read(item)
            except Exception:
                data = None
            if data:
                out[str(item)] = data.hex()
            if item % 100 == 0:
                print(f"  {item}/{end}", file=sys.stderr)
            time.sleep(delay)
    finally:
        d.close()
    with open(path, "w") as f:
        json.dump(out, f)
    print(f"{len(out)} items → {path}")
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    mode = sys.argv[1]

    if mode == "dump":
        start, end, path = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
        dump(start, end, path)
        return 0

    if mode == "read":
        item = int(sys.argv[2])
        d = Diag().open()
        try:
            d.spc()
            data = d.nv_read(item)
            print(f"NV {item}: {data.hex() if data else 'sin respuesta'}")
        finally:
            d.close()
        return 0

    if mode == "write":
        item = int(sys.argv[2])
        data = bytes.fromhex(open(sys.argv[3]).read().strip())
        d = Diag().open()
        try:
            d.spc()
            r = d.nv_write(item, data)
            print(f"escrito: {r.hex() if r else 'sin respuesta'}")
        finally:
            d.close()
        return 0

    print(f"[!] modo desconocido: {mode}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
