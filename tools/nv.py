#!/usr/bin/env python3
"""
Volcado y lectura de NV items por DIAG.

ADVERTENCIA: la lectura NV de `diag.py` es intermitente (ver su docstring).
Este script reintenta varias veces, pero un volcado completo del rango
0-999 puede tardar y dejar huecos. El volcado publicado en
research/nv_mf110_0_999.json se hizo con un cliente más tolerante.

Si lo usás para volcar, revisá cuántos items quedaron vacíos.

Uso:
    python3 nv.py dump 0 999 salida.json
    python3 nv.py read 5000
"""
import json
import sys
import time

from diag import Diag


def dump(start, end, path, delay=0.05, retries=2):
    d = Diag().open()
    out = {}
    missing = []
    try:
        d.spc()
        for item in range(start, end + 1):
            for _ in range(retries):
                data = d.nv_read(item)
                if data and len(data) >= 128:
                    break
                time.sleep(0.1)
            if data and len(data) >= 128:
                out[str(item)] = data.hex()
            else:
                missing.append(item)
            if item % 100 == 0:
                print(f"  {item}/{end}  ({len(out)} ok, {len(missing)} fallidos)",
                      file=sys.stderr)
            time.sleep(delay)
    finally:
        d.close()

    with open(path, "w") as f:
        json.dump(out, f)
    print(f"{len(out)} items → {path}")
    if missing:
        print(f"⚠ {len(missing)} items sin respuesta: {missing[:20]}...")
        print("  Ver la advertencia en el docstring de nv.py")
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
            data = None
            for _ in range(3):
                data = d.nv_read(item)
                if data:
                    break
                time.sleep(0.2)
            if data:
                print(f"NV {item} ({len(data)} bytes): {data.hex()}")
            else:
                print(f"NV {item}: sin respuesta")
        finally:
            d.close()
        return 0

    print(f"[!] modo desconocido: {mode}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
