#!/usr/bin/env python3
"""
Prueba el magic real del protocolo ARMPRG contra el stick.

Hallazgo de la ingenieria inversa de QMSL_MSVC10R.dll:

  QLIB_DOWNLOAD_Hello construye el paquete asi:

      append("QCOM fast download protocol host", 32)   <- MAGIC
      append_byte(iVersionNumber)
      append_byte(iCompatibleVersion)
      append_byte(iFeatureBits)
      enviar(...)

  El magic es de 32 bytes ASCII, no un numero.

Este script arma ese paquete y lo manda por el puerto serie del modo 0076,
probando varias convenciones de valores para los tres bytes.

Uso:
    python3 hello_magic.py               # prueba variantes
    python3 hello_magic.py --port /dev/ttyUSB0
"""
import os
import select
import sys
import time

MAGIC = b"QCOM fast download protocol host"   # 32 bytes exactos
PORT = "/dev/ttyUSB0"


def frame_hdlc(payload, crc=True):
    """HDLC clasico: 0x7E | esc(payload+crc) | 0x7E."""
    import crcmod
    _crc = crcmod.mkCrcFun(0x11021, rev=True, initCrc=0, xorOut=0xFFFF)

    def esc(b):
        return b.replace(b"\x7d", b"\x7d\x5d").replace(b"\x7e", b"\x7d\x5e")

    body = payload
    if crc:
        import struct
        body += struct.pack("<H", _crc(payload))
    return b"\x7e" + esc(body) + b"\x7e"


def read_for(fd, seconds=0.6):
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
        end = time.time() + 0.25
    return got


def build_variants():
    """Paquetes Hello candidatos: (nombre, bytes)."""
    out = []

    # A) magic solo
    out.append(("magic solo", MAGIC))
    out.append(("magic solo + hdlc", None))

    # B) magic + 3 bytes (version, compatible, features)
    for v, c, f in [(1, 1, 0), (2, 1, 0), (1, 1, 1), (0, 0, 0), (3, 3, 0)]:
        out.append((f"magic + {v},{c},{f}", MAGIC + bytes([v, c, f])))

    # C) magic + dwords (version, compatible, features) little endian
    import struct
    for v, c, f in [(1, 1, 0), (2, 1, 0)]:
        out.append((f"magic + dw {v},{c},{f}",
                    MAGIC + struct.pack("<III", v, c, f)))

    # D) magic + dwords big endian
    for v, c, f in [(1, 1, 0)]:
        out.append((f"magic + dwBE {v},{c},{f}",
                    MAGIC + struct.pack(">III", v, c, f)))

    return out


def main():
    port = PORT
    if "--port" in sys.argv:
        port = sys.argv[sys.argv.index("--port") + 1]

    if not os.path.exists(port):
        print(f"[!] no existe {port}.")
        print("    El stick debe estar en 0076 con ttyUSB expuesto (ver docs/05).")
        return 1

    print(f"[*] puerto: {port}")
    print(f"[*] magic:  {MAGIC!r} ({len(MAGIC)} bytes)\n")

    fd = os.fdopen(os.open(port, os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY), "r+b", buffering=0)
    try:
        junk = read_for(fd, 0.4)
        if junk:
            print(f"[*] residuo previo: {len(junk)} bytes\n")

        variants = build_variants()
        results = []
        for name, payload in variants:
            if payload is None:
                pkt = frame_hdlc(MAGIC)
            else:
                pkt = payload
            try:
                fd.write(pkt)
            except OSError as e:
                print(f"[!] write error: {e}")
                return 1
            got = read_for(fd, 0.7)
            results.append((name, pkt, got))
            status = "SIN RESPUESTA"
            if b"CRC invalid" in got:
                status = "CRC invalid"
            elif b"magic" in got.lower():
                status = f"MAGIC? {got[:50]!r}"
            elif got:
                status = f"RESP {got[:60]!r}"
            print(f"  {name:26s} len={len(pkt):4d} -> {status}")
            time.sleep(0.2)

        print("\n" + "=" * 62)
        ok = [r for r in results if r[2] and b"CRC invalid" not in r[2]]
        if ok:
            print("[+] variantes que NO dieron 'CRC invalid':")
            for name, pkt, got in ok:
                print(f"    {name}: {got[:120]!r}")
        else:
            print("[!] todas dieron CRC invalid o sin respuesta.")
            print("    Ojo: si el stick ya acepto el magic, el rechazo cambia")
            print("    de 'Invalid magic number' a 'CRC invalid'.")
        return 0
    finally:
        fd.close()


if __name__ == "__main__":
    sys.exit(main())
