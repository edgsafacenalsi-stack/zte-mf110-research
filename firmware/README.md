# Firmware

## Archivo incluido

| Archivo | Tamaño | SHA-256 |
|---|---|---|
| `nandprgcombined.mbn` | 108 500 B | `712f408a632ec4d9fad9fdd6e1d87a406d3e9dd691b205cababe35f5b802ab15` |

**Qué es:** el *NAND Programmer* de Qualcomm (ARMPRG v14.00.00). Es el
binario que el módem ejecuta en modo download y **el que implementa el
protocolo** documentado en [docs/06](../docs/06-protocolo-ARMPRG.md).

**Por qué está acá:** sin este archivo el repo no se puede verificar ni
continuar la investigación. Es el corazón del hallazgo.

**Copyright:** Qualcomm Incorporated, 2007. Se incluye con fines de
investigación e interoperabilidad (análisis de un protocolo de
comunicaciones para permitir el uso legítimo del propio hardware).

---

## Archivos NO incluidos

El resto del firmware (≈58 MB) no se distribuye en este repo. Se documentan
checksums para que cada quien verifique lo que consiga.

| Archivo | Tamaño | SHA-256 |
|---|---|---|
| `amss.mbn` | 15.9 MB | `a3fc8d85fc686aba3db336ce9999534c3714f2d22dfbc7297896b94c9a951aa3` |
| `efs.mbn` | 21 MB | `a05acca96e25afa05680c71dd8d2adf6b96846771146cb8d2e28cbb398d59254` |
| `oemsbl.mbn` | 260 KB | `c0f66af868375700e8aca235010367037a092d979aac9f40597b83550ff5f49a` |
| `oemsblhd.mbn` | — | `704ab7b167a7ef00a7d0b8d2d4ef2258db469c99b2dd13dcd184e4ad0ae6e0d1` |
| `amsshd.mbn` | — | `d9de9cac09903b5d447bb8f99ab6111047b253abb6b1a2d87b6cde207defb9c2` |
| `mibib.mbn` | — | `6f042cf1ed2d4b45c2b367bb53b15f633ff11b25b90cdce5a75d5b982e5a6212` |
| `qcsbl.mbn` | — | `8046a137e59bee36a31f5b6155e3670f23dd7bd484f2ee102bad94596b8cef2c` |
| `qcsblhd_cfgdata.mbn` | — | `e196f8a8e73c028f43652a5855ec9f82a13084ae213f22a7053da6b4059d2a38` |
| `nandprghd.mbn` | — | `95dd0835e692f767c6ceb2887ae96eb07417f7570719c5a841f6d65d01e4dc37` |
| `partition.mbn` | 464 B | `6b5aafbe322807966928e4f42bb7412e8083b748ece6e0a744562ceb8e414493` |
| `armprg.bin` | — | `f2c86a835dae6b3eb6e83f267eb77d5aef23464d4506cc20999884060f4d6f63` |

### Origen

El paquete usado se llamaba `MF110_P671A2_V1.0.2B17.7z` y se obtuvo de un
sitio de firmware de terceros (3ginfo.ru).

### El `partition.mbn` es chico y vale la pena

Aunque no se distribuye, se puede **reconstruir a mano**: su estructura
está completamente documentada en
[docs/08](../docs/08-firmware-re.md) y el script
[`tools/partition_parse.py`](../tools/partition_parse.py) lo decodifica.

### Verificar lo que bajes

```bash
sha256sum *.mbn
```

Comparar con la tabla de arriba. Si un checksum no coincide, **no usar
ese firmware**.

---

## Advertencia de versiones

El stick investigado tiene firmware `V1.0.0B03`, y el `efs.mbn` del paquete
es `V1.0.2B17`.

**Son versiones distintas.** Flashear un EFS de otra versión puede dejar
el equipo inutilizable.
