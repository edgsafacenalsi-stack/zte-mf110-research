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

## Análisis del firmware: desalineación del desensamblado

Un problema metodológico que consumió tiempo y conviene documentar:

**El desensamblado ARM de este binario puede dar resultados falsos si la
alineación está corrida.** Leyendo bloques con `capstone.disasm(data[a:b], a)`
se obtienen instrucciones válidas sintácticamente pero **que no son el
código real**, si `a` no cae en un límite de instrucción.

Ejemplo real de esta investigación:

```
# MAL: 0x112a4 desalineado
0x112a4: mov r1, r7        ← parece válido
0x112a8: mov r0, #8        ← parece válido
0x112ac: bl  0x16b94       ← parece válido

# BIEN: leyendo dwords primero y verificando
0x112a4: e1a01007  mov r1, r7
0x112a8: e3a00008  mov r0, #8
0x112ac: eb001638  bl  0x16b94
```

En este caso coincidía, pero en otros tramos daba basura como
`addeq sl, r1, r8, asr #13` (instrucciones condicionales imposibles
en medio de una función).

**Recomendación:** antes de interpretar, verificar que el primer word de
la función sea un prólogo válido (`e92d40f0` = `push {r4-r7,lr}`, etc.)
y que no aparezcan instrucciones con condición `EQ` sueltas.

### Donde el análisis quedó

Se identificó una función en `0x111dc` que:

```
0x111dc: push {r4,r5,r6,r7,r8,lr}
0x111e0: mov  r5, r0              ; r5 = parámetro
0x111e4: ldr  r0, =flag
0x111ec: ldrb r0, [r0]
0x111f0: cmp  r0, #0
0x111f4: bne  0x112a4             ; ya inicializado
0x111f8: mov  r2, #0x20           ; 32
0x111fc: ldr  r1, =0x817db2       ; "QCOM fast download protocol host"
0x11200: add  r0, r5, #7          ; r5 + 7
0x11204: blx  memcmp
0x11208: cmp  r0, #0
0x1120c: ldrne r1, =error
```

**Esto sugiere que el magic va en el offset 7**, pero:

- **No se logró reproducir contra el stick.** Todos los intentos con
  header de 7 bytes dieron `Invalid Command`.
- **El hello que SÍ funciona** manda el magic **al principio** (offset 0).

Por lo tanto: **`0x111dc` probablemente no es la función que procesa
nuestro hello**, sino otra ruta del firmware (posiblemente el código que
el ARMPRG usa cuando él mismo actúa como host, o el manejo de un buffer
interno distinto).

**Conclusión:** la estructura del paquete de escritura **sigue sin
resolverse**, y el análisis estático por sí solo no alcanzó.

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
