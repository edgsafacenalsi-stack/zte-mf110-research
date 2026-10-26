# 10 — Cómo seguir

El trabajo quedó en un punto concreto. Esto es lo que hay que hacer,
en orden de menor a mayor esfuerzo.

---

## Paso 1 — Probar `DEADBEEF` como magic (30 min)

**La hipótesis más fuerte y no está probada.**

`DEADBEEF` aparece en el literal pool de `nandprgcombined.mbn` (`0x118`),
cargado al arrancar en `r1..rFE` como valor inicial.

```
7E | DE AD BE EF | ...payload... | CRC | 7E
```

Variantes a probar:

- `DEADBEEF` + tipo + longitud + payload
- `DEADBEEF` al final en vez del principio
- `DEADBEEF` como CRC (comparando con lo que devuelve el stick)

Un test rápido con [tools/dl76_crc_hunt.py](../tools/dl76_crc_hunt.py)
modificado.

**Cómo saber si funcionó:** la respuesta deja de ser `ERR: CRC invalid`.

---

## Paso 2 — Decodificar el campo `0e` de la respuesta (1 h)

La respuesta a un comando inválido fue:

```
0e "ERR: CRC invalid\n" 92 ff
```

- `0e` = 14
- `"ERR: CRC invalid"` = 16 caracteres
- `"ERR: CRC invalid\n"` = 17

**Ninguna coincide con 14.** Determinar qué cuenta exactamente:

- ¿palabras de 2 bytes? (17/2 = 8.5, no)
- ¿sin el prefijo `ERR: `? (13, cerca pero no)
- ¿algún campo que no es longitud?

Esto revela el formato de la respuesta, y por simetría parte del de entrada.

---

## Paso 3 — Buscar implementaciones libres de ARMPRG (2 h)

Existen implementaciones libres del protocolo ARMPRG (es de 2007):

- Buscar `"ARMPRG"` en repositorios de flasheo de módems Qualcomm viejos.
- Proyectos de la era MSM7x00 / MSM62xx.

**Ventaja:** si alguna funciona, no hay que reimplementar nada.

> ⚠️ **Ojo con una trampa:** el CRC que el ARMPRG valida **se calcula del
> lado del host** (QPST). Ver `QMSL_MSVC10R.dll`. Una implementación libre
> sólo sirve si trae ese mismo algoritmo.

---

## Paso 3 — QPST en Windows real (útil, pero ya no es la vía principal)

Sigue siendo válido si el objetivo es **flashear ya** sin entender por qué
funciona. Requiere:

- VirtualBox 7.2+ con **Extension Pack** (sin él no hay USB 2.0/3.0)
- Una ISO de Windows (7/10/11)
- Passthrough USB del stick en `19d2:0076`

**Por qué:** en Wine, "Add New Port" crashea y `Download.exe` queda en
`No Phone Connected`. Ver
[07](07-lo-que-no-funciono.md#7-qpst-27496-en-wine--instalación).

**Pero ya no es la única opción**: ver el Paso 3c.

---

## ⭐ Paso 3c — Identificar el modo 2 del Crypto Engine (la vía más prometedora)

Este es el paso pendiente más valioso. Ver
[doc 11](11-dll-qpst-y-crc-hardware.md).

El CRC del protocolo lo calcula el **bloque CE (Crypto Engine)** del
chipset, no software. La función `0x1679c` del firmware lo configura con
**modo 2**:

```
0x167d4  str r0, [r4, #4]      ; modo = 2
0x167e0  stm r2, {r0, r1, r5, r7}   ; modo, 0, len, ...
0x167e8  str r0, [r4, #0x1c]   ; dispara
```

### Qué buscar

En el kernel de Linux, driver del Crypto Engine de Qualcomm:

```
linux/drivers/crypto/qce/
```

Buscar:

1. Qué corresponde al **modo 2** en MSM6290 (o generación equivalente).
2. El **polinomio** usado en ese modo.
3. Reflejo de entrada/salida y valor inicial.
4. Tamaño de palabra (probablemente 32 bits, dado `str r0,[r4,#4]=2`).

### Cómo confirmar que se acertó

Una vez implementado en Python, generar el paquete Hello y enviarlo por
`/dev/ttyUSB0` en modo `0076` (ver [doc 05](05-modo-download.md)).

**Si deja de responder `ERR: CRC invalid`, el CRC es correcto.**

Los scripts para probar ya están hechos:
`tools/hello_magic.py` y `tools/hello_crc.py`.

---

## Paso 4 — Desensamblar completo con radare2 (hecho)

```bash
r2 -a arm -b 32 firmware/nandprgcombined.mbn
# dentro:
e io.va=false        # IMPORTANTE: usar offsets de archivo
aaa
afl
s 0x5068            # función de validación principal
pdf
```

> **Nota sobre r2:** con `-m 0x800028` r2 lee el offset equivocado. La base
> real es **`0x800000`**, y lo más confiable es `e io.va=false` y navegar
> por offset de archivo directamente.

### Lo que ya se encontró con radare2

| Offset | Qué es |
|---|---|
| `0x5068` | Validación principal del paquete |
| `0x5954` | Dispatcher: `ldrb r0,[r4,#2]`, `cmp #4/#5/#6` |
| `0x5a24` | Respuesta tipo 5 (`EF 02 01`) |
| `0x1a14c` | **Tabla de handlers** (offset `+0x4c` = validador) |
| `0x816c60` | Validador → `0x1650` (espera registro HW) |
| `0x16d5c` | Función maestra: `sl=0xb` = 11 fragmentos |
| `0x80c7d8` | Handler `+0x3c` → **driver UART** (`str [sl,#0x304]`) |

### ⚠️ El hallazgo que cambia todo

`ERR: CRC invalid` **no lo calcula el ARMPRG**. Lo calcula **QPST** y el
ARMPRG sólo lo compara contra el paquete recibido.

El código del ARMPRG que "valida" termina en un **registro de hardware UART**
(`str [sl, #0x304]`), no en un algoritmo de CRC.

**Consecuencia:** reimplementar el flasheo sin QPST exige reproducir el
algoritmo de **`QMSL_MSVC10R.dll`** (17 MB, sin símbolos, Windows x86), no
el del firmware. Ese es el verdadero bloqueo, y es más duro de lo que
parecía al principio.

La ruta más razonable pasa a ser **hacer correr QPST en un Windows real**
(máquina virtual), no reimplementarlo.

---

## Paso 5 — Reimplementar el flasheo (una vez resuelto el framing)

Con el framing resuelto, la secuencia (de los mensajes de error) es:

```
1. SET SECURITY MODE
2. PARTITION TABLE     ← enviar partition.mbn (464 bytes)
3. OPEN MULTI
4. OPEN (por partición)
5. WRITE (por página, 2048 bytes)
6. CLOSE
```

Datos que ya se tienen:

- Tamaño de página: probablemente `0x800` (2048), del switch `oemsbl`
- Tabla de particiones: decodificada en [08](08-firmware-re.md)
- Progreso: `page_bytes_user`, `block_pages`, `device_blocks`
- Archivos a escribir: `partition.mbn` + `efs.mbn`

---

## Advertencia sobre versiones

| Componente | Versión |
|---|---|
| Firmware del stick | `V1.0.0B03` |
| `efs.mbn` disponible | `V1.0.2B17` |

**Son distintas.** Flashear un EFS de otra versión puede dejar el stick
inutilizable. Si se llega a este paso, tener en cuenta el riesgo.

---

## Si el stick se brickea

La salida documentada es un **programador de NAND externo** (CH341A, el
negro) para leer/escribir la NAND directamente.

**Pero** el stick de esta investigación nunca se brickeó: todas las
pruebas fueron reversibles. Ver la sección de estado en el
[README](../README.md).

---

## Cómo contribuir

Si avanzás en alguno de estos pasos:

1. Abrí un issue describiendo qué probaste y el resultado (aunque sea negativo).
2. Si resolvés el framing, mandá el `pcap`/log de la secuencia.
3. **Documentá los callejones sin salida también.** Este repo existe en
   buena medida para que otros no repitan errores.
