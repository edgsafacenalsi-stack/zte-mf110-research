#!/usr/bin/env python3
"""
Decodifica el archivo partition.mbn del ZTE MF110.

Formato (reconstruido por inspección):

    [0x00..0x08]  magic     9a1b7daa bc487d1f
    [0x08..0x0C]  versión   (3)
    [0x0C..0x10]  cantidad de entradas
    [0x10..]      entradas de 16 bytes:
                    nombre    16 bytes ASCII ("0:NOMBRE")
                    block_num u32
                    num_blocks u32
                    flags     u32

Uso:
    python3 partition_parse.py partition.mbn
"""
import struct
import sys

MAGIC = bytes.fromhex("9a1b7daabc487d1f")


def parse(path):
    d = open(path, "rb").read()

    if d[:8] != MAGIC:
        print(f"[!] magic inesperado: {d[:8].hex()} (esperado {MAGIC.hex()})")
        return None

    version, count = struct.unpack_from("<II", d, 8)
    print(f"magic:    {MAGIC.hex()}")
    print(f"versión:  {version}")
    print(f"entradas: {count}\n")

    print(f"{'partición':<20} {'bloque':>8} {'bloques':>8}  flags")
    print("-" * 56)

    out = []
    off = 0x10
    for _ in range(count):
        if off + 16 > len(d):
            break
        name = d[off:off + 16].split(b"\x00")[0].decode("latin1")
        block, nblocks, flags = struct.unpack_from("<III", d, off + 16)
        print(f"{name:<20} {block:>8} {nblocks:>8}  0x{flags:08x}")
        out.append({
            "name": name,
            "block": block,
            "num_blocks": nblocks,
            "flags": flags,
        })
        off += 28

    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    parse(sys.argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
