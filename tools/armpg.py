#!/usr/bin/env python3
"""
Cliente del protocolo de download Qualcomm (ARMPRG) para el MF110.

Reconstruido a partir de:
  - jcsullins/qdloader  (implementacion de referencia en Perl)
  - el firmware del stick (nandprgcombined.mbn, ARMPRG v14.00.00)
  - QMSL_MSVC10R.dll    (API de QPST, 1949 exports con nombre)

Framing:
    0x7E | escape(payload + CRC16_BE) | 0x7E
    escape: 0x7E -> 0x7D 0x5E ,  0x7D -> 0x7D 0x5D

CRC:
    CRC-16 CCITT reflejado, init=0x0000, xorOut=0xFFFF, luego swap16.
    Verificado contra la implementacion Perl: 0x995C para el magic.

Magic:
    host envia:   01 "QCOM fast download protocol host" 03 03 09
    target responde: 02 "QCOM fast download protocol targ"

Comandos conocidos:
    0x01  HELLO        (magic + version + compatible + featureBits)
    0x02  respuesta OK (del target)
    0x03  ...
    0x0D  ERROR
    0x0E  mensaje de texto
    0x0F  WRITE        (addr32 + len16 + datos)

Uso:
    python3 armpg.py probe                    # handshake
    python3 armpg.py version                  # pedir version del target
    python3 armpg.py write <addr> <archivo>   # escribir (PELIGROSO)
"""
import os
import select
import struct
import sys
import time

import crcmod

MAGIC_HOST = b"QCOM fast download protocol host"
MAGIC_TARG = b"QCOM fast download protocol targ"
PORT = "/dev/ttyUSB0"

VERSION = 0x03
COMPATIBLE = 0x03
FEATURE_BITS = 0x09

_crc = crcmod.mkCrcFun(0x11021, rev=True, initCrc=0x0000, xorOut=0xFFFF)


def swap16(v):
    return ((v << 8) | (v >> 8)) & 0xFFFF


def crc16(payload):
    return swap16(_crc(payload))


def escape(b):
    return b.replace(b"\x7d", b"\x7d\x5d").replace(b"\x7e", b"\x7d\x5e")


def unescape(b):
    out = bytearray()
    i = 0
    while i < len(b):
        if b[i] == 0x7D and i + 1 < len(b):
            out.append(b[i + 1] ^ 0x20)
            i += 2
        else:
            out.append(b[i])
            i += 1
    return bytes(out)


def packet(payload):
    c = crc16(payload)
    body = payload + struct.pack(">H", c)
    return b"\x7e" + escape(body) + b"\x7e"


class Armpg:
    def __init__(self, port=PORT, debug=False):
        self.port = port
        self.debug = debug
        self.fd = None

    def open(self):
        self.fd = os.fdopen(
            os.open(self.port, os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY),
            "r+b", buffering=0)
        # limpiar
        self._read(0.3)
        return self

    def close(self):
        if self.fd:
            self.fd.close()
            self.fd = None

    def _read(self, seconds=1.0):
        got = b""
        end = time.time() + seconds
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.08)
            if not r:
                continue
            try:
                chunk = os.read(self.fd.fileno(), 4096)
            except OSError:
                break
            if not chunk:
                break
            got += chunk
            end = time.time() + 0.35
        return got

    def send(self, payload):
        pkt = packet(payload)
        if self.debug:
            print(f"  --> {payload[:20].hex()}{'...' if len(payload) > 20 else ''}")
        self.fd.write(pkt)

    def recv_packet(self, timeout=2.0):
        """Lee un paquete HDLC y devuelve el payload sin CRC."""
        buf = b""
        end = time.time() + timeout
        started = False
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.08)
            if not r:
                continue
            try:
                chunk = os.read(self.fd.fileno(), 4096)
            except OSError:
                break
            if not chunk:
                continue
            for byte in chunk:
                b = bytes([byte])
                if b == b"\x7e":
                    if started and buf:
                        data = unescape(buf)
                        return data[:-2] if len(data) > 2 else data
                    started = True
                    buf = b""
                elif started:
                    buf += b
            end = time.time() + 0.3
        if started and buf:
            data = unescape(buf)
            return data[:-2] if len(data) > 2 else data
        return None

    # ---- comandos ----

    def hello(self):
        """Handshake. Devuelve True si el target responde con su magic."""
        payload = (bytes([0x01]) + MAGIC_HOST
                   + bytes([VERSION, COMPATIBLE, FEATURE_BITS]))
        self.send(payload)
        resp = self.recv_packet(2.5)
        if resp is None:
            return False, "sin respuesta"
        if len(resp) > 33 and resp[0] == 0x02 and resp[1:33] == MAGIC_TARG:
            return True, f"magic OK (ver={resp[33:].hex()})"
        if resp[0] == 0x0D:
            return False, f"ERROR: {resp[5:].decode(errors='replace').strip()}"
        if resp[0] == 0x0E:
            return False, f"MSG: {resp[1:].decode(errors='replace').strip()}"
        return False, f"respuesta inesperada: {resp[:40].hex()}"

    def get_version(self):
        """Pide la version del software del target."""
        self.send(bytes([0x06]))
        return self.recv_packet(2.0)

    def write_chunk(self, address, data):
        """Escribe un bloque en la direccion indicada. PELIGROSO."""
        payload = (bytes([0x0F]) + struct.pack(">I", address)
                   + struct.pack(">H", len(data)) + data)
        self.send(payload)
        resp = self.recv_packet(3.0)
        if resp == b"\x02":
            return True, "ACK"
        return False, resp.hex() if resp else "sin respuesta"


def main():
    port = PORT
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--port" in sys.argv:
        port = sys.argv[sys.argv.index("--port") + 1]
        args = [a for a in args if a != port]
    if "--debug" in sys.argv:
        pass

    if not os.path.exists(port):
        print(f"[!] no existe {port}")
        print("    El stick debe estar en 0076 con ttyUSB expuesto (docs/05).")
        return 1

    mode = args[0] if args else "probe"
    debug = "--debug" in sys.argv

    c = Armpg(port, debug=debug).open()
    try:
        if mode == "probe":
            ok, msg = c.hello()
            print(f"[{'OK' if ok else '!'}] hello: {msg}")
            return 0 if ok else 1

        if mode == "version":
            ok, msg = c.hello()
            print(f"[{'OK' if ok else '!'}] hello: {msg}")
            if not ok:
                return 1
            time.sleep(0.3)
            v = c.get_version()
            print(f"[*] version resp: {v.hex() if v else 'sin respuesta'}")
            return 0

        if mode == "write":
            if len(args) < 3:
                print("uso: armpg.py write <addr_hex> <archivo>")
                return 1
            addr = int(args[1], 0)
            path = args[2]
            data = open(path, "rb").read()
            ok, msg = c.hello()
            print(f"[{'OK' if ok else '!'}] hello: {msg}")
            if not ok:
                print("[!] sin handshake, no escribo nada")
                return 1
            ok, msg = c.write_chunk(addr, data)
            print(f"[{'OK' if ok else '!'}] write @0x{addr:x}: {msg}")
            return 0 if ok else 1

        print(f"[!] modo desconocido: {mode}")
        return 1
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
