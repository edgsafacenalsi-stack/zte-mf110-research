# 10 — Cómo seguir

El protocolo **está resuelto**. Lo que sigue es ejecutar el flasheo.

Índice: [← Herramientas](09-herramientas.md) · [Índice](00-INDICE.md) · [Protocolo desde QPST →](11-protocolo-desde-qpst.md)

---

## Dónde estamos

| Etapa | Estado |
|---|---|
| Acceso DIAG | ✅ |
| Lectura/escritura NV | ✅ |
| Entrada a modo download `0076` | ✅ |
| **Handshake del protocolo** | ✅ **magic + CRC correctos** |
| Secuencia de flasheo | ⏳ siguiente paso |
| Escritura de NAND | ⏳ no intentada |

El cliente con el CRC correcto está en
[`tools/armpg.py`](../tools/armpg.py).

---

## Paso 1 — Confirmar el handshake contra el stick

```bash
# 1. stick sano en 0031
python3 tools/at.py 'AT+ZSEC?'

# 2. entrar a 0076 (ver docs/05)
python3 tools/dl76.py one 1

# 3. handshake
python3 tools/armpg.py probe
```

**Éxito esperado:** la respuesta del stick contiene
`"QCOM fast download protocol targ"`.

Si aparece, **el protocolo quedó validado en hardware** y se puede seguir.

---

## Paso 2 — Descubrir la secuencia de comandos

El proyecto de referencia
[`jcsullins/qdloader`](https://github.com/jcsullins/qdloader) contiene la
secuencia completa. Los pasos identificados en su código:

```
sub doMagic        → handshake (hecho)
sub doHello        → protocol version exchange
sub doSecurityMode → SPC / modo de seguridad
sub doOpenMulti    → abrir imagen multi-parte
sub doOpen         → abrir partición
sub doWrite        → escribir bloque
sub doClose        → cerrar
```

**Leer ese código directamente** es lo más rápido: son ~986 líneas de Perl
con comentarios.

```bash
git clone https://github.com/jcsullins/qdloader
less qdloader/qdload.pl
```

### Lo que ya sabemos del firmware del stick

Del desensamblado de `nandprgcombined.mbn` (ver [doc 06](06-protocolo-ARMPRG.md)):

| Comando | Handler | Qué hace |
|---|---|---|
| 2, 3 | `0x5954` → `0x5068` | validación / control |
| 4 | `0x5954` (fall-through) | **escritura en NAND** |
| 5 | `0x5a24` | respuesta informativa (`EF 02 01`) |
| 6 | `0x5954` | control |

Y la secuencia que exige el firmware, deducida de sus mensajes de error:

```
1. SET SECURITY MODE
2. PARTITION TABLE        ← partition.mbn
3. OPEN MULTI
4. OPEN (por partición)
5. WRITE (por página, 2048 bytes)
6. CLOSE
```

---

## Paso 3 — Escribir `partition.mbn`

Esto es **la prueba de fuego** y también el primer riesgo real.

- `partition.mbn` son 464 bytes: **chico, reversible**.
- Si se escribe mal, el stick puede no arrancar.
- **Backup previo:** el volcado NV ya está en
  [`research/`](../research/), pero la tabla de particiones no se puede
  leer sin el protocolo completo.

**Antes de escribir, confirmar:**

1. El handshake funciona.
2. Se entiende la secuencia de `qdloader`.
3. Hay forma de revertir (reconectar el stick y verificar).

---

## Paso 4 — Lo que NO hacer

| Tentación | Por qué no |
|---|---|
| Flashear `efs.mbn` primero | 21 MB vs 464 bytes. Empezar por lo chico. |
| Usar el `efs.mbn` de `V1.0.2B17` | El stick es `V1.0.0B03`. **Versiones distintas.** |
| Flashear `amss.mbn` sin pensar | Es el baseband. Mal escrito = brick. |
| Confiar en un solo intento | Verificar después de cada paso. |

---

## Si el stick se brickea

1. **Reconectar** — a veces vuelve solo.
2. **CH341A** (programador de NAND externo) para leer/escribir la flash
   directamente.
3. Los voltajes y el pinout dependen del PCB. **Investigar antes de
   conectar.**

Ver [doc 12](12-estado-y-recuperacion.md) para el estado y recuperación.

---

## Lo que este proyecto ya aporta (aunque no se complete el flasheo)

- **El protocolo documentado** con CRC verificado contra referencia.
- **El hallazgo del ttyUSB en `0076`** (ver [doc 05](05-modo-download.md)).
- **La API de QPST** con 1551 firmas (ver [doc 11](11-protocolo-desde-qpst.md)).
- Un registro de **9 vías descartadas** ([doc 07](07-lo-que-no-funciono.md)).
- Herramientas funcionales: DIAG, NV, AT, cliente del protocolo.

---

## Contribuir

Si avanzás:

1. Abrí un issue con el resultado, **aunque sea negativo**.
2. Si conseguís el handshake, mandá el log.
3. Si llegás a escribir NAND, documentá la secuencia exacta.

**Los callejones sin salida valen tanto como los avances.**
