#!/usr/bin/env python3
"""
Prueba variantes de CRC y framing con el magic CORRECTO de QPST.

Contexto: con el magic equivocado (9a1b7daa) el ARMPRG respondia
"Invalid magic number". Con el magic real:

    "QCOM fast download protocol host"   (32 bytes)

el error cambia a "ERR: CRC invalid". Eso confirma que el magic es
correcto y que el rechazo ahora es por el checksum.

Este script prueba sistematicamente:

  - 21 variantes de CRC16 (polinomios, init, xorout, endianness)
  - framing con y sin 0x7E
  - con y sin los 3 bytes de version despues del magic
  - crc sobre distintas porciones

Uso:
    python3 hello_crc.py                # barrido completo
    python3 hello_crc.py --quick        # solo las mas probables
"""
import os
import select
import struct
import sys
import time

MAGIC = b"QCOM fast download protocol host"
PORT = "/dev/ttyUSB0"


def read_for(fd, seconds=0.5):
    got = b""
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.08)
        if not r:
            continue
        try:
            chunk = os.read(fd.fileno(), 4096)
        except OSError:
            break
        if not chunk:
            break
        got += chunk
        end = time.time() + 0.2
    return got


def esc(b):
    return b.replace(b"\x7d", b"\x7d\x5d").replace(b"\x7e", b"\x7d\x5e")


def crc_variants(data):
    import crcmod
    out = []

    def add(name, poly, rev, init, xo):
        try:
            f = crcmod.mkCrcFun(poly, rev=rev, initCrc=init, xorOut=xo)
            v = f(data)
        except Exception:
            return
        out.append((name + "/le", struct.pack("<H", v)))
        out.append((name + "/be", struct.pack(">H", v)))

    add("ccitt-false", 0x11021, False, 0xFFFF, 0x0000)
    add("xmodem", 0x11021, False, 0x0000, 0x0000)
    add("kermit", 0x11021, True, 0x0000, 0x0000)
    add("kermit-ffff", 0x11021, True, 0xFFFF, 0xFFFF)
    add("x25", 0x11021, True, 0xFFFF, 0xFFFF)
    add("ibm", 0x18005, True, 0x0000, 0x0000)
    add("modbus", 0x18005, True, 0xFFFF, 0x0000)
    add("arc", 0x18005, True, 0x0000, 0x0000)

    # sumas simples
    out.append(("sum16/le", struct.pack("<H", sum(data) & 0xFFFF)))
    out.append(("sum16/be", struct.pack(">H", sum(data) & 0xFFFF)))
    out.append(("nocrc", b""))
    return out


def build_payloads():
    """Payloads base: (nombre, bytes_sin_crc)."""
    out = [
        ("magic", MAGIC),
        ("magic+3bytes 1,1,0", MAGIC + bytes([1, 1, 0])),
        ("magic+3bytes 2,1,0", MAGIC + bytes([2, 1, 0])),
        ("magic+3bytes 0,0,0", MAGIC + bytes([0, 0, 0])),
        ("magic+dw 1,1,0", MAGIC + struct.pack("<III", 1, 1, 0)),
        ("magic+len32", MAGIC + struct.pack("<I", 32)),
    ]
    return out


def main():
    quick = "--quick" in sys.argv
    port = PORT
    if "--port" in sys.argv:
        port = sys.argv[sys.argv.index("--port") + 1]

    if not os.path.exists(port):
        print(f"[!] no existe {port} (necesita 0076 con ttyUSB)")
        return 1

    payloads = build_payloads()
    if quick:
        payloads = payloads[:2]

    fd = os.fdopen(os.open(port, os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY),
                   "r+b", buffering=0)
    try:
        read_for(fd, 0.4)
        total = 0
        hits = []

        for pname, base in payloads:
            variants = crc_variants(base)
            if quick:
                variants = [v for v in variants
                            if v[0].startswith(("ccitt", "xmodem", "kermit/", "nocrc"))]
            print(f"\n--- payload: {pname} ({len(base)} bytes) ---")
            for cname, crc in variants:
                body = base + crc
                for fname, framed in [
                    ("raw", body),
                    ("hdlc", b"\x7e" + esc(body) + b"\x7e"),
                ]:
                    try:
                        fd.write(framed)
                    except OSError as e:
                        print(f"  [!] write: {e}")
                        return 1
                    got = read_for(fd, 0.45)
                    total += 1
                    if got and b"CRC invalid" not in got:
                        hits.append((pname, cname, fname, framed, got))
                        status = f"*** {got[:70]!r}"
                    elif b"CRC invalid" in got:
                        status = "CRC invalid"
                    else:
                        status = "-"
                    print(f"  {cname:20s} {fname:5s} -> {status}")
                    time.sleep(0.1)

        print("\n" + "=" * 64)
        print(f"pruebas: {total}")
        if hits:
            print(f"[+] {len(hits)} SIN 'CRC invalid':")
            for pname, cname, fname, framed, got in hits:
                print(f"    {pname} / {cname} / {fname}")
                print(f"      enviado: {framed[:44].hex()}...")
                print(f"      resp:    {got[:100]!r}")
        else:
            print("[!] todas dieron CRC invalid o silencio.")
        return 0
    finally:
        fd.close()


if __name__ == "__main__":
    sys.exit(main())
