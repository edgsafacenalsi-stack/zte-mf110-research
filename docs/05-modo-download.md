# 05 — Modo download `0076`

El modo download es donde vive el flasheo. Llegar acá fue el trabajo de
varias sesiones.

## Cómo se entra

### Vía DIAG (por software)

```
AT / DIAG autenticado  →  4B 10 01 00  →  stick re-enumera como 19d2:0076
```

Ver [tools/dl76.py](../tools/dl76.py) (`enter_download()`).

### Vía blob de autenticación ZXIC

Existe un blob de 137 bytes (`qsc62xx_unlocker`) que el stick acepta en
modo `0031` y que lo lleva a `0076`.

**Limitación:** modifica el estado del bootloader de forma **no
reproducible**. No sirve como método confiable.

## 🔑 Hallazgo: `0076` puede exponer un ttyUSB

Esto **contradice nuestro propio intento inicial** y la documentación
que se encuentra normalmente:

| Entrada a `0076` | `/dev/ttyUSB*` | Driver |
|---|---|---|
| Blob ZXIC solo | ❌ | — |
| After handshake + **paquete de 1216 bytes** | ✅ `ttyUSB0` | `option` |

### Cómo se produce

1. Entrar a `0076` por DIAG.
2. Enviar el comando HDLC de 1216 bytes (`cmd 1` + 1215 ceros en nuestro caso).
3. El dispositivo **no** re-enumera, sino que queda en `0076` **con el
   puerto serie posteado por el driver `option`**.

Confirmación con udev:

```
DEVPATH=.../1-12:1.0/ttyUSB0/tty/ttyUSB0
ID_USB_DRIVER=option
ID_MODEL=ZTE_CDMA_Technologies_MSM
```

### Por qué importa

- Se puede hablar con el bootloader **por serie estándar** (`os.write`),
  sin libusb.
- Abre la posibilidad de usar herramientas serie normales.
- **No** arregla por sí solo a QPST (ver [07](07-lo-que-no-funciono.md)),
  porque QPST seguía sin enumerar el puerto.

## Qué responde el stick

Una vez en `0076` con tty, el bootloader **responde en texto plano**:

```
ERR: CRC invalid
```

Ese mensaje es la clave de todo: significa que **el framing llega**, pero
el CRC no es el esperado. Detalle en [06](06-protocolo-ARMPRG.md).

## Estructura de la respuesta observada

```
<basura previa>
92 ff                    ← 2 bytes de control
7e 7e                    ← delimitadores vacíos
0e                       ← longitud (14)
"ERR: CRC invalid\n"     ← mensaje
92 ff                    ← mismo par de control
7e 7e                    ← cierre
0e "ERR: CRC invalid\n" 92 ff 7e 7e   ← se repite ~300 veces
```

**Nota:** el `0e` es 14, y `"ERR: CRC invalid"` mide 16 caracteres.
La longitud no cuadra con el mensaje completo — posiblemente `0e` cuenta
otra cosa (palabras, o sin el `ERR:`).

## NADA de Sahara/EDL

Es importante decirlo porque es el camino obvio:

```
Sahara  → "Invalid magic number"
```

El MF110 **no** usa la cadena de boot de Qualcomm moderna.
Usa **ARMPRG**, que es la generación anterior.

## Riesgo

Cada comando enviado en `0076` puede:

- Re-enumerar el stick (`0076` → `2000` → `0031`), o
- Dejarlo esperando más datos (se queda en `0076`)

Ninguna prueba hecha en este repo produjo brick, pero **el comando 4 es
escritura en NAND** y no se ejecutó a propósito.
