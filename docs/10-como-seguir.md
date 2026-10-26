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

## Paso 3 — Probar el servidor ARMPRG con un cliente existente (2 h)

Existen implementaciones libres de ARMPRG en Linux:

- **`armprg` de `libqmi` / `openmoko`** — el protocolo es de 2007, hay
  código por ahí.
- Buscar `"ARMPRG"` en repositorios de flasheo de módems viejos.
- También hubo un cliente en Python para MSM7x00.

**Ventaja:** si alguno funciona, no hay que reimplementar nada.
**Probarlo contra el stick y ver si el framing coincide.**

> Si aparece uno que funcione, **contribuir el resultado acá**.

---

## Paso 4 — Desensamblar completo con radare2 (3-4 h)

```bash
sudo pacman -S radare2
r2 -a arm -b 32 -m 0x800028 firmware/nandprgcombined.mbn
```

Dentro:

```
aaa                      ; análisis automático
afl                      ; listar funciones
s 0x808ee8               ; ir a la función de verificación
pdf                      ; desensamblar con análisis
```

Con análisis automático se obtienen **referencias cruzadas**, que es lo que
con capstone a mano no se tiene. Eso responde:

- ¿Dónde se calcula el CRC que se compara?
- ¿Qué función lee el magic?
- ¿Cuál es el formato exacto del header?

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
