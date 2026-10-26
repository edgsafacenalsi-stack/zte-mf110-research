# 02 — Acceso DIAG (QCDM)

DIAG es el canal de diagnóstico de Qualcomm. Permite leer/escribir NV items,
y es la base de todo lo que se hizo después.

## El detalle que costó caro

**DIAG está en la interfaz 0**, no en la 3.

```
IFACE = 0
EP_OUT = 0x01
EP_IN  = 0x81
```

Antes de descubrirlo se probó contra la interfaz 3 (la AT) sin éxito.

## Framing

### Comandos (host → stick)

```
0x7E | payload | CRC16 (LE) | 0x7E
```

Con escapado HDLC: `0x7D → 0x7D 0x5D`, `0x7E → 0x7D 0x5E`.

### Respuestas (stick → host)

**Asimétrico:** la respuesta **no lleva `0x7E` al inicio**.

Eso hace que un parser naive falle al leer la primera respuesta y parezca
que el dispositivo no contesta.

## CRC16

CCITT, **reflejado**, little-endian:

```python
import crcmod
_crc = crcmod.mkCrcFun(0x11021, rev=True, initCrc=0, xorOut=0xFFFF)
```

## Autenticación

| Paso | Valor | Resultado |
|---|---|---|
| SPC | `000000` | aceptado |
| Password | `FF FF FF FF FF FF FF FE` | aceptado |

Con eso el canal queda en modo "servicio" y se pueden leer/escribir NV items.

## Ejemplo mínimo

Ver [tools/diag.py](../tools/diag.py):

```python
from diag import Diag

d = Diag()
d.open()            # reclama la interfaz 0
d.spc()             # SPC + password
print(d.nv_read(0)) # respuesta desescapada de NV item 0
d.close()
```

> **Limitación conocida:** el cliente incluido abre y autentica el canal
> DIAG de forma confiable, pero la lectura de NV items es **intermitente**.
> Las respuestas largas llevan separadores `0x7E` internos y hace falta
> sincronizar el contador de secuencia del módem.
>
> El volcado publicado en `research/` se hizo con un cliente más tolerante
> que reintentaba y resincronizaba. `tools/nv.py` reintenta, pero avisa
> cuántos items quedaron sin respuesta.
>
> **Esto no invalida el volcado**: los datos son reales. Simplemente el
> cliente simplificado de este repo no es tan robusto como el original.

## Entrar al modo download por DIAG

```
4B 10 01 00
```

Subsistema `0x10`, subcomando `1`. El stick re-enumera como `19d2:0076`.

## Subcomandos que respondieron

| Comando | Efecto |
|---|---|
| `4B 10 01 00` | Entrar a modo download |
| `0x01` (en 0076) | "Invalid magic number" |
| `0x07` (poke) | Eco con dirección, **no escribe realmente** |
| `0x08` (peek) | USBError |

## Referencias

- Código completo: [tools/diag.py](../tools/diag.py)
- Volcado NV: [research/nv_v2_0_999.json](../research/)
