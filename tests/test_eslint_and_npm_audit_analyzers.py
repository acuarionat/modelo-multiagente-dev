"""
Test de los adaptadores MC-05/MS-06 para JS/TS (herramientas reales,
mismo estilo que tests/test_code_analysis_tools.py): ESLint (regla
complexity) y npm audit, invocados contra un workspace temporal real.
"""

import os
import shutil
import tempfile

from core.code_analysis.eslint_complexity_analyzer import ejecutar_eslint_complexity
from core.code_analysis.models import ESTADO_ERROR, ESTADO_NO_APLICA, ESTADO_OK
from core.code_analysis.npm_audit_analyzer import ejecutar_npm_audit

workspace = tempfile.mkdtemp(prefix="test_eslint_npm_audit_")

try:
    # ==========================================================
    # eslint-complexity — MC-05 (herramienta real, node_modules local)
    # ==========================================================

    codigo_tsx = """
function funcionSimple() {
  return 1;
}

function funcionCompleja(a: number, b: number, c: number, d: number, e: number): number {
  if (a) {
    if (b) {
      if (c) {
        if (d) {
          if (e) {
            return 1;
          }
          return 2;
        }
        return 3;
      }
      return 4;
    }
    return 5;
  }
  return 6;
}
"""
    with open(os.path.join(workspace, "modulo.tsx"), "w", encoding="utf-8") as handle:
        handle.write(codigo_tsx)

    resultado_eslint = ejecutar_eslint_complexity(workspace)
    print("\n" + "=" * 70)
    print("ejecutar_eslint_complexity — módulo con función compleja")
    print("=" * 70)
    print(resultado_eslint)

    assert resultado_eslint["estado"] == ESTADO_OK, resultado_eslint
    funciones = resultado_eslint["datos"]["funciones"]
    por_nombre = {f["nombre"]: f for f in funciones}
    assert por_nombre["funcionSimple"]["aceptable"] is True
    assert por_nombre["funcionCompleja"]["complejidad"] >= 6

    # Workspace sin archivos JS/TS → NO_APLICA, nunca 0 %.
    workspace_vacio = tempfile.mkdtemp(prefix="test_eslint_vacio_")
    resultado_eslint_vacio = ejecutar_eslint_complexity(workspace_vacio)
    print(resultado_eslint_vacio)
    assert resultado_eslint_vacio["estado"] == ESTADO_NO_APLICA
    shutil.rmtree(workspace_vacio, ignore_errors=True)

    # ==========================================================
    # npm audit — MS-06 (herramienta real; requiere red para consultar
    # el índice de vulnerabilidades, igual que pip-audit en
    # test_code_analysis_tools.py: solo se exige un estado válido).
    # ==========================================================

    manifiesto_ausente = ejecutar_npm_audit(workspace)
    print("\n" + "=" * 70)
    print("ejecutar_npm_audit — sin package-lock.json")
    print("=" * 70)
    print(manifiesto_ausente)
    assert manifiesto_ausente["estado"] == ESTADO_NO_APLICA

    with open(os.path.join(workspace, "package.json"), "w", encoding="utf-8") as handle:
        handle.write('{"name": "fixture", "version": "1.0.0", "dependencies": {}}')
    with open(os.path.join(workspace, "package-lock.json"), "w", encoding="utf-8") as handle:
        handle.write(
            '{"name": "fixture", "version": "1.0.0", "lockfileVersion": 3, '
            '"requires": true, "packages": {"": {"name": "fixture", "version": "1.0.0"}}}'
        )

    resultado_npm_audit = ejecutar_npm_audit(workspace)
    print("\n" + "=" * 70)
    print("ejecutar_npm_audit — package.json sin dependencias")
    print("=" * 70)
    print(resultado_npm_audit)
    assert resultado_npm_audit["estado"] in {ESTADO_OK, ESTADO_ERROR, ESTADO_NO_APLICA}
    if resultado_npm_audit["estado"] == ESTADO_OK:
        assert "dependencias" in resultado_npm_audit["datos"]
        for dependencia in resultado_npm_audit["datos"]["dependencias"]:
            assert "segura" in dependencia
    else:
        assert resultado_npm_audit["detalle_error"]

finally:
    shutil.rmtree(workspace, ignore_errors=True)

print("\nTodas las verificaciones de eslint_complexity_analyzer y npm_audit_analyzer pasaron.")
