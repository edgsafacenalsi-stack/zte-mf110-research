#!/usr/bin/env python3
"""
Envío de comandos AT al módem por /dev/ttyUSB2.

Nota: el puerto AT es ttyUSB2, NO ttyUSB1 (ese es DIAG).

Para leer SMS hace falta seleccionar almacenamiento antes:
    AT+CPMS="ME","ME","ME"
    AT+CMGL=4

Uso:
    python3 at.py 'AT+ZSEC?'
    python3 at.py 'AT+CPMS="ME","ME","ME"' 'AT+CMGL=4'
    python3 at.py --port /dev/ttyUSB2 'AT'
"""
import sys
import time

PORT = "/dev/ttyUSB2"


def send(cmd, port=None, wait=1.2):
    """Envía un comando AT y devuelve las líneas de respuesta."""
    port = port or PORT
    with open(port, "r+b", buffering=0) as f:
        f.write(b"\r")
        time.sleep(0.1)
        try:
            f.read(4096)
        except Exception:
            pass
        f.write(cmd.encode() + b"\r")

        lines = []
        end = time.time() + wait
        buf = b""
        while time.time() < end:
            try:
                chunk = f.read(4096)
            except Exception:
                time.sleep(0.05)
                continue
            if chunk:
                buf += chunk
                end = time.time() + 0.3
                while b"\r\n" in buf or b"\n" in buf:
                    sep = b"\r\n" if b"\r\n" in buf else b"\n"
                    line, buf = buf.split(sep, 1)
                    line = line.decode(errors="replace").strip()
                    if line:
                        lines.append(line)
                    if line in ("OK", "ERROR") or line.startswith("+CME ERROR"):
                        return lines
        return lines


def main():
    args = sys.argv[1:]
    port = None
    if args and args[0] == "--port":
        port = args[1]
        args = args[2:]
    if not args:
        print(__doc__)
        return 1
    for cmd in args:
        print(f">>> {cmd}")
        for line in send(cmd, port=port):
            print(f"    {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
