# 08 — Ingeniería inversa del firmware

Cómo se llegó de "hay un montón de `.mbn`" a "el protocolo es ARMPRG".

## Los archivos

| Archivo | Tamaño | Qué es |
|---|---|---|
| `amss.mbn` | 15.9 MB | Baseband completo — contiene el lock |
| `efs.mbn` | 21 MB | Filesystem EFS |
| `oemsbl.mbn` | 260 KB | Bootloader (segunda etapa) |
| `nandprgcombined.mbn` | 108 KB | **Programador NAND / ARMPRG** |
| `partition.mbn` | 464 B | Tabla de particiones |
| `qcsbl.mbn`, `mibib.mbn`, `*.hd.mbn` | varios | Headers y primeras etapas |

Sólo `nandprgcombined.mbn` está en el repo. El resto: ver
[firmware/README.md](../firmware/README.md).

## Paso 1 — mirar los strings

Lo más simple primero. En `amss.mbn`:

```
zte_dsatsec.c        ← archivo fuente del subsistema de seguridad
ZNCK                 ← nombre del código de red
RSA                  ← criptografía
```

Ver `tools/strings_scan.py`.

## Paso 2 — `partition.mbn` decodificado a mano

Era lo más chico y resultó enorme de informativo.

```
00000000: 9a1b 7daa bc48 7d1f 0300 0000 0b00 0000   ← header
00000010: 303a 4d49 4249 4200 ...                    ← "0:MIBIB"
```

### Estructura

```
[0x00..0x08]  magic   9a1b7daa bc487d1f
[0x08..0x0C]  versión 3
[0x0C..0x10]  cantidad de particiones = 11 (0x0b)
[0x10..]      entradas de 28 bytes:
                 nombre (16 bytes ASCII, "0:NOMBRE")
                 + block_num (u32)
                 + num_blocks (u32)
                 + flags (u32)
```

### La tabla completa

Salida de `tools/partition_parse.py`:

| Partición | Bloque | Bloques | Flags |
|---|---|---|---|
| `0:MIBIB` | 6 | 4 | `0xfeffffff` |
| `0:SIM_SECURE` | 4 | 2 | `0xfeffffff` |
| `0:QCSBL` | 64 | 10 | `0xffffffff` |
| `0:OEMSBL1` | 256 | 30 | `0xffffffff` |
| `0:OEMSBL2` | 256 | 30 | `0xffffffff` |
| `0:AMSS` | 20000 | 1000 | `0xffffffff` |
| `0:NANDPRG` | 2000 | 100 | `0xffffffff` |
| `0:NVBAK` | 4000 | 100 | `0xffffffff` |
| `0:FOTA` | 1024 | 100 | `0xffffffff` |
| `0:FTL` | 512 | 512 | `0xffffffff` |
| `0:EFS2` | `0xFFFFFFFF` | 65535 | `0xffffffff` |

> `0:EFS2` tiene bloque y tamaño "comodín" (`0xFFFFFFFF`): ocupa el resto
> de la NAND. `0:OEMSBL1` y `0:OEMSBL2` comparten bloque de inicio (dos
> copias, típico de un bootloader con redundancia).

**`0:SIM_SECURE` es donde vive el lock** (ver [04](04-lock.md)).
**`0:NANDPRG` es la partición del programador.**

## Paso 3 — buscar el magic

El magic de `partition.mbn` (`9a1b7daa bc487d1f`) **aparece dentro de
`oemsbl.mbn`** en el offset `0x10C0`:

```
000010b0: ac9f 56fe 7a12 7fcd aa73 ee55 dbbd 5ee3
000010c0: 9a1b 7daa bc48 7d1f a1be 419d ead2 def1   ← el de partition.mbn
000010d0: 5a05 0000 303a 4e41 4e44 5052 4700 0000   ← "0:NANDPRG"
000010e0: fe4f 2de9                                  ← STMFD (código ARM)
```

Es una **tabla de firmas seguida de código**. Eso permitió encontrar
el dispatcher:

```
000010e0: e92d4ffe  STMFD sp!, {r1-r11,lr}
000010fc: e3590000  CMP   r9, #0
00001110: e3590002  CMP   r9, #2
00001118: e3590003  CMP   r9, #3
00001120: e3590004  CMP   r9, #4     ← switch de comandos
```

## Paso 4 — el giro: no era `oemsbl`

Se buscó `"ERR: CRC invalid"` en todos los `.mbn`:

```
oemsbl.mbn              → NO ESTÁ
nandprgcombined.mbn     → offset 0x18158  ✅
```

**El que responde por el puerto serie es el programador NAND, no el
bootloader.** Ese fue el cambio de modelo mental que destrabó todo.

## Paso 5 — desensamblar `nandprgcombined.mbn`

### Formato del archivo

```
[0x00] 00000005     versión
[0x04] 00000003     nº de segmentos
[0x08] 0000055a
[0x0C] 00800028     ← BASE DE CARGA
[0x10] 0001a7ac
[0x14] 0001a7ac
[0x18] 0081a7d4
...
[0x28] e59f10e8     ← primer instrucción ARM
```

**Base de carga `0x800028`.** Calculada cruzando el literal pool
con el header (`0x81a7d4 - 0x1a7ac = 0x800028`).

### Identificación

```
0x19bb4: "  QUALCOMM ARMPRG Identification Block"
         "  Compiled Dec 07 2010 17:07:15"
         "  Version == 14.00.00"
         "  NPRG6246.HEX for MSM6246 ONLY - UART and HSUSB"
```

### Desensamblar

```bash
python3 tools/disasm.py firmware/nandprgcombined.mbn 0x5948 0x5b20
```

Usa **capstone** y aplica la base automáticamente.

### Direcciones clave encontradas

| Offset | Qué hay |
|---|---|
| `0x5948` | Dispatcher de comandos (2..6) |
| `0x5a24` | Construcción de respuesta tipo 5 (`EF 02 01`) |
| `0x5af4` | Validación de secuencia (0 o 1) |
| `0x8ec0` | Copia de buffer (**no** es el validador, error corregido) |
| `0x8ee8` | Verificación de paquete y checksum |
| `0x9040` | `ADD r0, r0, r2` — el **checksum es una suma** |
| `0x14b28` | Literal → string `"ERR: CRC invalid"` |
| `0x17d82+` | Tabla de mensajes del protocolo |

## Paso 6 — `amss.mbn` y el lock

`amss.mbn` es un **ELF** (empieza con `7f 45 4c 46`), a diferencia del
resto. Eso permitió:

- Localizar los flags `0x1D13B04` (`net_lock`) y `0x1D13B05` (`sim_lock`).
- Encontrar el punto de parcheo:

```
0xe30aa8: 13 d0  (BEQ)  →  13 e0  (B)
```

## Errores de lectura que conviene no repetir

Durante el análisis se leyeron varias funciones ARM mal. Queda registrado
porque es un modo de pérdida de tiempo:

| Lo que parecía | Lo que era |
|---|---|
| `0x8ec0` = validador CRC | era una copia de buffer |
| `0x10a4`/`0x10a8` = firmas | eran IDs de parámetro (`0x132`, `0x12f`) |
| `DEADBEEF` = magic de protocolo | es inicialización del literal pool |
| `92 ff` = CRC del mensaje | es control de respuesta, no checksum |

**Lección:** leer ARM a mano lleva a conclusiones falsas. Usar capstone
o un desensamblador real y **volver a verificar cada conclusión**.

## Herramientas

| Script | Uso |
|---|---|
| [tools/disasm.py](../tools/disasm.py) | Desensamblar cualquier offset |
| [tools/strings_scan.py](../tools/strings_scan.py) | Strings con offsets |
| [tools/partition_parse.py](../tools/partition_parse.py) | Decodificar `partition.mbn` |
