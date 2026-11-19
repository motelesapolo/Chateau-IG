"""Material propio del hotel.

  python scripts/material.py optimizar     → deja listos los archivos nuevos (lo corre GitHub solo)
  python scripts/material.py inventario    → lista fotos/videos con cuántas veces se usaron
"""
import json
import sys

import _boot
from autopilot import material


def main(cmd: str) -> int:
    if cmd == "optimizar":
        res = material.optimize()
        lines = [f"### Material: {len(res['ok'])} archivos listos"]
        lines += [f"- ✅ {p}" for p in res["ok"]]
        lines += [f"- ❌ {e}" for e in res["errores"]]
        _boot.step_summary("\n".join(lines))
        return 0
    if cmd == "inventario":
        rows = material.inventory()
        if not rows:
            print("No hay material todavía en material/.")
            return 0
        cat = None
        for r in rows:
            if r["categoria"] != cat:
                cat = r["categoria"]
                print(f"\n## {cat}")
            extra = f", {r['segundos']} s" if "segundos" in r else ""
            print(f"- {r['path']} ({r['tipo']}, {r.get('orientacion', '?')} {r.get('tamano', '')}{extra}) "
                  f"usos: {r['usos']}{' · ' + ', '.join(r['usado_en']) if r['usado_en'] else ''}")
        if "--json" in sys.argv:
            print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
