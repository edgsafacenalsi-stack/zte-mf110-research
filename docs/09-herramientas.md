# 09 — Workspace y herramientas

## Requisitos

```bash
python3 -m venv venv
source venv/bin/activate
pip install pyusb crcmod capstone
```

Permisos USB: el usuario debe estar en el grupo `uucp` (Arch) o tener una
regla udev. Para `usb.core` además puede hacer falta `plugdev`.

## Scripts

### `tools/diag.py`

Cliente DIAG mínimo (QCDM): apertura de interfaz, SPC, password, lectura
y escritura de NV items.

```python
from diag import Diag
d = Diag()
d.open()
d.spc()
print(d.nv_read(0).hex())
d.close()
```

### `tools/nv.py`

Volcado y escritura masiva de NV items.

```bash
python3 tools/nv.py dump 0 999 research/nv.json
python3 tools/nv.py read 5000
```

### `tools/at.py`

Envío de comandos AT por `/dev/ttyUSB2`.

```bash
python3 tools/at.py 'AT+ZSEC?'
python3 tools/at.py 'AT+CPMS="ME","ME","ME"' 'AT+CMGL=4'
```

> Para leer SMS hay que setear `AT+CPMS="ME","ME","ME"` **antes** de
> `AT+CMGL=4`.

### `tools/dl76.py`

Cliente del modo download. Entra a `0076` y envía comandos HDLC.

```bash
python3 tools/dl76.py enter          # entrar a 0076
python3 tools/dl76.py watch          # ver PIDs
python3 tools/dl76.py one 1          # comando 1, payload vacío
python3 tools/dl76.py one 1 00..00   # con payload hex
```

**Verifica integridad antes y después de cada comando** (`AT+ZSEC?`) y
aborta si el stick no vuelve sano.

### `tools/dl76_crc_hunt.py`

Prueba sistemática de variantes de CRC y framing contra el bootloader,
leyendo de `/dev/ttyUSB0` en modo 0076.

```bash
python3 tools/dl76_crc_hunt.py
```

**Requiere** que el stick esté en `0076` **con ttyUSB** (ver
[05](../docs/05-modo-download.md)).

### `tools/disasm.py`

Desensambla `nandprgcombined.mbn` (o cualquier `.mbn`) con capstone.

```bash
python3 tools/disasm.py firmware/nandprgcombined.mbn 0x5948 0x5b20
```

### `tools/strings_scan.py`

Lista strings con offsets.

```bash
python3 tools/strings_scan.py firmware/nandprgcombined.mbn 5
```

### `tools/partition_parse.py`

Decodifica `partition.mbn` e imprime la tabla de particiones.

```bash
python3 tools/partition_parse.py firmware/partition.mbn
```

### `tools/gen_com_reg.py`

Convierte las tablas de registro de un MSI de QPST a un `.reg` importable
por Wine. Documentado en [07](../docs/07-lo-que-no-funciono.md).

## Advertencia

Todos los scripts de `0076` **hablan con el bootloader**. El comando 4
es escritura en NAND. Los scripts incluidos **no lo usan**, pero si
modificás algo, tené claro qué estás mandando.
