# 01 — Dispositivo y hardware

## Identificación

| Campo | Valor |
|---|---|
| Modelo | ZTE MF110 |
| Tipo | HSPA/UMTS USB stick |
| Chipset | Qualcomm **MSM6290** (familia MSM6246/6290) |
| Firmware | `BD_P671A2V1.0.0B03` |
| IMEI | `35179003xxxxxxx` *(redactado)* |
| Serial USB | `P671A2xxxxxxxxxx` *(redactado)* |
| SIM-lock | MCC/MNC |

## Modos USB observados

| VID:PID | Nombre | Cuándo aparece |
|---|---|---|
| `19d2:0031` | ZTE WCDMA Technologies MSM | Modo normal |
| `19d2:0076` | ZTE CDMA Technologies MSM | Modo download |
| `19d2:2000` | ZTE HSPA (MF627/628/636+) | Transitorio tras reset |

### `0031` — modo normal

Expone **4 interfaces**:

| Interfaz | Clase | Dispositivo | Uso |
|---|---|---|---|
| `1-12:1.0` | `ff/ff/ff` | vendor | *(varía con el driver)* |
| `1-12:1.1` | `ff/ff/ff` | `/dev/ttyUSB1` | **DIAG** (QCDM) |
| `1-12:1.2` | `08/06/50` | mass storage | MicroSD |
| `1-12:1.3` | `ff/ff/ff` | `/dev/ttyUSB2` | **AT commands** |

> **Ojo:** el puerto **AT es `ttyUSB2`**, no `ttyUSB1`.
> Confundirlos fue uno de los primeros errores.

### `0076` — modo download

Una sola interfaz vendor-specific, con un endpoint:

- EP OUT `0x01`, EP IN `0x81`
- **No habla Sahara/EDL** (responde "Invalid magic number" a ese framing)
- **No es un puerto serie por defecto** — ver [05](05-modo-download.md) para la excepción

## Cómo se identifica en Linux

```bash
lsusb | grep 19d2
ls /dev/ttyUSB*
udevadm info -q property -n /dev/ttyUSB2 | grep -E 'ID_MODEL|ID_VENDOR'
```

En modo download "completo" (ver [05](05-modo-download.md)) el driver
`option` engancha la interfaz y aparece:

```
ID_USB_DRIVER=option
ID_MODEL=ZTE_CDMA_Technologies_MSM
```

## SIM y red

Probado con dos SIM:

| SIM | MCC/MNC | `AT+ZSEC?` | Registro en red |
|---|---|---|---|
| Personal | `72234` | `3,0` | Sí (`+CREG: 0,1`), recibe SMS |
| Claro | `722310` | `2,1` | No |

`AT+ZSEC?` devuelve `<estado>,<código>`:

- `3,0` → SIM autorizada (la del operador del lock)
- `2,1` → SIM de otro operador (**bloqueado**)

## Datos del stick

- Número propio, centro de SMS y APN: **redactados** (son datos personales).
- Lo único relevante técnicamente es el APN del operador, que se puede
  consultar con `AT+CGDCONT?` en cualquier equipo.

## Comandos ZTE ocultos

`AT+ZCDRUN=A..G` — consulta firmware, autorun, y modo download.

`AT+ZCDRUN=E` activa un flag interno pero **no cambia VID/PID**.

## Nota sobre el hardware

Este stick en particular tiene el conector USB **soldado a mano**, lo que
lo hace propenso a desconexiones físicas. Si se reproduce, verificar
primero que el conector esté firme antes de sospechar del firmware.
