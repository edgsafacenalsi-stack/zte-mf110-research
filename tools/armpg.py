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
        # CRITICO: poner el TTY en modo raw, sin eco ni extensiones.
        # Sin esto el driver 'option' procesa los bytes y los 0x7E/0x7D
        # se corrompen. Es lo que hace qdloader con:
        #     stty raw -iexten -echo
        os.system(f"stty -F {self.port} raw -iexten -echo 2>/dev/null")
        self.fd = os.fdopen(
            os.open(self.port, os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY),
            "r+b", buffering=0)
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

    def recv_packet(self, timeout=2.5):
        """Lee UN paquete HDLC completo. Devuelve payload sin CRC, o None.

        Algoritmo de qdloader: espera el 0x7E inicial, acumula hasta el
        siguiente 0x7E, desescapa y quita los 2 bytes de CRC.
        """
        # esperar 0x7E inicial
        end = time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if not r:
                continue
            try:
                c = os.read(self.fd.fileno(), 1)
            except OSError:
                return None
            if not c:
                continue
            if c[0] == 0x7E:
                break
        else:
            return None

        # acumular hasta el 0x7E de cierre
        buf = bytearray()
        end = time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if not r:
                continue
            try:
                c = os.read(self.fd.fileno(), 1)
            except OSError:
                return None
            if not c:
                continue
            if c[0] == 0x7E:
                data = unescape(bytes(buf))
                return data[:-2] if len(data) > 2 else data
            buf.append(c[0])
        return None

    # ---- comandos ----

    def hello(self):
        """Handshake. Devuelve (ok, info, respuesta_cruda).

        La respuesta valida empieza con 0x02 y contiene el magic del target,
        seguido de la geometria de la NAND.
        """
        payload = (bytes([0x01]) + MAGIC_HOST
                   + bytes([VERSION, COMPATIBLE, FEATURE_BITS]))
        self.send(payload)
        resp = self.recv_packet(3.0)
        if resp is None:
            return False, "sin respuesta", None
        if len(resp) > 33 and resp[0] == 0x02 and resp[1:33] == MAGIC_TARG:
            info = f"magic del target OK, protocolo v{resp[33]}.{resp[34]}"
            nand = None
            i = resp.find(b"SAMSUNG")
            if i < 0:
                i = resp.find(b"\x0fSAMSUNG")
            if i >= 0:
                j = resp.find(b"\x00", i)
                nand = resp[i:j].decode(errors="replace").lstrip("\x0f")
                info += f", NAND={nand}"
            return True, info, resp
        if resp[0] == 0x0D:
            return False, f"ERROR: {resp[5:].decode(errors='replace').strip()}", resp
        if resp[0] == 0x0E:
            return False, f"MSG: {resp[1:].decode(errors='replace').strip()}", resp
        return False, f"respuesta inesperada (tipo 0x{resp[0]:02x})", resp

    def request_params(self):
        """Pide los parametros del target (comando 0x07)."""
        self.send(bytes([0x07]))
        return self.recv_packet(3.0)

    def close_flush(self):
        self.send(bytes([0x15]))
        return self.recv_packet(2.0)

    def secure_mode(self, mode=1):
        self.send(bytes([0x17, mode]))
        return self.recv_packet(2.0)

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
            ok, msg, raw = c.hello()
            print(f"[{'OK' if ok else '!'}] hello: {msg}")
            if ok and raw:
                print(f"\n[*] respuesta completa: {len(raw)} bytes")
                import re
                for m in re.finditer(rb"[\x20-\x7e]{4,}", raw):
                    print(f"    @{m.start():4d}: {m.group().decode()}")
            return 0 if ok else 1

        if mode == "params":
            ok, msg, _ = c.hello()
            print(f"[{'OK' if ok else '!'}] hello: {msg}")
            if not ok:
                return 1
            time.sleep(0.3)
            r = c.request_params()
            if r is None:
                print("[!] requestParam: silencio")
                return 1
            print(f"[*] params: tipo=0x{r[0]:02x} len={len(r)}")
            print(f"    {r[:80].hex()}")
            return 0 if r[0] == 0x08 else 1

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
