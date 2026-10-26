# 11 — El protocolo desde QPST y el CRC real

Índice: [← Protocolo ARMPRG](06-protocolo-ARMPRG.md) · [Índice](00-INDICE.md) · [Cómo seguir →](10-como-seguir.md)

> ⚠️ **Corrección importante.** Una versión anterior de este documento
> afirmaba que el CRC del protocolo lo calculaba el *Crypto Engine* del
> hardware. **Era incorrecto.** La sección
> [Por qué me equivoqué](#por-qué-me-equivoqué) explica el error.

---

## ✅ Verificado en hardware — HANDSHAKE COMPLETO

Probado contra el stick en modo `0076`. **Funciona.**

### Paquete enviado

```
7e 01 51434f4d206661737420646f776e6c6f61642070726f746f636f6c20686f7374 030309 c632 7e
   │  └────────── "QCOM fast download protocol host" ──────────┘ │││ │
   │                                                             │││ └── featureBits 0x09
   │                                                             │└┴──── versión/compat 0x03
   └──────────────────────────────────────────────────────────────────── tipo 0x01 = HELLO
```

### Respuesta del stick (576 bytes)

```
02 51434f4d...74617267 03 02 00 04 00 00 00 00 00 00 0f
│  └─ "QCOM fast download protocol targ" ─┘ │  │  │
│                                           │  │  └── feature bits
│                                           │  └───── compatible 0x02
│                                           └──────── versión 0x03
└────────────────────────────────────────────────────── tipo 0x02 = OK

53 41 4d 53 55 4e 47 5f 4b 39 46 31 32 30 38 64
└──────────── "SAMSUNG_K9F1208d" ────────────┘

00 80 00 00      ← 0x8000 = 32768
00 08 00 00 ...  ← 0x800 = 2048  (repetido: mapa de páginas/bloques)
```

### 🔑 La clave: `stty raw -iexten -echo`

**Este fue el bloqueo silencioso de toda la investigación.**

Sin configurar el TTY, el driver `option` **procesa los bytes**:
- Los delimitadores `0x7E` se corrompen
- Las respuestas se cortan a 2 bytes (`02 00`)
- Los comandos "funcionan" a veces y a veces no

Con el TTY en modo `raw`, **todo funciona de forma confiable**:

```python
os.system(f"stty -F {port} raw -iexten -echo")
```

Es exactamente lo que hace `qdloader`:

```perl
system "/bin/stty raw -iexten -echo < $tty";
```

### Hardware del stick identificado

| Parámetro | Valor |
|---|---|
| **NAND** | **Samsung K9F1208** |
| Página | **2048 bytes** (`0x800`) |
| Bloque | **32768 bytes** (`0x8000`) |
| Protocolo del target | **v3.2** |

**Estos son datos leídos del silicio**, no del firmware descargado.

### Prueba de que el CRC es el correcto

| Variante | Resultado |
|---|---|
| Con escape HDLC | ✅ respuesta completa |
| Sin escape | ✅ respuesta completa |
| Doble `0x7E` inicial | ✅ respuesta completa |
| Sin `0x7E` final | ✅ respuesta completa |
| **CRC sin `swap16`** | ❌ `ERR: CRC invalid` |
| **CRC little-endian** | ❌ `ERR: CRC invalid` |

### Lo que sigue pendiente

| Comando | Resultado |
|---|---|
| `0x07` requestParams | silencio con el TTY en modo cocinado; **reintentar con `stty raw`** |
| `0x03`–`0x06`, `0x0C` | rechazados |
| `0x07` (sin raw) | **reset del stick** |

La secuencia siguiente de `qdloader`:

```
0x07        → requestParams  (respuesta tipo 0x08)
0x15        → closeFlush     (respuesta 0x16)
0x17 0x01   → secureMode     (respuesta 0x18)
```

---

## Resumen

1. El **magic** del host es `"QCOM fast download protocol host"` (32 bytes).
2. El **magic que responde el target** es `"QCOM fast download protocol targ"`.
3. El **CRC es software**, del lado del host: CRC-16 CCITT reflejado,
   `init=0`, `xorOut=0xFFFF`, y luego **swap de bytes**.
4. **El paquete Hello completo** (verificado byte a byte contra la
   implementación de referencia):

```
01 51434f4d206661737420646f776e6c6f61642070726f746f636f6c20686f7374 03 03 09 c632
│  └────────── "QCOM fast download protocol host" ──────────┘  │  │  │  └crc
│                                                              │  │  └─ featureBits
│                                                              │  └──── compatible
└─ tipo de comando (0x01 = HELLO)                              └─────── versión
```

5. Todo está implementado en [`tools/armpg.py`](../tools/armpg.py).

### Comandos del protocolo

| Byte | Comando | Formato |
|---|---|---|
| `0x01` | HELLO | `<0x01> <magic32> <ver> <compat> <feat>` |
| `0x02` | respuesta OK (del target) | `<0x02> <magic32> ...` |
| `0x0D` | ERROR | `<0x0D> ... <mensaje>` |
| `0x0E` | mensaje de texto | `<0x0E> <texto>` |
| `0x0F` | WRITE | `<0x0F> <addr32> <len16> <datos>` |
| `0x06` | pedir versión | `<0x06>` |

La respuesta a `0x0F` exitoso es un único byte **`0x02`**.

---

## Fuente: `jcsullins/qdloader`

La implementación de referencia en código abierto es:

```
https://github.com/jcsullins/qdloader
```

Es un cliente Perl del protocolo Qualcomm, del proyecto de investigación
`[R&D][QUALCOMM] Using QDL, EHostDL and DIAG interfaces` (XDA), que a su vez
se basa en la spec publicada por Qualcomm.

### El código que importa

```perl
sub setupPacket {
    my $packet = shift;
    my $crc = swap16( crc( 0xffff, $packet ) );
    return deserialize( "7e "
          . serialize( escape( $packet . deserialize( serial16($crc) ) ) )
          . " 7e" );
}

sub crcByte {
    my $crc = shift;
    my $c   = shift;
    return ( ( $crc >> 8 ) & 0xffff ) ^ $crcTable[ ( $crc ^ $c ) & 0xff ];
}

sub crc {
    my $crc    = shift;
    my $buffer = shift;
    foreach ( unpack( 'C*', $buffer ) ) { $crc = crcByte( $crc, $_ ); }
    return ~$crc & 0xffff;
}
```

### El paquete Hello completo (de `writeMagic`)

```perl
return undef
  if (
    !sendPacket(
        $fd,
        deserialize(
"01 51 43 4f 4d 20 66 61 73 74 20 64 6f 77 6e 6c 6f 61 64 20 70 72 6f 74 6f 63 6f 6c 20 68 6f 73 74 03 03 09"
        )
    )
  );
```

Desglosado:

| Bytes | Significado |
|---|---|
| `01` | tipo de comando: HELLO |
| `51 43 4f 4d ... 68 6f 73 74` | `"QCOM fast download protocol host"` |
| `03` | versión |
| `03` | versión compatible |
| `09` | feature bits |

### La respuesta esperada

```perl
if ( scalar @responseBytes > 35 && $responseBytes[0] == 0x02 ) {
    my $magicCodeCheck = "QCOM fast download protocol targ";
    my $magicCodeRecvd = substr( $response, 1, 32 );
    if ( $magicCodeRecvd eq $magicCodeCheck ) { ... }
}
```

> **Nota:** el *host* envía `...host`, el *target* responde `...targ`.
> Son distintos a propósito.

### La escritura de bloques (de `writeChunk`)

```perl
sendPacket( $fd, deserialize(
    "0f " . serial32($address) . " " . serial16($length) . " " . serialize($chunk)
) );
...
if ( scalar @responseBytes != 1 || $responseBytes[0] != 2 ) { error }
```

| Campo | Tamaño | Orden |
|---|---|---|
| `0x0F` | 1 | — |
| address | 4 | big-endian |
| length | 2 | big-endian |
| datos | N | — |

**ACK:** un único byte `0x02`.

---

## El CRC, verificado

### Implementación en Python

```python
import crcmod, struct

_crc = crcmod.mkCrcFun(0x11021, rev=True, initCrc=0x0000, xorOut=0xFFFF)

def swap16(v):
    return ((v << 8) | (v >> 8)) & 0xFFFF

def crc16(payload):
    return swap16(_crc(payload))
```

### Verificación cruzada con el Perl original

| Implementación | CRC de `"QCOM fast download protocol host"` |
|---|---|
| Perl (`qdloader`) | `0x995C` |
| Python (arriba) | `0x995C` ✅ |

**Coinciden exactamente.**

### Paquete resultante

```
7e 51434f4d206661737420646f776e6c6f61642070726f746f636f6c20686f7374 995c 7e
   └────────────── "QCOM fast download protocol host" ──────────────┘ └crc┘
```

---

## Framing

```
0x7E | escape( payload + CRC_BE ) | 0x7E
```

| Byte | Escape |
|---|---|
| `0x7E` | `0x7D 0x5E` |
| `0x7D` | `0x7D 0x5D` |

El CRC se serializa **big-endian** (`serial16` del Perl).

---

## Estructura del paquete (de la ing. inversa de la DLL)

Los offsets internos que sacamos de `QMSL_MSVC10R.dll` siguen siendo
válidos como **modelo del buffer de QPST**:

| Campo | Offset | Nota |
|---|---|---|
| TX buffer | `this+0x0000` | 8192 bytes |
| RX buffer | `this+0x2000` | 8192 bytes |
| write offset | `this+0x4000` | |
| read index | `this+0x4004` | |

Y la API de QPST (`QLIB_*`) tiene **1949 exports con nombre**, de los
cuales se extrajeron **1551 firmas** con parámetros documentados:

```
QLIB_DOWNLOAD_Hello( iVersionNumber, iCompatibleVersion, iFeatureBits )
QLIB_DOWNLOAD_QFprom_Read( iRowAddress, iAddressType )
QLIB_DOWNLOAD_QFprom_Write( iRowAddress, iMSBBytes, iLSBBytes )
QLIB_UploadCEFS_File()
QLIB_DownloadCEFS_File()
QLIB_StartFactoryImageDownload()
```

Detalle de esa parte en el [anexo](#anexo-la-api-de-qpst).

---

## Por qué me equivoqué

Vale la pena documentarlo porque es un error **metodológicamente
instructivo**.

### Lo que vi

En `nandprgcombined.mbn`, la función que valida los bloques de datos:

```
0x1679c  push {r3-r7,lr}
0x167d4  str  r0, [r4, #4]        ; modos
0x167e0  stm  r2, {r0, r1, r5, r7}
0x167e8  str  r0, [r4, #0x1c]     ; ← parece "disparar"
0x167ec  str  r6, [r4, #0x20]     ; dirección del buffer
0x167f0  bl   #0x333c             ; espera
0x167f4  ldr  r0, [r4, #0x1c]     ; ← parece "leer resultado"
```

### Lo que concluí

"Es un acelerador de hardware: escribe un registro, dispara, lee el
resultado. Por eso ningún CRC de software coincide."

### Lo que realmente era

Un **motor de checksum por DMA** que el bootloader usa para validar
bloques de imagen **>grandes** durante el flasheo. No es el CRC del
protocolo de paquetes, que corre en el **host**.

### Por qué el error se mantuvo

El patrón `str rX, [reg]` / `bl` / `ldr rX, [reg]` **es** típico de
hardware. Pero también lo es de **cualquier rutina de memoria con estado**
que use un registro de periférico para DMA.

**La confirmación nunca llegó porque no la busqué del lado correcto:**
asumí que el host era el que no tenía el algoritmo, cuando el que carece
de él es el firmware.

### La lección

Cuando 228 pruebas sistemáticas fallan con **el mismo mensaje exacto**,
no es que "el método es imposible": es que **algún supuesto de base está
mal**. En este caso el supuesto era `init=0`.

**La combinación correcta (`init=0x0000` + `xorOut=0xFFFF` + `swap`) no
estaba en ninguna de las 19 variantes que probé**, porque las agrupé
mal: usé `init=0xFFFF` con `xorOut=0x0000` y `init=0` con `xorOut=0`,
nunca la mezcla.

---

## Herramientas

| Script | Qué hace |
|---|---|
| [`tools/armpg.py`](../tools/armpg.py) | **Cliente con el CRC correcto** |
| [`tools/hello_magic.py`](../tools/hello_magic.py) | Prueba del magic (histórico) |
| [`tools/hello_crc.py`](../tools/hello_crc.py) | Las 228 pruebas que fallaron (histórico) |
| [`tools/dl76.py`](../tools/dl76.py) | Entrada a `0076` |
| [`tools/disasm.py`](../tools/disasm.py) | Desensamblado del firmware |

---

## Anexo: la API de QPST

### La DLL carga en Wine

Con Python embebido de Windows, `ctypes.WinDLL` carga
`QMSL_MSVC10R.dll` y resuelve los exports:

```
[+] DLL cargada
    [QLIB_DOWNLOAD_Hello]                    -> OK
    [QLIB_DOWNLOAD_Ping]                     -> OK
    [QLIB_QPHONEMS_SwitchToDownloadMode]     -> OK
    [QLIB_GetLastSoftwareDownloadErrorInfo]  -> OK
```

### Dependencias

`KERNEL32`, `MSVCR100`, `MSVCP100`, `CRYPT32`, `bcrypt`, `WS2_32`,
`ole32`, `USER32`, `ADVAPI32`, `NTDLL`. Ninguna exótica.

> **La DLL no se distribuye en este repo** (17 MB, material de Qualcomm).
> Los offsets documentados permiten reproducir el análisis con el QPST
> original.
