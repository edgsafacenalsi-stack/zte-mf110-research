# Índice de documentación

| # | Documento | Qué cubre |
|---|---|---|
| 01 | [Dispositivo y hardware](01-dispositivo.md) | Identificación, interfaz USB, modos, SIM |
| 02 | [Acceso DIAG](02-diag.md) | Cómo se habla con el chipset por libusb |
| 03 | [NV items](03-nv.md) | Lectura/escritura de NV, volcado de 987 ítems |
| 04 | [El lock](04-lock.md) | Cómo funciona el SIM-lock y por qué el NCK no se calcula |
| 05 | [Modo download 0076](05-modo-download.md) | Cómo se entra, handshake, qué aparece en USB |
| 06 | [Protocolo ARMPRG](06-protocolo-ARMPRG.md) | **El hallazgo central.** Estructura, comandos, estado |
| 07 | [Lo que no funcionó](07-lo-que-no-funciono.md) | Registro de callejones sin salida |
| 08 | [Ingeniería inversa del firmware](08-firmware-re.md) | Strings, ARM, offsets, símbolos encontrados |
| 09 | [Workspace y herramientas](09-herramientas.md) | Scripts incluidos y cómo usarlos |
| 10 | [Cómo seguir](10-como-seguir.md) | Próximos pasos concretos |

## Lectura rápida

Si venís por el protocolo:
→ **06** y luego **08**

Si venís a intentar el desbloqueo:
→ **04** (entendé el lock) → **07** (no repitas errores) → **10**

Si venís por el reto de ingeniería inversa:
→ **08** y [tools/](../tools/)
