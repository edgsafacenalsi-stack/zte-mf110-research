# 11 — El protocolo desde QPST: la DLL y el CRC de hardware

> **Este documento cierra la pregunta más importante del proyecto:**
> ¿de dónde sale el `ERR: CRC invalid` y cómo se resuelve?

Índice: [← Protocolo ARMPRG](06-protocolo-ARMPRG.md) · [Índice](00-INDICE.md) · [Cómo seguir →](10-como-seguir.md)

---

## Resumen en cinco líneas

1. La validación del ARMPRG **termina en hardware**, no en un algoritmo.
2. El **magic real** del protocolo es `"QCOM fast download protocol host"`.
3. `QMSL_MSVC10R.dll` **tiene 1949 funciones exportadas con nombre**.
4. El **CRC lo calcula el Crypto Engine** del chipset (bloque CE).
5. Por eso **ningún CRC de software coincide** — se probaron 228 variantes.

---

## Parte 1 — El magic del protocolo

### De dónde salió

Desensamblando `QLIB_DOWNLOAD_Hello` en `QMSL_MSVC10R.dll`:

```
0x2fcbd0  push ebp
0x2fccd3  mov  esi, [ebp+8]        ; handle
          ...
0x3000cf  mov  esi, 0x1086337C     ; ← puntero a la constante
0x3000d9  mov  ecx, 8
0x3000d7  rep movsd                ; copia 8 dwords = 32 bytes
0x3000dd  movsb                    ; +1
0x3000e3  push 0x20                ; longitud = 32
0x3000eb  call 0x11bd70            ; append al buffer
```

La constante en `0x1086337C` (RVA `0x86337C`, base de imagen `0x10000000`):

```
hex: 51434f4d206661737420646f776e6c6f61642070726f746f636f6c20686f7374
txt: "QCOM fast download protocol host"
```

**32 bytes exactos, sin terminador.**

### Verificación contra el hardware

Con el stick en modo `0076` y `/dev/ttyUSB0` disponible:

| Magic enviado | Framing | Respuesta |
|---|---|---|
| `9a1b7daa...` (partition.mbn) | HDLC | `Invalid Command` |
| `QCOM fast download protocol host` | raw | (silencio) |
| **`QCOM fast download protocol host`** | **HDLC** | **`ERR: CRC invalid`** |
| `QCOM...` + 3 bytes de versión | raw | (silencio) |

**El cambio de mensaje es la prueba.** `Invalid magic number` /
`Invalid Command` → `ERR: CRC invalid` significa que **el stick reconoce el
magic** y ahora falla en la etapa siguiente.

---

## Parte 2 — Estrutura del paquete

### Cómo arma QPST el Hello

```
append(MAGIC, 32)                 ; "QCOM fast download protocol host"
append_byte(iVersionNumber)       ; 1 byte
append_byte(iCompatibleVersion)   ; 1 byte
append_byte(iFeatureBits)         ; 1 byte
enviar()
```

### El buffer de envío (descubierto en `0x11bf00`)

```
memset(this + 0x0000, 0xAA, 0x2000)   ; buffer TX
memset(this + 0x2000, 0xBB, 0x2000)   ; buffer RX
[this + 0x4000] = 0x20000000          ; offset=0, capacidad=0x2000
[this + 0x4004] = 0                     ; índice de lectura
```

| Campo | Offset | Uso |
|---|---|---|
| TX buffer | `+0x0000` | 8192 bytes, se llena con `0xAA` al resetear |
| RX buffer | `+0x2000` | 8192 bytes, se llena con `0xBB` |
| write offset | `+0x4000` | word bajo |
| read index | `+0x4004` | byte |

Las funciones de append:

| Función | Qué agrega |
|---|---|
| `0x11bd70(buf, len)` | bloque |
| `0x11bc60(byte)` | 1 byte |
| `0x11bc90(word)` | 2 bytes |
| `0x11bcc0(dword)` | 4 bytes |

---

## Parte 3 — La API de QPST (1949 exports)

`QMSL_MSVC10R.dll` exporta **1949 funciones** con nombre. No es un binario
opaco: es un SDK.

### Firmas con parámetros (extraídas de los strings de log)

```
QLIB_DOWNLOAD_Hello( iVersionNumber, iCompatibleVersion, iFeatureBits )
QLIB_DOWNLOAD_Ping()
QLIB_DOWNLOAD_QFprom_Read( iRowAddress, iAddressType )
QLIB_DOWNLOAD_QFprom_Write( iRowAddress, iMSBBytes, iLSBBytes )
QLIB_AbortSW_DownloadOperation()
QLIB_QPHONEMS_SwitchToDownloadMode()
QLIB_GetLastSoftwareDownloadErrorInfo()
QLIB_UploadCEFS_File()
QLIB_DownloadCEFS_File()
QLIB_StartFactoryImageDownload()
QLIB_Set_QPHONEMS_Userdefined_Autoresend( bAutomaticResend, iTimeoutValueMS_ForAutoResend )
```

**1551 firmas completas** en total en el binario.

### La DLL carga en Wine (verificado)

Con Python embebido de Windows:

```
[+] DLL cargada
    [QLIB_DOWNLOAD_Hello]                    -> OK
    [QLIB_DOWNLOAD_Ping]                     -> OK
    [QLIB_QPHONEMS_SwitchToDownloadMode]     -> OK
    [QLIB_GetLastSoftwareDownloadErrorInfo]  -> OK
```

Dependencias: `KERNEL32`, `MSVCR100`, `MSVCP100`, `CRYPT32`, `bcrypt`,
`WS2_32`, `ole32`, `USER32`, `ADVAPI32`, `NTDLL`. **Ninguna exótica.**

---

## Parte 4 — El CRC es HARDWARE ⚠️

Este es el hallazgo que cierra la investigación.

### El bucle de validación en el firmware

En `nandprgcombined.mbn`, zona del mensaje `"checksum failed"`:

```
0x11850  ldr  r0, [sl]
0x11858  blx  r0                  ; obtiene longitud
0x1185c  ldr  r1, [fp, #0x24]     ; límite
0x11860  add  r0, r4, #128, #28   ; r4 + 0x800  (2048)
0x11864  cmp  r0, r1
0x11868  subhs r5, r1, r4         ; resto
0x1186c  movlo r5, #128, #28      ; trozo de 0x800
0x11870  mov  r2, r5              ; len
0x11874  mov  r1, sb
0x11878  mov  r0, r8
0x1187c  bl   #0x1679c            ; ← CALCULA
0x11880  and  r7, r0, #0xff
0x11884  cmp  r7, #1
0x11888  beq  #0x1189c            ; éxito
```

**Procesa en bloques de 2048 bytes (`0x800`).**

### La función de cálculo `0x1679c`

```
0x1679c  push {r3-r7,lr}
0x167a4  ldr  r0, =0x0081f1dc     ; flag global
0x167ac  ldrb r0, [r0]
0x167d0  ldr  r4, =0x0083cf20     ; ← registros del motor de CRC
0x167c8  mov  r0, #2
0x167d4  str  r0, [r4, #4]        ; MODO = 2
0x167d8  str  r1, [r4]            ; RESET
0x167dc  add  r2, r4, #8
0x167e0  stm  r2, {r0, r1, r5, r7}  ; configura modo, 0, LEN, buffer
0x167e4  mov  r0, #1
0x167e8  str  r0, [r4, #0x1c]     ; ← DISPARA
0x167ec  str  r6, [r4, #0x20]     ; dirección del buffer
0x167f0  bl   #0x333c             ; espera
0x167f4  ldr  r0, [r4, #0x1c]     ; ← LEE EL RESULTADO
```

### Qué significa

Ése no es un algoritmo. Es un **acelerador de hardware**: el bloque
**Crypto Engine (CE)** del MSM6290.

| Dirección | Operación |
|---|---|
| `str [r4,#4] = 2` | selecciona modo |
| `stm {modo, 0, len, ...}` | configura |
| `str [r4,#0x1c] = 1` | dispara |
| `ldr [r4,#0x1c]` | lee resultado |

**El polinomio y la configuración viven en el hardware, no en el firmware.**

---

## Parte 5 — Por qué 228 pruebas de CRC fallaron

Con el magic correcto se probaron:

| Variante | Resultado |
|---|---|
| CRC16 CCITT (false/true, LE/BE) | `CRC invalid` |
| CRC16 XMODEM | `CRC invalid` |
| CRC16 Kermit, Kermit-FFFF, X25 | `CRC invalid` |
| CRC16 IBM, Modbus, ARC | `CRC invalid` |
| Suma de 16 bits (LE/BE) | `CRC invalid` |
| Sin CRC | `CRC invalid` |
| 6 payloads distintos × 19 variantes × 2 framings | **228 pruebas** |

**Todas dieron `CRC invalid`.** El patrón constante:

```
raw   → silencio       (el parser ni lo procesa)
hdlc  → CRC invalid    (lo procesa y rechaza)
```

El **framing `0x7E` + escapado es correcto**. El rechazo es exclusivamente
por el valor del checksum.

**Conclusión: ningún CRC de software va a coincidir, porque el valor lo
produce el CE con su propia configuración.**

---

## Parte 6 — Qué queda por hacer

### Ruta abierta: identificar el modo 2 del CE

El bloque CE de Qualcomm está documentado en el kernel de Linux:

```
linux/drivers/crypto/qce/
```

Buscar qué corresponde al modo `2` para esta generación de MSM. Eso daría:

- el polinomio
- el tamaño de palabra (32 bits)
- el reflejo de entrada/salida
- el valor inicial

Una vez identificado, el cálculo se reimplementa en Python y se puede
generar el paquete Hello válido.

### Ruta cerrada

- ❌ Probar más variantes de CRC software
- ❌ Depender de la DLL para el algoritmo (no lo tiene)
- ❌ Sahara/EDL

---

## Nota importante para quien retome

**Me equivoqué durante la investigación** al afirmar que el CRC dependía de
`QMSL_MSVC10R.dll`. La DLL **configura** el hardware y recibe el resultado,
pero **no calcula** el CRC en software.

Por eso la búsqueda del algoritmo en la DLL no podía dar frutos.

**El lugar correcto donde mirar es el driver `qce` del kernel Linux etiquetado
para MSM de esa generación.**

---

## Herramientas

| Script | Qué hace |
|---|---|
| [`tools/hello_magic.py`](../tools/hello_magic.py) | Prueba el magic real contra el stick |
| [`tools/hello_crc.py`](../tools/hello_crc.py) | Barrido de 228 variantes de CRC |
| [`tools/dl76.py`](../tools/dl76.py) | Entrada a `0076` y envío HDLC |
| [`tools/disasm.py`](../tools/disasm.py) | Desensambla `nandprgcombined.mbn` |

## Evidencia cruda

| Archivo | Contenido |
|---|---|
| `firmware/nandprgcombined.mbn` | El ARMPRG completo |
| Ver [firmware/README.md](../firmware/README.md) | Checksums del resto |

La `QMSL_MSVC10R.dll` **no se distribuye** (17 MB, material de Qualcomm).
Los offsets y desensamblados de este documento están documentados arriba
para que se puedan reproducir si alguien tiene el QPST original.
