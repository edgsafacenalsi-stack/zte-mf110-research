#!/usr/bin/env python3
"""
Descubre que CRC espera el bootloader 0076.

Contexto: en el modo 0076, escribiendo por /dev/ttyUSB0 (driver 'option'),
el bootloader responde en texto plano cuando el CRC es incorrecto:

    <hdr 2 bytes> 7e 7e 0e "ERR: CRC invalid\n" <crc 2 bytes> 7e 7e

Nunca responde "OK", asi que probamos variantes de CRC y de framing hasta
encontrar una que NO produzca "CRC invalid".

Seguro: solo comando 0 (el mas inofensivo), un intento por variante,
con pausa. Cualquier cosa rara -> parar y reconectar.
"""
import os
import os
import sys
import time
import select
import struct

PORT = "/dev/ttyUSB0"


def crc_variants(data):
    """Devuelve lista de (nombre, bytes_crc)."""
    out = []

    def add_crcmod(name, poly, rev, init, xo):
        import crcmod
        f = crcmod.mkCrcFun(poly, rev=rev, initCrc=init, xorOut=xo)
        v = f(data)
        out.append((name + "/le", struct.pack("<H", v)))
        out.append((name + "/be", struct.pack(">H", v)))

    add_crcmod("ccitt-false", 0x11021, False, 0xFFFF, 0x0000)
    add_crcmod("xmodem", 0x11021, False, 0x0000, 0x0000)
    add_crcmod("kermit", 0x11021, True, 0x0000, 0x0000)
    add_crcmod("kermit-ffff", 0x11021, True, 0xFFFF, 0xFFFF)
    add_crcmod("ibm", 0x18005, True, 0x0000, 0x0000)
    add_crcmod("ibm-init-ffff", 0x18005, True, 0xFFFF, 0x0000)
    add_crcmod("crc16/arc", 0x18005, True, 0x0000, 0x0000)
    add_crcmod("modbus", 0x18005, True, 0xFFFF, 0x0000)
    add_crcmod("x25", 0x11021, True, 0xFFFF, 0xFFFF)
    # suma simple
    out.append(("sum8", bytes([sum(data) & 0xFF])))
    out.append(("xor8", bytes([__import__("functools").reduce(lambda a, b: a ^ b, data, 0)])))
    out.append(("none", b""))
    return out


def esc(b):
    return b.replace(b"\x7d", b"\x7d\x5d").replace(b"\x7e", b"\x7d\x5e")


def read_for(fd, seconds=1.0):
    got = b""
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try:
                d = os.read(fd.fileno(), 4096)
            except Exception:
                break
            if not d:
                break
            got += d
            end = time.time() + 0.25
    return got


def main():
    if not os.path.exists(PORT):
        print(f"[!] no existe {PORT}. El stick debe estar en 0076 con tty.")
        return 1

    fd = os.fdopen(os.open(PORT, os.O_RDWR | os.O_NONBLOCK), "r+b", buffering=0)
    try:
        # limpiar lo pendiente
        junk = read_for(fd, 0.5)
        if junk:
            print(f"[*] cola previa: {len(junk)} bytes")

        payload = bytes([0x00])
        variants = crc_variants(payload)
        print(f"[*] {len(variants)} variantes de CRC para payload {payload.hex()}\n")

        results = []
        for name, c in variants:
            for frame, fname in [
                (b"\x7e" + esc(payload + c) + b"\x7e", "hdlc"),
                (esc(payload + c), "rawesc"),
            ]:
                try:
                    fd.write(frame)
                except Exception as e:
                    print(f"[!] write error en {name}/{fname}: {e}")
                    return 1
                got = read_for(fd, 0.45)
                results.append((name, fname, frame, got))
                status = "SIN RESPUESTA"
                if b"CRC invalid" in got:
                    status = "CRC invalid"
                elif got:
                    status = f"RESP: {got[:40].hex()}"
                print(f"{name:22s} {fname:8s} {frame.hex():28s} -> {status}")
                time.sleep(0.15)

        print("\n================ ================")
        ok = [r for r in results if r[3] and b"CRC invalid" not in r[3]]
        if ok:
            print(f"[+] {len(ok)} variantes SIN 'CRC invalid':")
            for name, fname, frame, got in ok:
                print(f"    {name}/{fname}: {frame.hex()} -> {got[:60].hex()}")
        else:
            print("[!] todas dieron CRC invalid. El CRC es otro.")
        return 0
    finally:
        os.close(fd)


if __name__ == "__main__":
    sys.exit(main())
