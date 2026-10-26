# 13 — Ingeniería del paquete de escritura

Índice: [← El protocolo desde QPST](11-protocolo-desde-qpst.md) · [Índice](00-INDICE.md)

> **Estado:** handshake completo y validado en hardware. Esta parte
> documenta lo que se sabe del **paquete de escritura** y lo que falta.

---

## Lo confirmado

### El handshake funciona

```bash
stty -F /dev/ttyUSB0 raw -iexten -echo
python3 tools/armpg.py probe
```

```
[OK] hello: magic del target OK, protocolo v3.2, NAND=SAMSUNG_K9F1208d
```

### Comandos que el firmware RECONOCE

Se envió un byte por comando, tras el handshake. El firmware respondió:

| Comando | Respuesta | Interpretación |
|---|---|---|
| `0x02` | `InvalidCmd` | no existe |
| `0x03` | `InvalidCmd` | no existe |
| **`0x04`** | **`Invalid packet length`** | ✅ **existe**, falta formato |
| `0x05` | (error 0x03) `Invalid packet length` | variante de 0x04 |
| `0x06` | `InvalidCmd` | no existe |
| **`0x08`** | **`Simple write not allowed`** | ✅ **existe**, requiere otro modo |
| `0x09` | (error 0x05) `Simple write not allowed` | variante de 0x08 |
| `0x0A` | **desconecta el stick** | comando de reset |

**Esto es información sólida**: el firmware nos dice qué comandos reconoce
y en qué estado está cada uno.

### El handler de escritura, desensamblado

Función `0x11c8c` en `nandprgcombined.mbn`:

```
011c8c: push {r4, lr}
011c90: add  r2, r0, #6          ; r2 = puntero al payload
011c94: ldrh r0, [r0, #4]        ; comando, word en offset 4
011c98: cmp  r0, #7              ; debe ser 7
011c9c: ldrne r1, =error         ; si no: error
011ca4: ldrb r0, [r2, #1]
011ca8: ldrb r1, [r2, #2]
011cac: orr  r0, r0, r1, lsl #8
011cb0: ldrb r1, [r2, #3]
011cb4: orr  r0, r0, r1, lsl #16
011cb8: ldrb r1, [r2, #4]
011cbc: orr  r1, r0, r1, lsl #24  ; dirección de 32 bits
011cc0: ldrb r0, [r2, #5]
011cc4: ldrb r3, [r2, #6]
011cc8: orr  r4, r0, r3, lsl #8   ; longitud de 16 bits
011ccc: cmp  r4, #64, #28         ; límite (~1024)
011cd0: bls  0x11ce4              ; si cabe
011ce4: mov  r3, #4
011cec: strb r3, [r0]             ; respuesta tipo 4
011cf0: ldrb r3, [r2, #1]
011cf4: strb r3, [r0, #1]         ; eco de la dirección
011d18: bl   0x83c4               ; ESCRITURA
011d34: bl   0x57b0               ; enviar respuesta
```

### Estructura deducida

```
offset  +0x00  ...
        +0x04  comando (word, little-endian) = 7
        +0x06  inicio del payload:
                 +1..+4  dirección (32 bits LE)
                 +5..+6  longitud (16 bits LE)
                 +7..    datos
```

**Problema:** no se logró reproducir el formato exacto que acepte el
firmware. Ver abajo.

---

## Intentos fallidos (documentados a propósito)

| Paquete enviado | Respuesta |
|---|---|
| `07` (solo el comando) | `Invalid Command` |
| `04 07 <addr32> <len16>` | `Invalid Command` |
| `00000000` + `07 00` + ceros | `Invalid Command` |
| `01000000` + `07 00` + ceros | `Invalid Command` |
| `04000000` + `07 00` + ceros | **`Invalid magic number`** |
| `04000000 0700` + `DEADBEEF` | `Invalid Command` |
| `04000000 0700` + `QCOM host` | `Invalid Command` |
| `04000000 0700` + `QCOM targ` | `Invalid Command` |
| `04000000 0700` + magic de partition | `Invalid Command` |

**Observación:** el único que llegó a una etapa distinta fue
`04000000 0700` solo, que respondió `Invalid magic number`. Pero al
agregarle cualquier cosa volvió a `Invalid Command`.

Eso sugiere que **el `0x04` del header era coincidencia**, no la estructura
correcta.

---

## Por qué no se siguió por fuerza bruta

Probar combinaciones a ciegas no escala: el espacio de formatos posibles es
enorme y cada intento puede resetear el stick.

**El camino correcto** es leer la función que **valida el magic de entrada**.
El firmware tiene el mensaje en `0x17e40`:

```
Invalid magic number
```

Siguiendo su referencia se llega al validador de paquetes entrantes, que es
**distinto** de `0x11c8c` (ese es el handler de escritura, que solo se
ejecuta después de que el paquete ya fue aceptado).

---

## Lo que esto aporta igual

Aunque el paquete de escritura no esté resuelto:

1. **El handshake está completo y funciona.** Cualquiera puede reproducirlo.
2. **La NAND está identificada** (`SAMSUNG_K9F1208d`) con su geometría.
3. **Se sabe qué comandos existen** (`0x04`, `0x08`) y qué error dan.
4. **El handler de escritura está desensamblado** con su estructura.
5. **El bug del `stty`** está documentado: sin eso, nada funciona.

Eso es más de lo que había público sobre este modelo.

---

## Para quien retome

1. Seguir la referencia al string `Invalid magic number` (`0x17e40`).
2. Desensamblar esa función: es el validador de paquetes entrantes.
3. De ahí sale el formato real del header.
4. Con el formato, usar el handler `0x11c8c` (ya documentado) para escribir.

El firmware está en [`firmware/nandprgcombined.mbn`](../firmware/).

Herramientas: [`tools/disasm.py`](../tools/disasm.py) y
[`tools/armpg.py`](../tools/armpg.py).
