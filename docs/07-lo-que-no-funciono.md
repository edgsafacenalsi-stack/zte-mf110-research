# 07 — Lo que NO funcionó

Registro deliberado de callejones sin salida. **Esto ahorra tiempo** a quien
intente lo mismo.

---

## 1. Fuerza bruta del código de desbloqueo

**Qué se intentó:** probar secuencialmente códigos de 2 bytes (65 536).

**Resultado:**
- 0 aciertos.
- A los ~291 comandos: `ERR: Window overrun detected...`
- El `0xC8` que apareció una vez fue un **falso positivo**.

**Por qué falla:** el código es criptográfico (RSA), no un PIN corto.
Ver [04](04-lock.md).

**No repetir.** Consume intentos y no lleva a nada.

---

## 2. `uhubctl` / corte de energía del puerto

**Objetivo:** sacar el stick de `0076` y que vuelva a `0031` limpio.

**Resultado:** el hub raíz reporta

```
wHubCharacteristics 0x000a → "No power switching"
```

**No hay conmutación de energía por software.** No se puede.

---

## 3. Atributo `disable` del puerto USB

**Objetivo:** lo mismo, por otra vía.

**Resultado:** `disable` sí desconecta el dispositivo, pero al reactivar
vuelve en el **mismo PID (`0076`)**, no en `0031`.

```
/sys/bus/usb/devices/usb1/1-0:1.0/usb1-port11/disable
```

**No sirve para resetear el modo.**

---

## 4. `AT+CLCK`

**Qué se esperaba:** el comando estándar GSM para control de bloqueo.

**Resultado:** es un **stub**. Siempre devuelve `0`, no hace nada.

```
AT+CLCK="PN"   →  ERROR (con SIM no autorizada)
```

**El comando existe pero no está implementado.**

---

## 5. `AT+ZCDRUN=E`

**Qué se esperaba:** entrar a modo download cambiando el VID/PID.

**Resultado:** activa un flag interno, pero **no cambia VID/PID**.
Se queda en `0031`.

---

## 6. Baipás por Sahara / EDL

**Qué se esperaba:** el camino moderno de Qualcomm para flashear.

**Resultado:** el stick responde `Invalid magic number` a cualquier
intento de handshake Sahara.

**El MF110 no usa Sahara.** Usa ARMPRG. Ver [06](06-protocolo-ARMPRG.md).

---

## 7. QPST 2.7.496 en Wine — instalación

Esto merece detalle porque **casi funciona**, lo que hace perder tiempo.

### 7.1 El instalador no completa

```
MSIEXEC ... /i QPST 2.7.msi
→ error 1603 en InstallFinalize
```

Sólo copia `QPSTService.exe` y abandona.

**Solución encontrada:** extraer el MSI del instalador y usar
`msiextract` (paquete `msitools`):

```bash
msiextract QPST_2.7_CAPTURED.msi
# → 154 archivos
```

### 7.2 El MSI está embebido y se borra

El instalador es un *bootstrapper* que extrae el MSI a
`%TEMP%\{GUID}\QPST 2.7.msi` y lo borra al terminar.

**Hay que copiarlo mientras MSIEXEC corre:**

```bash
find wineprefix/drive_c/users/*/AppData/Local/Temp -name "*.msi" -size +1M
```

### 7.3 Aplicación no arranca: faltan clases COM

```
err:ole:com_get_class_object class {73e704ea-...} not registered
```

**Solución:** convertir las tablas `Registry.idt` y `Class.idt` del MSI
a un `.reg` y registrarlo:

```bash
msidump -t -d msi_tables QPST_2.7_CAPTURED.msi
python3 tools/gen_com_reg.py
wine reg import qpst_com.reg
```

Y registrar las 19 DLLs COM con `regsvr32` (ver
[tools/gen_com_reg.py](../tools/gen_com_reg.py)).

Resultado: **QPSTConfig.exe arranca limpio, sin errores.**

### 7.4 El bloqueo real: "Add New Port"

```
QPST Configuration
Ports: (vacío)
[Add New Port] ← click → QPSTConfig.exe CRASHEA
```

Diálogo de crash de Wine. **Es un bug de Wine 11** en la enumeración de
puertos.

### 7.5 Aún con ttyUSB en 0076, no ve el puerto

Después del hallazgo de que `0076` puede exponer `ttyUSB0`
(ver [05](05-modo-download.md)), se mapeó:

```
wineprefix/dosdevices/com33 -> /dev/ttyUSB0
```

Y se inyectó en el registro:

```
HKCU\Software\Qualcomm\QPST Software Download\Settings
    MRU Port Name = COM33
    CEFS prtn MRUL\0 = ...\partition.mbn
    CEFS cefs MRUL\0 = ...\efs.mbn
```

**Resultado:** `Download.exe` abre, pero sigue diciendo
**`No Phone Connected`** y el combo de puerto está vacío.

**Conclusión:** QPST depende de la enumeración de puertos de Windows
(`SetupDiGetClassDevs`), que Wine no implementa para este caso.
No hay workaround por registro.

---

## 8. `Download.exe` por línea de comandos

**Qué se encontró:** el binario tiene soporte de argumentos

```
download_file: "%ls"
partition_file: "%ls"
partition_patch_file: "%ls"
```

**Resultado:** **no hay modo consola**. Con `-h` abre la GUI y espera.
`SDCommandLineParser` es para parsing interno de la GUI, no para
automatización.

---

## Resumen

| Vía | Por qué falla |
|---|---|
| Fuerza bruta | RSA + ventana limitada |
| `uhubctl` | hub sin power switching |
| `disable` USB | vuelve en el mismo PID |
| `AT+CLCK` | stub |
| `AT+ZCDRUN=E` | no cambia VID/PID |
| Sahara/EDL | protocolo equivocado |
| QPST instalación | MSI 1603 → resuelto con msiextract |
| QPST COM | registro manual → resuelto |
| **QPST puertos** | **crash / no enumera → SIN SOLUCIÓN en Wine** |
| QPST CLI | no existe |

**La única vía viva es reimplementar ARMPRG.** Ver [06](06-protocolo-ARMPRG.md).
