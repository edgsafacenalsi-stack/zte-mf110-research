# ZTE MF110 — Red teaming sobre un módem USB bloqueado

Investigación de ingeniería inversa sobre el **ZTE MF110** (Personal Argentina),
un módem USB que trae **SIM-lock** de operador. El objetivo era liberarlo
sin pagar herramientas comerciales (DC-Unlocker), usando solo el hardware,
el firmware público y Linux.

**Estado: NO desbloqueado.** Pero el camino quedó mucho más claro que al
inicio, y el punto exacto donde se traba está identificado.

> Este repo es una bitácora técnica. Todo se hizo sobre un stick propio,
> declarado prescindible, sin acceso a datos de terceros.

---

## Qué es el dispositivo

| Dato | Valor |
|---|---|
| Modelo | ZTE MF110 (HSDPA/HSUPA) |
| Chipset | Qualcomm **MSM6290** |
| Firmware | `BD_P671A2V1.0.0B03` |
| VID:PID normal | `19d2:0031` |
| VID:PID download | `19d2:0076` |
| VID:PID transitorio | `19d2:2000` (reset / re-enumeración) |
| SIM-lock | MCC/MNC — detectado `72234` (Personal) y `722310` (Claro) |

El lock **no** es una contraseña. El firmware valida el código NCK contra una
**clave pública RSA** almacenada en la partición `SIM_SECURE`. Por eso calcular
el NCK desde el IMEI es imposible: no hay función que lo derive.

---

## Resumen de los hallazgos

### 1. El lock no es reversible por fuerza bruta

- `AT+ZNCK?` → `5` significa **5 intentos intactos**.
- Se identificó el punto de parcheo en `amss.mbn`: `0xe30aa8: 13 d0` (BEQ) → `13 e0`.
- Se descartó la fuerza bruta: el buffer del bootloader se llena
  tras ~291 comandos (`Window overrun`).

### 2. El modo download (`0076`) **habla un protocolo documentado**

Esto es el hallazgo central del repo. El stick, en modo download, ejecuta
**Qualcomm ARMPRG v14.00.00** y **responde en texto plano** por el puerto serie:

```
ERR: CRC invalid
ERR: Window overrun detected...
Invalid magic number
No security mode received before partition table
No partition table received before open multi
```

Todos esos mensajes viven en `nandprgcombined.mbn` (incluido en
[firmware/](firmware/)).

### 3. El modo download **expone un ttyUSB** si se entra de la forma correcta

Este es un hallazgo que **contradice la documentación previa** (y nuestro
propio intento inicial):

| Cómo se entra a `0076` | ¿Hay `/dev/ttyUSB*`? |
|---|---|
| Con el blob de autenticación ZXIC solo | **No** (solo endpoint USB crudo) |
| Enviando un paquete de 1216 bytes tras el handshake | **Sí** (`/dev/ttyUSB0`, driver `option`) |

Eso abre la puerta a usar herramientas serie estándar en vez de libusb.

### 4. El CRC lo calcula el **hardware**, no un algoritmo

Es el hallazgo que cierra la pregunta central del proyecto.

- El **magic real** del protocolo es `"QCOM fast download protocol host"`
  (32 bytes). Confirmado contra el stick: el error cambia de
  `Invalid magic number` a `ERR: CRC invalid`.
- Se probaron **228 variantes de CRC software**: ninguna coincide.
- La razón: en `nandprgcombined.mbn`, la función `0x1679c` **dispara el
  Crypto Engine** del chipset y lee el resultado de un registro.

```
0x167e8  str r0, [r4, #0x1c]   ; dispara el cálculo en hardware
0x167ec  str r6, [r4, #0x20]   ; dirección del buffer
0x167f4  ldr r0, [r4, #0x1c]   ; lee el resultado
```

**Ningún CRC de software va a coincidir.** Para resolverlo hay que
identificar el modo 2 del bloque CE del MSM6290 (documentado en el driver
`qce` del kernel Linux).

Detalle completo en
[docs/11-dll-qpst-y-crc-hardware.md](docs/11-dll-qpst-y-crc-hardware.md).

---

## Estructura del repo

```
docs/       Documentación técnica por tema
tools/      Scripts Python (DIAG, NV, protocolo 0076, sondeo de CRC)
firmware/   nandprgcombined.mbn (ARMPRG) + checksums del resto
research/   Volcados NV, perfiles de SIM, resultados de pruebas
```

Empezá por [docs/00-INDICE.md](docs/00-INDICE.md).

---

## Estado de verificación

Probado contra hardware real (stick sano, `ZSEC 2,1`):

| Script | Estado |
|---|---|
| `tools/at.py` | ✅ verificado |
| `tools/partition_parse.py` | ✅ verificado |
| `tools/disasm.py` | ✅ verificado |
| `tools/strings_scan.py` | ✅ verificado |
| `tools/diag.py` | ⚠️ abre y autentica; lectura NV intermitente |
| `tools/nv.py` | ⚠️ depende de lo anterior; reintenta |
| `tools/dl76.py` | ⚠️ requiere entrar a `0076`; no probado de punta a punta |
| `tools/dl76_crc_hunt.py` | ✅ usado contra hardware |
| `tools/hello_magic.py` | ✅ verificado — magic aceptado por el stick |
| `tools/hello_crc.py` | ✅ verificado — 228 pruebas, todas `CRC invalid` |

Las limitaciones están explicadas en cada documento, no escondidas.

---

## Lo que NO funcionó (y por qué)

Esto está documentado a propósito: evita que otros repitan el trabajo.

| Vía | Resultado |
|---|---|
| `AT+ZNCK` / códigos conocidos | Rechazados, sólo consume intentos |
| Fuerza bruta de 2 bytes | 65 536 intentos sin acierto; `Window overrun` |
| `uhubctl` para cortar energía | El hub raíz **no tiene power switching** |
| Atributo `disable` del puerto | Reconecta en `0076`, no vuelve a `0031` |
| QPST 2.7.496 en Wine — instalación | MSI falla (`1603`), se resuelve con `msiextract` + registro COM manual |
| QPST en Wine — detección de puerto | **"Add New Port" crashea** QPSTConfig bajo Wine 11 |
| QPST en Wine — `Download.exe` | Abre GUI, nunca ve el puerto (`No Phone Connected`) |
| QPST CLI | No existe modo consola; abre GUI siempre |

Ver [docs/07-lo-que-no-funciono.md](docs/07-lo-que-no-funciono.md) para el detalle.

---

## Estado del stick al cerrar la sesión

- PID `19d2:0031` restaurado ✅
- `AT+ZSEC?` → `2,1` (sin cambios)
- `AT+ZNCK?` → `5` (intentos intactos)
- **Sin brick.** Todas las pruebas fueron reversibles.

---

## Licencia y límites

Los scripts son **MIT**. `nandprgcombined.mbn` es material de
**Qualcomm Incorporated** (copyright 2007), incluido únicamente con fines
de investigación e interoperabilidad. El resto del firmware no se
distribuye acá: ver [firmware/README.md](firmware/README.md) para checksums
y origen.

**Esto es investigación sobre hardware propio.** Intentar lo mismo con un
dispositivo ajeno o con datos de terceros no es el objetivo de este repo.
