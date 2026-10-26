# Estado del stick y cómo recuperarlo

Información práctica para quien esté experimentando: **cómo saber si el
stick está sano y cómo volver a un estado conocido.**

---

## Estados posibles

| VID:PID | Estado | ttyUSB | Cómo salir |
|---|---|---|---|
| `19d2:0031` | **Normal** (sano) | `ttyUSB0/1/2` | — |
| `19d2:0076` | Download | `ttyUSB0` (si se entró bien) | Reconectar USB |
| `19d2:2000` | Transitorio | ninguno | Espera ~1-2 s |

---

## Verificar que está sano

```bash
lsusb | grep 19d2
# esperado: ID 19d2:0031

python3 tools/at.py 'AT' 'AT+ZSEC?' 'AT+ZNCK?'
```

Salida esperada:

```
>>> AT+ZSEC?
    +ZSEC: 2,1
    OK
>>> AT+ZNCK?
    +ZNCK: 5
    OK
```

| Valor | Significado |
|---|---|
| `+ZSEC: 2,1` | SIM no autorizada (bloqueado) — **estado normal si no está desbloqueado** |
| `+ZSEC: 3,0` | SIM autorizada |
| `+ZNCK: 5` | **5 intentos restantes** — no se consumió ninguno |

**Si `ZNCK` bajó de 5, algún intento de desbloqueo consumió un turno.**

---

## Si quedó en `0076`

Suele resolverse solo. El stick se resetea tras un error grave:

```bash
sleep 5
lsusb | grep 19d2
```

Si sigue en `0076`:

1. **Físicamente desconectar y reconectar** el stick (lo más confiable).
2. El atributo `disable` del puerto lo devuelve en `0076`, no en `0031`.

```bash
# NO resuelve: vuelve en el mismo modo
echo 1 > /sys/bus/usb/devices/usb1/1-0:1.0/usb1-portN/disable
echo 0 > /sys/bus/usb/devices/usb1/1-0:1.0/usb1-portN/disable
```

---

## Cómo entrar a `0076` (para pruebas)

```bash
# 1. verificar que está sano en 0031
python3 tools/at.py 'AT+ZSEC?'

# 2. entrar
python3 - <<'EOF'
import sys, time
sys.path.insert(0, 'tools')
import dl76
ok, sec = dl76.at_check()
print("sano:", ok, sec)
EOF
```

O con el helper directo:

```bash
python3 tools/dl76.py one 1
```

> **Nota:** `dl76.py one 1` corre una comprobación de integridad antes y
> después. Si el pre-chequeo falla, aborta sin tocar el stick.

---

## Qué ocurre al enviar comandos en `0076`

| Respuesta del stick | Qué significa |
|---|---|
| `Invalid magic number` | Los primeros bytes no son un magic conocido |
| `Invalid Command` | El magic se reconoció pero el tipo de comando no |
| `ERR: CRC invalid` | El comando y el magic están bien; el checksum no |
| (silencio) | El framing no llegó al parser |
| Re-enumeración USB | El stick reseteó (revisar `lsusb`) |

**Ninguna respuesta observada en este proyecto dejó el stick inutilizable.**
Todas las pruebas fueron reversibles con una reconexión.

---

## Riesgo real

El único comando peligroso es el de **escritura en NAND** (comando 4 en el
dispatcher del ARMPRG, `0x5958`). Los scripts incluidos **no lo ejecutan**.

Si se llega a implementar el flasheo, recordar:

- `amss.mbn` es el baseband: escribirlo mal = brick del equipo.
- El `efs.mbn` disponible es `V1.0.2B17` y el del stick es `V1.0.0B03`.
  **Versiones distintas.**
- La recuperación de brick requiere programador de NAND externo (CH341A).

---

## Hardware de este stick

El conector USB de éste en particular está **soldado a mano**. Antes de
culpar al firmware ante un comportamiento raro, verificar la conexión
física: cortes intermitentes generan re-enumeraciones que parecen bugs.
