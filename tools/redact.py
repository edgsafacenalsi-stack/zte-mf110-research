#!/usr/bin/env python3
"""
Redacta identificadores personales de un archivo JSON de volcado NV.

Reemplaza IMEI y serial USB por placeholders. El volcado NV los contiene
codificados en BCD, así que hay que buscarlos en hex y en ASCII.

Uso:
    python3 redact.py entrada.json salida.json --imei 351790031234567 --serial P671A2EXAMPLE0000
"""
import json
import sys


def bcd(dec: str) -> bytes:
    """IMEI en BCD empaquetado (el orden que usa el firmware)."""
    out = bytearray()
    for i in range(0, len(dec) - 1, 2):
        out.append(int(dec[i + 1]) << 4 | int(dec[i]))
    return bytes(out)


def bcd_alt(dec: str) -> bytes:
    """Variante con nibbles invertidos."""
    out = bytearray()
    for i in range(0, len(dec) - 1, 2):
        out.append(int(dec[i]) << 4 | int(dec[i + 1]))
    return bytes(out)


def variants(imei, serial):
    """Todas las representaciones a buscar, con su reemplazo."""
    pairs = []

    if imei:
        for blob in (bcd(imei), bcd_alt(imei)):
            pairs.append((blob, b"\xff" * len(blob)))
        pairs.append((imei.encode(), b"X" * len(imei)))
        pairs.append((imei.encode("utf-16-le"), b"X\0" * len(imei)))

    if serial:
        b = serial.encode()
        pairs.append((b, b"P671A2" + b"X" * (len(b) - 6)))
        pairs.append((b, b"Z" * len(b)))

    return pairs


def redact_text(s, pairs):
    for old, new in pairs:
        if not old:
            continue
        s = s.replace(old.hex(), new.hex())
        s = s.replace(old.hex().upper(), new.hex().upper())
        try:
            s = s.replace(old.decode("latin1"), new.decode("latin1"))
        except Exception:
            pass
    return s


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    src, dst = sys.argv[1], sys.argv[2]
    imei = serial = None
    a = sys.argv
    if "--imei" in a:
        imei = a[a.index("--imei") + 1]
    if "--serial" in a:
        serial = a[a.index("--serial") + 1]

    pairs = variants(imei, serial)
    data = json.load(open(src))

    n = 0
    for k, v in data.items():
        nv = redact_text(str(v), pairs)
        if nv != v:
            n += 1
        data[k] = nv

    json.dump(data, open(dst, "w"))
    print(f"{len(data)} items, {n} redactados → {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
