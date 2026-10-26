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


def send(cmd, port=None, wait=1.5):
    """Envía un comando AT y devuelve las líneas de respuesta.

    Usa un puerto bloqueante con flush previo. Es más lento que
    select() pero evita mezclarse con el buffer del driver, que en
    este módem produce respuestas corruptas tipo "AT+ZAT+ZAT+ZSEC?".
    """
    port = port or PORT
    with open(port, "r+b", buffering=0) as f:
        # limpiar residuos del comando anterior
        try:
            f.write(b"\r")
            time.sleep(wait * 0.6)
            f.read(4096)
        except Exception:
            pass

        f.write(cmd.encode() + b"\r")

        lines = []
        buf = b""
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                chunk = f.read(4096)
            except Exception:
                time.sleep(0.02)
                continue
            if not chunk:
                continue
            buf += chunk
            deadline = time.time() + 0.3
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.decode(errors="replace").strip("\r").strip()
                if not line:
                    continue
                # descartar ecos partidos del comando anterior ("AT+Z", "AT")
                if line in ("AT", "AT+Z") or line == cmd:
                    continue
                lines.append(line)
                if line == "OK" or line == "ERROR" or line.startswith("+CME ERROR"):
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
        resp = send(cmd, port=port)
        if not resp:
            print("    <sin respuesta>")
        for line in resp:
            print(f"    {line}")
        time.sleep(0.2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
