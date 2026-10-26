#!/usr/bin/env python3
"""
Cliente DIAG (QCDM) para ZTE MF110 / MSM6290.

Habla con la interfaz QCDM del módem por libusb.

Framing:
  comandos:  0x7E | payload | CRC16-CCITT(ref) LE | 0x7E   (con escapado HDLC)
  respuestas: SIN 0x7E inicial (asimétrico)

DIAG está en la INTERFAZ 0 (EP 0x01 OUT / 0x81 IN), no en la 3.

IMPORTANTE — estado de esta implementación:
  El canal DIAG se abre, autentica (SPC + password) y permite el diálogo
  básico. La lectura de NV items funciona pero es intermitente: exige
  sincronizar el contador de secuencia del módem y el framing de las
  respuestas largas (que llevan separadores 0x7E internos). El volcado
  completo de este repo se hizo con el cliente original, más tolerante.

  `nv_read()` devuelve la respuesta desescapada en bruto y NO recorta
  los 128 bytes de datos automáticamente. Ver docs/03-nv.md.

Uso:
    python3 diag.py            # prueba de conexión + lectura de NV 0
"""
import struct

import crcmod
import usb.core
import usb.util

VID = 0x19D2
PID_NORM = 0x0031
IFACE = 0
EP_OUT = 0x01
EP_IN = 0x81

SPC = b"\x00\x00\x00\x00\x00\x00"
PASSWORD = bytes.fromhex("FFFFFFFFFFFFFFFE")

_crc = crcmod.mkCrcFun(0x11021, rev=True, initCrc=0, xorOut=0xFFFF)


def esc(b):
    return b.replace(b"\x7d", b"\x7d\x5d").replace(b"\x7e", b"\x7d\x5e")


def unesc(b):
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


def frame(payload):
    return b"\x7e" + esc(payload + struct.pack("<H", _crc(payload))) + b"\x7e"


class Diag:
    def __init__(self):
        self.dev = None
        self.detached = False

    def open(self, timeout=15):
        import time
        t0 = time.time()
        while time.time() - t0 < timeout:
            self.dev = usb.core.find(idVendor=VID, idProduct=PID_NORM)
            if self.dev:
                break
            time.sleep(0.1)
        if not self.dev:
            raise RuntimeError("stick no encontrado en 19d2:0031")

        try:
            if self.dev.is_kernel_driver_active(IFACE):
                self.dev.detach_kernel_driver(IFACE)
                self.detached = True
        except Exception:
            pass
        usb.util.claim_interface(self.dev, IFACE)
        return self

    def close(self):
        try:
            usb.util.release_interface(self.dev, IFACE)
        except Exception:
            pass
        if self.detached:
            try:
                self.dev.attach_kernel_driver(IFACE)
            except Exception:
                pass
        try:
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass

    def drain(self, rounds=3, timeout=100):
        for _ in range(rounds):
            try:
                self.dev.read(EP_IN, 4096, timeout=timeout)
            except Exception:
                break

    def request(self, payload, wait=0.5, retries=4):
        """Envía un comando y devuelve la respuesta desescapada, o None."""
        import time
        for attempt in range(retries):
            self.drain(rounds=2, timeout=100)
            self.dev.write(EP_OUT, frame(payload), timeout=1500)
            time.sleep(wait + attempt * 0.3)
            for _ in range(3):
                try:
                    raw = bytes(self.dev.read(EP_IN, 4096, timeout=700))
                except Exception:
                    break
                raw = raw.strip(b"\x7e")
                got = unesc(raw)
                if got:
                    return got
        return None

    def spc(self):
        """Autenticación de servicio: SPC + password."""
        r1 = self.request(b"\x41" + SPC)
        r2 = self.request(b"\x42" + PASSWORD)
        return r1, r2

    def nv_read(self, item):
        """Lee un NV item.

        Devuelve la respuesta desescapada en bruto. El payload tiene
        cabecera + item + datos + CRC; ver docs/03-nv.md para el formato.
        """
        req = b"\x26" + struct.pack("<H", item) + b"\x00\x00"
        return self.request(req, wait=0.6)


if __name__ == "__main__":
    d = Diag().open()
    try:
        spc_r, pw_r = d.spc()
        print(f"SPC:      {'ok' if spc_r else 'sin respuesta'}")
        print(f"password: {'ok' if pw_r else 'sin respuesta'}")
        r = d.nv_read(0)
        if r:
            print(f"NV 0 ({len(r)} bytes): {r.hex()}")
        else:
            print("NV 0: sin respuesta (ver docstring: lectura intermitente)")
    finally:
        d.close()
