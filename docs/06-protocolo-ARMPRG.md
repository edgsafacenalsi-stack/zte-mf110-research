# 06 — Protocolo ARMPRG

**Este es el documento central del repo.** Registra todo lo que se sabe del
protocolo de flasheo del MF110 y el punto exacto donde quedó.

## El descubrimiento

En modo download, el stick **no habla Sahara/EDL**. Habla **Qualcomm ARMPRG**.

Identificación, extraída de `nandprgcombined.mbn`:

```
  QUALCOMM ARMPRG Identification Block
  Compiled Dec 07 2010 17:07:15
  Version == 14.00.00
  NPRG6246.HEX for MSM6246 ONLY - UART and HSUSB
  Multi-Image Boot Support only
  Copyright (c) 2007 by QUALCOMM, Incorporated
```

**`ARMPRG` = ARM Programmer.** Es el programador NAND que QPST carga antes
de flashear. El stick **ya lo tiene ejecutándose**, por eso responde.

## Cómo se confirmó

1. Se buscó el string `"ERR: CRC invalid"` en todo el firmware.
2. **No está en `oemsbl.mbn`** (el bootloader).
3. **Está en `nandprgcombined.mbn`**, offset `0x18158`.
4. Ese mismo binario contiene *todos* los mensajes que fuimos viendo:
   `Window overrun`, `Invalid magic number`, `checking partition table`.

## Todos los mensajes del protocolo

Extraídos con offsets de `nandprgcombined.mbn`. **Están en orden de
aparición en el binario, que sigue el flujo esperado del protocolo:**

```
0x17d82  ARMPRG size msg overrun
0x17df4  ERR: Window overrun detected...
0x17e40  Invalid magic number
0x17e74  Parameter Request Packet Length Error
0x17e9c  Internal error - reply_buffer overrun
0x17ec4  Invalid packet length
0x17edc  Packet too large
0x17ef0  Read unsuccessful
0x17f20  Simple write not allowed
0x17f3c  Write unsuccessful
0x17f70  crc verify failed
0x17f9c  Already opened in different mode
0x17fc0  Already opened, ignoring open in same mode
0x17fec  Open failed
0x17ff8  Cannot close when not previously opened
0x18030  Set security mode failed.
0x1804c  No security mode received before partition table
0x18080  Partition table length exceeded
0x180a0  Unknown error accepting partition table
0x180c8  No security mode received before open multi
0x180f4  No partition table received before open multi
0x18124  Open multi failed, unknown error
0x18148  checksum failed
0x18158  ERR: CRC invalid
0x1818c  Image file with header
0x181b4  page_bytes_user
0x181c4  block_pages
0x181d0  device_blocks
```

## La secuencia de flasheo que exige

Los mensajes de error revelan el **orden obligatorio**:

```
1. SET SECURITY MODE
     ↓ (si falta → "No security mode received before ...")
2. PARTITION TABLE        ← partition.mbn
     ↓ (si falta → "No partition table received before open multi")
3. OPEN MULTI
     ↓
4. OPEN (por partición)
     ↓
5. WRITE (por página)
     ↓
6. CLOSE
```

Cada paso tiene su validación y su mensaje de error específico. Eso hace
del protocolo **algo verificable paso a paso**: si un paso falla, el
mensaje dice exactamente cuál.

## Estructura del paquete (parcial)

Reconstruida desensamblando el dispatcher ARM en `0x5948` y siguientes,
con base de carga `0x800028`:

```
Offset  Campo
------  ------------------------------------------
+0x01   secuencia      (válido: 0 o 1)
+0x02   tipo comando   (válidos: 2, 3, 4, 5, 6)
+0x08   (buffer/longitud)
+0x0C   dirección      (offset NAND)
+0x10   puntero a tabla de handlers
+0x14   (relación con +0x18)
+0x18   (relación con +0x14)
+0x20   campo comparado
+0x24   campo comparado
+0x2C   bloque de 16 bytes comparado
+0x3C   campo de checksum
+0x40   campo de checksum
```

### Dispatcher

```
0x5948  STMFD sp!, {r4,lr}
0x5954  LDRB  r0, [r4, #2]      ; tipo
0x5958  CMP   r0, #4
0x595c  CMP   r0, #5
0x5960  CMP   r0, #6
0x5964  BNE   salir             ; sólo 4,5,6 llegan al handler
0x5968  MOV   r1, #0
0x596c  MOV   r0, r4
0x5970  BL    <validación>
0x5974  LDR   r1, [r4, #0x10]
0x5978  LDR   r0, [r4, #0xC]
0x597c  LDR   r1, [r1, #4]
0x5980  BLX   r1                ; ejecuta handler del comando
0x5984  MOV   r0, #4
0x5988  STRB  r0, [r4, #2]      ; respuesta: tipo 4
```

### Respuesta informativa

```
0x5a24  MOV  r1, #0xEF
0x5a28  STRB r1, [r0, #0xC]     ; 0xEF
0x5a2c  MOV  r1, #2
0x5a30  STRB r1, [r0, #0xD]     ; 0x02
0x5a34  MOV  r1, #1
0x5a38  STRB r1, [r0, #0xE]     ; 0x01
0x5a44  MOV  r0, #5
0x5a48  STRB r0, [r4, #2]       ; respuesta tipo 5
```

### Validación de secuencia

```
0x5af4  LDRB  r3, [r0, #2]      ; tipo == 5 ?
0x5af8  CMP   r3, #5
0x5b00  LDRB  r3, [r0, #1]      ; secuencia
0x5b04  CMP   r3, #0
0x5b08  CMPNE r3, #1            ; válida si 0 o 1
```

### Checksum: es una SUMA, no un CRC

```
0x9028  LDR   r1, [r5, #0x3c]
0x902c  LDR   r0, [r4, #0x3c]
0x9030  CMPEQ
0x9034  LDR   r1, [r5, #0x40]
0x9038  LDR   r2, [r4, #0x40]
0x9040  ADD   r0, r0, r2        ; ¡suma de campos!
0x9044  BEQ   éxito
```

Esto corresponde al mensaje `checksum failed`, que es **distinto** de
`ERR: CRC invalid`. Son dos validaciones separadas.

## Lo que NO se pudo determinar

**El framing exacto en el cable (wire format).** Es el único bloqueo.

### El hallazgo decisivo (radare2, base `0x800000`)

Desensamblando `nandprgcombined.mbn` se siguió la cadena completa:

```
0x5954  ldrb r0,[r4,#2]   ; tipo (4,5,6)
0x5970  bl   0x5068       ; validación principal
0x5068  ldr  r1,[r4,#0x10]  ; tabla de handlers
0x507c  ldr  r2,[r1,#0x4c]  ; handler[0x4C] = validador
0x5084  blx  r2           ; ¡valida!
0x1a14c    tabla de handlers (+0x4c = 0x816c60)
0x816c60   validador → 0x1650 (registro de hardware)
0x16d5c    función maestra, sl=0xb (11 fragmentos)
0x80c7d8   handler +0x3c → driver UART
0xc880     str r0,[sl,#0x304]  ← ¡REGISTRO DE HARDWARE!
```

**La "validación" del ARMPRG termina en un registro de hardware UART**
(`str [sl, #0x304]`), no en un algoritmo de CRC.

### ⚠️ Corrección posterior (ver [doc 11](11-dll-qpst-y-crc-hardware.md))

En una primera lectura se concluyó que **`ERR: CRC invalid` lo calculaba
QPST** en `QMSL_MSVC10R.dll`. **Eso resultó incorrecto.**

Lo que se verificó después:

- El **magic real** es `"QCOM fast download protocol host"` (32 bytes).
- Con ese magic, el error cambia de `Invalid magic number` a `CRC invalid`.
- La función `0x1679c` del firmware **dispara el Crypto Engine del hardware**
  y lee el resultado de un registro (`str [r4,#0x1c]`, `ldr [r4,#0x1c]`).

**El CRC es hardware.** Ningún algoritmo de software coincide — se probaron
228 variantes.

Ver [doc 11](11-dll-qpst-y-crc-hardware.md) para el desarrollo completo.

### Aún así, las pruebas de framing siguen siendo válidas

Se probaron:

| Variante | Resultado |
|---|---|
| HDLC `7E` + escapado + CRC16 LE | `ERR: CRC invalid` |
| HDLC `7E` + escapado + CRC16 BE | `ERR: CRC invalid` |
| 21 combinaciones de CRC16 (CCITT, XMODEM, Kermit, IBM, X25, ARC, Modbus) | todas `CRC invalid` |
| Suma simple (8-bit) / XOR | `CRC invalid` |
| Sin CRC | `CRC invalid` |
| Framing sin `7E` | generalmente sin respuesta |
| `deadbeef` como magic | no probado contra el stick |
| `partition.mbn` completo | no probado contra el stick |

Todas las variantes que **usan `7E`** obtienen respuesta (el parser las
procesa). Las que no, son ignoradas. Eso confirma **`7E` como delimitador**
pero no el formato interno.

## Hipótesis para quien siga

1. **El magico `DEADBEEF`** aparece en el literal pool de `nandprg` (`0x118`).
   Puede ser el magic del wire format. **No se probó contra el stick.**
2. **`0x92 0xFF`** en la respuesta puede ser un **magic de respuesta**
   (no un checksum del payload).
3. **El campo de longitud `0e`** en la respuesta: verificar si cuenta
   bytes, palabras o caracteres del mensaje sin el prefijo `ERR:`.
4. El wire format probablemente tiene un **header fijo** antes del payload,
   con magic + tipo + longitud, y el CRC **no** va sobre el payload entero.

## Herramientas para seguir

- [tools/dl76.py](../tools/dl76.py) — cliente con entrada a `0076` y envío HDLC
- [tools/dl76_crc_hunt.py](../tools/dl76_crc_hunt.py) — busca el CRC por prueba
- [tools/disasm.py](../tools/disasm.py) — desensambla `nandprg` con capstone
