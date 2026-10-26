#!/usr/bin/env python3
"""
Convierte las tablas Registry.idt y Class.idt de un MSI a un .reg de Windows
que Wine pueda importar con 'wine regedit'.

Motivo: QPSTConfig.exe falla con "class not registered" porque el MSI no se
pudo instalar (error 1603 en InstallFinalize bajo Wine). La tabla de registro
del MSI contiene todas las claves COM necesarias, asi que se reconstruyen
directamente en el registro de Wine.

Los valores de la tabla .idt tienen formato: s72 (string), i2 (int),
l255 (localizable), L0 (nulo), s38 (GUID), etc.
"""
import sys
import os
from collections import defaultdict

TABLES = os.environ.get("MSI_TABLES", "msi_tables")
OUT = os.environ.get("QPUT", "qpst_com.reg")

HIVES = {
    0: "HKEY_CLASSES_ROOT",
    1: "HKEY_CURRENT_USER",
    2: "HKEY_LOCAL_MACHINE",
    3: "HKEY_USERS",
}

# Componentes cuyo nombre real es <archivo>.dll.<guid> ->
# hay que quedarse con la parte del archivo
def clean_component(comp):
    """QPSTProxyComponents.dll.GUID -> QPSTProxyComponents.dll"""
    if ".dll." in comp:
        return comp.split(".dll.")[0] + ".dll"
    if ".tlb." in comp:
        return comp.split(".tlb.")[0] + ".tlb"
    if ".exe." in comp:
        return comp.split(".exe.")[0] + ".exe"
    return comp


def parse_idt(path):
    """Lee un .idt y devuelve (nombre_columnas, filas)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    if len(lines) < 3:
        return [], []
    cols = lines[0].split("\t")
    rows = []
    for line in lines[3:]:  # las dos primeras son tipos
        if not line.strip() or line.startswith("\t"):
            continue
        # el .idt separa con tabs y los valores pueden tener tabs escapados
        parts = line.split("\t")
        rows.append(parts)
    return cols, rows


def reg_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def main():
    reg_cols, reg_rows = parse_idt(os.path.join(TABLES, "Registry.idt"))
    cls_cols, cls_rows = parse_idt(os.path.join(TABLES, "Class.idt"))

    # --- construir mapa CLSID -> archivo (desde Class.idt)
    clsid_map = {}
    if cls_cols:
        try:
            i_clsid = cls_cols.index("CLSID")
            i_ctx = cls_cols.index("Context")
            i_comp = cls_cols.index("Component_")
        except ValueError:
            i_clsid = i_ctx = i_comp = None
        if i_clsid is not None:
            for row in cls_rows:
                if len(row) <= max(i_clsid, i_ctx, i_comp):
                    continue
                clsid = row[i_clsid].strip("{}").upper()
                ctx = row[i_ctx] or "InprocServer32"
                comp = clean_component(row[i_comp])
                clsid_map[clsid] = (ctx, comp)

    # --- agrupar Registry.idt por clave
    # Registry: Root(tabla) Key Name Value Component_
    entradas = defaultdict(list)
    if reg_cols:
        for row in reg_rows:
            if len(row) < 5:
                continue
            tbl, root, key, name, value, comp = row[0], row[1], row[2], row[3], row[4], row[5] if len(row) > 5 else ""
            if tbl != "Registry":
                continue
            try:
                hive = HIVES.get(int(root), None)
            except ValueError:
                hive = None
            if not hive or not key:
                continue
            entradas[(hive, key)].append((name, value, clean_component(comp)))

    # --- escribir .reg
    out = ["Windows Registry Editor Version 5.00", ""]
    n_claves = 0
    for (hive, key), vals in entradas.items():
        out.append(f"[{hive}\\{key}]")
        for name, value, comp in vals:
            if value == "":
                # clave por defecto con el path del archivo
                if name == "" and comp:
                    out.append(f'@="{reg_escape(comp)}"')
                elif name:
                    out.append(f'"{reg_escape(name)}"=""')
                continue
            if name == "":
                out.append(f'@="{reg_escape(value)}"')
            else:
                out.append(f'"{reg_escape(name)}"="{reg_escape(value)}"')
        out.append("")
        n_claves += 1

    # --- agregar InprocServer32 para cada CLSID que apunte a una DLL
    out.append("; --- CLSIDs mapeados desde Class.idt ---")
    for clsid, (ctx, comp) in clsid_map.items():
        if not comp.lower().endswith(".dll"):
            continue
        out.append(f"[HKEY_CLASSES_ROOT\\CLSID\\{{{clsid}}}\\{ctx}]")
        out.append(f'@="C:\\\\Qualcomm\\\\QPST\\\\bin\\\\{comp}"')
        out.append("")
        n_claves += 1

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))

    print(f"claves de Registry.idt: {len(entradas)}")
    print(f"CLSIDs de Class.idt: {len(clsid_map)}")
    print(f"claves escritas: {n_claves}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
