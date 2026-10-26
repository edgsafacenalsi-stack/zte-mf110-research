# research/

Datos crudos y resultados de pruebas.

| Archivo | Qué es |
|---|---|
| `nv_mf110_0_999.json` | Volcado de 987 NV items (0–999). IMEI/serial verificados ausentes. |
| `sim_profiles.json` | Respuestas AT y sondeo al bootloader con dos SIM. IMSI redactados. |

## Sobre el volcado NV

- Formato: `{"<item>": "<hex de 128 bytes>"}`
- **Contiene calibración de radio.** Es útil como referencia, pero
  **no** copiarlo a otro equipo a ciegas.
- El rango 0–999 **no** incluye items de identidad (IMEI, etc.), lo que
  se confirmó buscando el IMEI en ASCII, UTF-16 y BCD (ambos órdenes de
  nibbles).

Ver [docs/03-nv.md](../docs/03-nv.md).

## Datos que NO se publican

Los volcados completos (0–2999) de la sesión original no se incluyen acá.
Si los publicás desde tu propia investigación, **verificá primero** que no
contengan IMEI, IMSI ni claves de autenticación.
