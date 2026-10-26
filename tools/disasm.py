#!/usr/bin/env python3
"""
Desensamblador ARM para los .mbn de Qualcomm.

Aplica automáticamente la base de carga si detecta el header.

Uso:
    python3 disasm.py <archivo.mbn> <inicio_hex> <fin_hex> [base_hex]

Ejemplos:
    python3 disasm.py firmware/nandprgcombined.mbn 0x5948 0x5b20
    python3 disasm.py firmware/oemsbl.mbn 0x10e0 0x1130 0x0
"""
import struct
import sys

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN


def detect_base(d):
    """Los .mbn Qualcomm llevan la base de carga en el header."""
    if len(d) < 0x20:
        return 0
    # Header típico: [0]=ver [4]=nseg [8]=? [0xC]=base
    base = struct.unpack_from("<I", d, 0x0C)[0]
    if 0x800000 <= base <= 0x900000:
        return base
    return 0


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1

    path = sys.argv[1]
    start = int(sys.argv[2], 0)
    end = int(sys.argv[3], 0)
    d = open(path, "rb").read()

    if len(sys.argv) > 4:
        base = int(sys.argv[4], 0)
    else:
        base = detect_base(d)
        if base:
            print(f"[*] base de carga detectada: 0x{base:06x}")

    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    code = d[start:end]

    print(f"[*] {path}  0x{start:06x}..0x{end:06x}\n")
    for ins in md.disasm(code, base + start):
        off = ins.address - base
        print(f"{off:06x}:  {ins.mnemonic:8s} {ins.op_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
