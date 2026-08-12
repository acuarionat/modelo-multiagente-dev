import os
import shutil
import tempfile

from core.code_analysis.dependency_analyzer import ejecutar_pip_audit
from core.code_analysis.models import ESTADO_ERROR, ESTADO_NO_APLICA, ESTADO_OK
from core.code_analysis.radon_analyzer import ejecutar_radon
from core.code_analysis.secrets_analyzer import ejecutar_gitleaks
from core.code_analysis.semgrep_analyzer import ejecutar_semgrep

workspace = tempfile.mkdtemp(prefix="test_code_analysis_")

try:
    # ==========================================================
    # radon — MC-05 (herramienta real, instalada localmente)
    # ==========================================================

    codigo_complejo = '''
def funcion_simple(x):
    return x + 1


def funcion_compleja(a, b, c, d, e):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return 1
                    return 2
                return 3
            return 4
        return 5
    return 6
'''
    with open(os.path.join(workspace, "modulo.py"), "w", encoding="utf-8") as handle:
        handle.write(codigo_complejo)

    resultado_radon = ejecutar_radon(workspace)
    print("\n" + "=" * 70)
    print("ejecutar_radon — módulo con función compleja")
    print("=" * 70)
    print(resultado_radon)

    assert resultado_radon["estado"] == ESTADO_OK, resultado_radon
    funciones = resultado_radon["datos"]["funciones"]
    assert {f["nombre"] for f in funciones} == {"funcion_simple", "funcion_compleja"}
    por_nombre = {f["nombre"]: f for f in funciones}
    assert por_nombre["funcion_simple"]["aceptable"] is True
    assert por_nombre["funcion_compleja"]["complejidad"] >= 6

    # Workspace vacío (sin archivos .py) → NO_APLICA, nunca 0 %.
    workspace_vacio = tempfile.mkdtemp(prefix="test_code_analysis_vacio_")
    resultado_radon_vacio = ejecutar_radon(workspace_vacio)
    print(resultado_radon_vacio)
    assert resultado_radon_vacio["estado"] == ESTADO_NO_APLICA
    shutil.rmtree(workspace_vacio, ignore_errors=True)

    # ==========================================================
    # semgrep — MS-05 (herramienta real; puede requerir red para
    # `--config auto`, por lo que solo se exige un estado válido
    # y una estructura de datos correcta cuando el estado es OK).
    # ==========================================================

    resultado_semgrep = ejecutar_semgrep(workspace)
    print("\n" + "=" * 70)
    print("ejecutar_semgrep — módulo de prueba")
    print("=" * 70)
    print(resultado_semgrep)
    assert resultado_semgrep["estado"] in {ESTADO_OK, ESTADO_ERROR}
    if resultado_semgrep["estado"] == ESTADO_OK:
        assert "hallazgos" in resultado_semgrep["datos"]
        for hallazgo in resultado_semgrep["datos"]["hallazgos"]:
            assert set(hallazgo) == {"archivo", "linea", "regla", "mensaje", "severidad", "critico"}
    else:
        assert resultado_semgrep["detalle_error"]

    workspace_vacio_semgrep = tempfile.mkdtemp(prefix="test_code_analysis_vacio_semgrep_")
    resultado_semgrep_vacio = ejecutar_semgrep(workspace_vacio_semgrep)
    assert resultado_semgrep_vacio["estado"] == ESTADO_NO_APLICA
    shutil.rmtree(workspace_vacio_semgrep, ignore_errors=True)

    # ==========================================================
    # pip-audit — MS-06 (herramienta real, instalada para esta prueba)
    # ==========================================================

    manifiesto_no_encontrado = {"encontrado": False, "ruta": None, "contenido": None, "estado": "NO_APLICA", "error": None}
    resultado_sin_manifiesto = ejecutar_pip_audit(manifiesto_no_encontrado, workspace)
    print("\n" + "=" * 70)
    print("ejecutar_pip_audit — sin manifiesto")
    print("=" * 70)
    print(resultado_sin_manifiesto)
    assert resultado_sin_manifiesto["estado"] == ESTADO_NO_APLICA

    with open(os.path.join(workspace, "requirements.txt"), "w", encoding="utf-8") as handle:
        handle.write("requests==2.25.0\n")  # versión con vulnerabilidades conocidas, para forzar hallazgos reales.
    manifiesto_ok = {
        "encontrado": True, "ruta": "requirements.txt",
        "contenido": "requests==2.25.0\n", "estado": "OK", "error": None,
    }
    resultado_pip_audit = ejecutar_pip_audit(manifiesto_ok, workspace)
    print("\n" + "=" * 70)
    print("ejecutar_pip_audit — requirements.txt con dependencia vulnerable")
    print("=" * 70)
    print(resultado_pip_audit)
    assert resultado_pip_audit["estado"] in {ESTADO_OK, ESTADO_ERROR}
    if resultado_pip_audit["estado"] == ESTADO_OK:
        dependencias = resultado_pip_audit["datos"]["dependencias"]
        assert any(dep["nombre"].casefold() == "requests" for dep in dependencias)
    else:
        # Solo aceptable si es por ausencia de red/servicio de índice de
        # vulnerabilidades, nunca se convierte en 0 % de MS-06.
        assert resultado_pip_audit["detalle_error"]

    manifiesto_no_soportado = {
        "encontrado": True, "ruta": "pyproject.toml",
        "contenido": "[project]\nname='x'\n", "estado": "OK", "error": None,
    }
    resultado_manifiesto_no_soportado = ejecutar_pip_audit(manifiesto_no_soportado, workspace)
    assert resultado_manifiesto_no_soportado["estado"] == ESTADO_NO_APLICA

    manifiesto_con_error = {"encontrado": True, "ruta": "requirements.txt", "contenido": None, "estado": "ERROR", "error": "boom"}
    resultado_manifiesto_error = ejecutar_pip_audit(manifiesto_con_error, workspace)
    assert resultado_manifiesto_error["estado"] == ESTADO_ERROR

    # ==========================================================
    # gitleaks — MS-07 (herramienta NO instalada en este entorno:
    # se prueba explícitamente que la ausencia se reporta como ERROR,
    # nunca como 0 %, que es exactamente el comportamiento exigido).
    # ==========================================================

    resultado_gitleaks = ejecutar_gitleaks(workspace)
    print("\n" + "=" * 70)
    print("ejecutar_gitleaks — herramienta no instalada")
    print("=" * 70)
    print(resultado_gitleaks)
    if shutil.which("gitleaks") is None:
        assert resultado_gitleaks["estado"] == ESTADO_ERROR
        assert "no encontrada" in resultado_gitleaks["motivo"].casefold()
    else:
        assert resultado_gitleaks["estado"] in {ESTADO_OK, ESTADO_ERROR}
        if resultado_gitleaks["estado"] == ESTADO_OK:
            for hallazgo in resultado_gitleaks["hallazgos"]:
                assert hallazgo["valor"] == "[REDACTED]"

finally:
    shutil.rmtree(workspace, ignore_errors=True)

print("\nTodas las verificaciones de core/code_analysis pasaron.")
