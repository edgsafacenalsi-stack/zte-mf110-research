# 04 — El lock: cómo funciona realmente

Esta sección documenta por qué **calcular el NCK desde el IMEI es imposible**.

## Cómo NO funciona

En muchos módems baratos el código de desbloqueo es un hash simple del IMEI.
**En el MF110 no es así.**

Se verificó:

1. El firmware contiene la rutina de verificación en `amss.mbn`.
2. La validación es **criptográfica con clave pública RSA**.
3. El código de desbloqueo se verifica **contra la clave pública**, no se
   calcula a partir de ella.

Con una clave pública podés **verificar** una firma, no **generar** una.
Por eso no hay función `nck = f(imei)`.

## Dónde está el lock

| Elemento | Ubicación |
|---|---|
| Flag de red | RAM `0x1D13B04` |
| Flag de SIM | RAM `0x1D13B05` |
| Verificación RSA | `amss.mbn` |
| Datos de la SIM del operador | Partición `SIM_SECURE` |
| Código fuente (string en el binario) | `zte_dsatsec.c` |

## El punto de parcheo

En `amss.mbn`:

```
0xe30aa8:  13 d0    BEQ   (salta si el código es válido)  ← original
0xe30aa8:  13 e0    B     (salta siempre)                 ← parche
```

Con ese cambio el firmware **aceptaría cualquier código**.

**Pero** para aplicarlo hace falta **escribir `amss` en la NAND**.
Y ahí está el problema: la única vía de escritura es el modo download, cuyo
protocolo no está resuelto (ver [06](06-protocolo-ARMPRG.md)).

## Por qué el lock compara MCC/MNC

`AT+ZSEC?` devuelve `<estado>,<código>`:

| Valor | Significado |
|---|---|
| `3,0` | SIM autorizada |
| `2,1` | SIM no autorizada (bloqueado) |

Los MCC/MNC detectados fueron `72234` (Personal) y `722310` (Claro).
La comparación es directa contra la lista embebida en `SIM_SECURE`.

## Lo que NO sirve

| Intento | Resultado |
|---|---|
| `AT+CLCK` | **Stub**: siempre devuelve `0`, no hace nada |
| `AT+CLCK="PN"` | ERROR con SIM no autorizada |
| Fuerza bruta de códigos | Ver más abajo |
| Exponer NV items | El lock no está en NV |

## La fuerza bruta

Se intentó con los **primeros 2 bytes** (65 536 combinaciones):

- **0 aciertos**
- A los ~291 comandos: `Window overrun` (el buffer del bootloader se llena)
- `0xC8` resultó ser un **falso positivo**

Aun con el protocolo resuelto, la fuerza bruta **no es viable**:
el NCK es un valor criptográfico de 16 dígitos, no un código corto.

## Conclusión

| Vía | ¿Viable? |
|---|---|
| Calcular NCK del IMEI | ❌ **Imposible** (RSA) |
| Fuerza bruta | ❌ No |
| Pagar DC-Unlocker | ✅ pero $ |
| Parchear `amss` y flashear | ⚠️ **Bloqueado por el protocolo de flasheo** |
| Flashear `efs.mbn` de otro operador | ⚠️ Requiere el mismo protocolo, y versiones distintas (`B03` vs `B17`) |

La última vía es la que se persiguió, y es lo que cubre
[05](05-modo-download.md) y [06](06-protocolo-ARMPRG.md).
