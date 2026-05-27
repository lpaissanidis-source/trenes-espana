"""
patch_ouigo.py
Aplica los parches necesarios a la librería ouigo para que funcione
con la versión actual de la API de Ouigo Spain (que devuelve campos
extra no definidos en el dataclass original).

Parches:
  1. types_class.py — agrega el campo optional 'short_code' a Station_ES
  2. stations.py    — filtra campos desconocidos antes de construir Station_ES

Idempotente: si ya está parchado, no hace nada.
"""

import pathlib
import ouigo

ouigo_dir = pathlib.Path(ouigo.__file__).parent

# ── Patch 1: types_class.py ──────────────────────────────────────────────────
types_path = ouigo_dir / "types_class.py"
content = types_path.read_text(encoding="utf-8")

if "short_code" not in content:
    old = "    hidden: bool\n"
    new = "    hidden: bool\n    short_code: Optional[str] = None\n"
    patched = content.replace(old, new, 1)
    if patched != content:
        types_path.write_text(patched, encoding="utf-8")
        print("Patcheado: types_class.py — campo short_code agregado a Station_ES")
    else:
        print("AVISO: no se encontró el punto de inserción en types_class.py")
else:
    print("OK: types_class.py ya tiene short_code")

# ── Patch 2: stations.py ─────────────────────────────────────────────────────
stations_path = ouigo_dir / "stations.py"
content = stations_path.read_text(encoding="utf-8")

if "allowed = set(Station_ES" not in content:
    old = "                stations_es = [Station_ES(**station) for station in stations_json]"
    new = (
        "                allowed = set(Station_ES.__dataclass_fields__.keys())\n"
        "                stations_es = [Station_ES(**{k: v for k, v in station.items() if k in allowed}) for station in stations_json]"
    )
    patched = content.replace(old, new, 1)
    if patched != content:
        stations_path.write_text(patched, encoding="utf-8")
        print("Patcheado: stations.py — filtro de campos desconocidos aplicado")
    else:
        print("AVISO: no se encontró la línea a parchear en stations.py")
else:
    print("OK: stations.py ya tiene filtro de campos")

print("Parches ouigo completados.")
