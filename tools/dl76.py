#!/usr/bin/env python3
"""
Cliente del protocolo de download 0076 para ZTE MF110 - v2.

Cambio clave respecto a v1: el bootloader NO responde por el endpoint.
Tras ejecutar un comando, el stick RE-ENUMERA el USB con otro PID.
Ese PID es el canal de respuesta.

Flujo por comando:
  1. Verificar stick en 0031 sano (AT+ZSEC?)
  2. Entrar a 0076
  3. Enviar comando HDLC (CRC-16 CCITT LE)
  4. Esperar re-enumeracion: muestrear PID cada 50 ms durante N ms
  5. Registrar la secuencia de PIDs observada
  6. Esperar retorno a 0031 y verificar AT de nuevo

Uso:
    dl76.py sweep            -> barrido comandos 1..7 con payload vacio
    dl76.py sweep-payload    -> igual pero payload de 4 bytes cero
    dl76.py one N [hex]      -> un solo comando, con payload hex opcional
    dl76.py watch            -> solo vigilar PIDs
"""
import os
import sys
import time
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crcmod
import usb.core
import usb.util

VID, PID_NORM, PID_DL = 0x19D2, 0x0031, 0x0076
IFACE, EP_OUT, EP_IN = 0, 0x01, 0x81

AUTH = bytes.fromhex(
    "4BCB0200321170B2DCEC4257F087EDCACB09C8AFB6F39A70F4E9F49980AA1141ABB872E6CBD263E279502A35624DA"
    "19A6EFE5AF90B9DE95C67004B1DCC4628781B8123433D2760A57CD54FF7455B6CB5EBA0612002725050A4BC7D5D841764F4D"
    "6C55AE121CB787D5D5BD874B7373102AFD3FD15C5D89C2CC30C46C3C270CDC371DB43E58B77765E7E")

_crc = crcmod.mkCrcFun(0x11021, rev=True, initCrc=0, xorOut=0xffff)


def esc(b):
    return b.replace(b"\x7d", b"\x7d\x5d").replace(b"\x7e", b"\x7d\x5e")


def frm(p):
    return b"\x7e" + esc(p + struct.pack("<H", _crc(p))) + b"\x7e"


def current_pid():
    """PID actual del stick, o None si no esta."""
    for pid in (PID_NORM, PID_DL, 0x2000, 0x2002, 0x2003, 0x0053, 0x0001):
        if usb.core.find(idVendor=VID, idProduct=pid):
            return pid
    # buscar cualquier PID de ZTE
    try:
        devs = list(usb.core.find(find_all=True, idVendor=VID))
        if devs:
            return devs[0].idProduct
    except Exception:
        pass
    return None


def wait_pid(pid, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if usb.core.find(idVendor=VID, idProduct=pid):
            return True
        time.sleep(0.05)
    return False


def watch_pids(seconds=8.0):
    """Muestrea la secuencia de PIDs durante N segundos."""
    seq = []
    t0 = time.time()
    while time.time() - t0 < seconds:
        p = current_pid()
        if not seq or seq[-1][0] != p:
            seq.append((p, round(time.time() - t0, 2)))
        time.sleep(0.04)
    return seq


def claim(dev):
    det = False
    try:
        if dev.is_kernel_driver_active(IFACE):
            dev.detach_kernel_driver(IFACE)
            det = True
    except Exception:
        pass
    try:
        usb.util.claim_interface(dev, IFACE)
    except Exception:
        return None
    return det


def release(dev, det):
    try:
        usb.util.release_interface(dev, IFACE)
    except Exception:
        pass
    if det:
        try:
            dev.attach_kernel_driver(IFACE)
        except Exception:
            pass
    try:
        usb.util.dispose_resources(dev)
    except Exception:
        pass


def drain(dev, rounds=3, timeout=250):
    for _ in range(rounds):
        try:
            dev.read(EP_IN, 4096, timeout=timeout)
        except Exception:
            break


def enter_download(timeout=60):
    d = usb.core.find(idVendor=VID, idProduct=PID_NORM)
    if not d:
        print("  [!] no hay stick en 0031")
        return False
    det = claim(d)
    if det is None:
        print("  [!] no pude reclamar interfaz")
        return False
    try:
        drain(d)
        d.write(EP_OUT, AUTH, timeout=1500)
        drain(d, timeout=350)
        d.write(EP_OUT, frm(bytes([0x3A])), timeout=800)
        drain(d, timeout=350)
        d.write(EP_OUT, frm(bytes([0x4B, 0x10, 0x01, 0x00])), timeout=500)
    finally:
        release(d, det)
    if wait_pid(PID_DL, timeout):
        print("  [*] en 0076")
        return True
    print(f"  [!] no entro a 0076 (pid actual: {current_pid()})")
    return False


def send_cmd(payload):
    """Envia un comando HDLC a 0076. Devuelve True si el write salio."""
    dl = usb.core.find(idVendor=VID, idProduct=PID_DL)
    if not dl:
        print("  [!] no esta en 0076")
        return False
    det = claim(dl)
    if det is None:
        print("  [!] no pude reclamar 0076")
        return False
    ok = False
    try:
        drain(dl, 1, 200)
        dl.write(EP_OUT, frm(payload), timeout=1000)
        ok = True
    except Exception as e:
        print(f"  [!] write error: {e}")
    finally:
        release(dl, det)
    return ok


def at_check(port="/dev/ttyUSB2"):
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import at_scan
        at_scan.PORT = port
        r1 = at_scan.send("AT", wait=1.0) or []
        r2 = at_scan.send("AT+ZSEC?", wait=1.5) or []
        ok = any("OK" in x for x in r1)
        sec = next((x for x in r2 if "ZSEC" in x), "?")
        return ok, sec
    except Exception as e:
        return False, f"err {e}"


def wait_healthy(timeout=25):
    """Espera que vuelva a 0031 con ttyUSB y AT respondiendo."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if usb.core.find(idVendor=VID, idProduct=PID_NORM):
            import os
            if os.path.exists("/dev/ttyUSB2"):
                time.sleep(0.7)
                ok, sec = at_check()
                if ok:
                    return True, sec
        time.sleep(0.2)
    return False, "timeout"


def run_one(name, payload, settle=8.0):
    print(f"\n=== {name}: {payload.hex()} ===")
    ok, sec = at_check()
    print(f"  pre  AT={ok} {sec}")
    if not ok:
        print("  [!] stick no sano ANTES. Aborto este comando.")
        return {"cmd": name, "status": "unsafe-pre"}

    if not enter_download():
        status = "no-enter"
        healthy, after = wait_healthy()
        print(f"  post {after} (recovered={healthy})")
        return {"cmd": name, "status": status, "after": after}

    if not send_cmd(payload):
        healthy, after = wait_healthy()
        print(f"  post {after} (recovered={healthy})")
        return {"cmd": name, "status": "write-fail", "after": after}

    print(f"  secuencia de PIDs tras enviar (2 s):")
    seq = watch_pids(2.5)
    for p, t in seq:
        label = "0031" if p == PID_NORM else ("0076" if p == PID_DL else str(p))
        print(f"    +{t:4.2f}s  pid={label}")

    healthy, after = wait_healthy()
    print(f"  post {after} (recovered={healthy})")
    return {"cmd": name, "status": "sent", "seq": seq, "after": after, "healthy": healthy}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    mode = sys.argv[1]

    if mode == "watch":
        print("=== vigilando PIDs (10 s) ===")
        for p, t in watch_pids(10):
            print(f"  +{t:4.2f}s  {p}")
        return 0

    results = []

    if mode == "sweep":
        for n in range(1, 8):
            r = run_one(f"cmd{n}", bytes([n]))
            results.append(r)
            if r.get("healthy") is False and r.get("status") == "sent":
                print("\n[!] PARADA: el stick no volvio sano. Abortando barrido.")
                break
            time.sleep(1.0)
    elif mode == "sweep-payload":
        for n in range(1, 8):
            r = run_one(f"cmd{n}+zeros", bytes([n]) + b"\x00" * 8)
            results.append(r)
            if r.get("healthy") is False and r.get("status") == "sent":
                print("\n[!] PARADA: el stick no volvio sano. Abortando barrido.")
                break
            time.sleep(1.0)
    elif mode == "one":
        n = int(sys.argv[2], 0)
        extra = bytes.fromhex(sys.argv[3]) if len(sys.argv) > 3 else b""
        r = run_one(f"cmd{n}", bytes([n & 0xFF]) + extra)
        results.append(r)
    else:
        print(f"[!] modo desconocido: {mode}")
        return 1

    print("\n\n================ RESUMEN ================")
    for r in results:
        seq = ""
        if "seq" in r:
            seq = " -> ".join(
                ("0031" if p == PID_NORM else "0076" if p == PID_DL else str(p))
                for p, _ in r["seq"]
            )
        print(f"{r['cmd']:12s} {r['status']:10s} {seq:35s} post={r.get('after','-')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
