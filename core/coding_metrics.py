"""
Cálculo determinístico (solo Python) de las métricas de Codificación, a
partir de la evidencia YA NORMALIZADA por core/code_analysis/ (nunca de
afirmaciones de un agente LLM). Ningún agente calcula estos valores: los
agentes de Calidad y Seguridad de Codificación solo los interpretan.

MC-06 está fuera de alcance en esta fase: el Índice de Calidad del Código
se define temporalmente como MC-05 (decisión de alcance documentada aquí,
no un cálculo definitivo).
"""

from core.umbral_aprobacion import UMBRAL_APROBACION, supera_umbral

# Umbral único (80 %, comparación estricta): ver core/umbral_aprobacion.py.
UMBRAL_MC05_SATISFACTORIO = UMBRAL_APROBACION
UMBRAL_MS06_SATISFACTORIO = UMBRAL_APROBACION
UMBRAL_MS07_SATISFACTORIO = UMBRAL_APROBACION


def calcular_mc05(evidencia_radon: dict) -> dict:
    """
    MC-05 Adecuación de la Complejidad Ciclomática = funciones con CC
    aceptable / funciones analizadas, según la herramienta de complejidad
    seleccionada para el lenguaje del repositorio (Radon o ESLint —
    "herramienta" en la evidencia recibida se conserva para presentación).
    """
    herramienta = (evidencia_radon or {}).get("herramienta")
    estado_herramienta = (evidencia_radon or {}).get("estado")
    if estado_herramienta != "OK":
        return {
            "codigo": "MC-05", "herramienta": herramienta,
            "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable",
            "motivo": (evidencia_radon or {}).get("detalle_error") or f"{herramienta or 'analizador de complejidad'}: estado {estado_herramienta!r}.",
        }

    funciones = (evidencia_radon.get("datos") or {}).get("funciones") or []
    denominador = len(funciones)
    if denominador == 0:
        return {
            "codigo": "MC-05", "herramienta": herramienta,
            "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable",
            "motivo": f"{herramienta or 'El analizador de complejidad'} no reportó funciones evaluables.",
        }

    numerador = sum(1 for funcion in funciones if funcion.get("aceptable") is True)
    valor = numerador / denominador

    return {
        "codigo": "MC-05", "herramienta": herramienta,
        "valor": valor, "numerador": numerador, "denominador": denominador,
        "estado_calculo": "calculada",
        "satisfactorio": supera_umbral(valor),
    }


def calcular_ms05(evidencia_semgrep: dict) -> dict:
    """MS-05 Vulnerabilidades Críticas Detectadas = conteo de hallazgos críticos (Semgrep). Resultado deseado: 0."""
    estado_herramienta = (evidencia_semgrep or {}).get("estado")
    if estado_herramienta != "OK":
        return {
            "codigo": "MS-05", "valor": None, "numero_criticas": None,
            "estado_calculo": "no_evaluable",
            "motivo": (evidencia_semgrep or {}).get("detalle_error") or f"semgrep: estado {estado_herramienta!r}.",
        }

    hallazgos = (evidencia_semgrep.get("datos") or {}).get("hallazgos") or []
    numero_criticas = sum(1 for hallazgo in hallazgos if hallazgo.get("critico") is True)

    # MS-05 es un conteo, no un porcentaje: se normaliza a [0, 1] únicamente
    # para poder promediarlo con MS-06/MS-07 en el índice de seguridad
    # (1.0 = sin críticas, 0.0 = al menos una crítica). No se hace media
    # simple sin normalizar (MS-05 + MS-06 + MS-07) / 3.
    return {
        "codigo": "MS-05", "valor": 1.0 if numero_criticas == 0 else 0.0,
        "numero_criticas": numero_criticas,
        "estado_calculo": "calculada",
        "satisfactorio": numero_criticas == 0,
    }


def calcular_ms06(evidencia_pip_audit: dict) -> dict:
    """MS-06 Cobertura de Dependencias Seguras = dependencias seguras / dependencias analizadas (pip-audit)."""
    estado_herramienta = (evidencia_pip_audit or {}).get("estado")
    if estado_herramienta != "OK":
        return {
            "codigo": "MS-06", "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable",
            "motivo": (evidencia_pip_audit or {}).get("detalle_error") or f"pip-audit: estado {estado_herramienta!r}.",
        }

    dependencias = (evidencia_pip_audit.get("datos") or {}).get("dependencias") or []
    denominador = len(dependencias)
    if denominador == 0:
        return {
            "codigo": "MS-06", "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable", "motivo": "pip-audit no reportó dependencias analizadas.",
        }

    numerador = sum(1 for dependencia in dependencias if dependencia.get("segura") is True)
    valor = numerador / denominador

    return {
        "codigo": "MS-06", "valor": valor, "numerador": numerador, "denominador": denominador,
        "estado_calculo": "calculada",
        "satisfactorio": supera_umbral(valor),
    }


def calcular_ms07(evidencia_gitleaks: dict, archivos_analizados: list) -> dict:
    """
    MS-07 Cobertura de Código sin Secretos Expuestos =
    archivos de código analizados sin secretos / archivos de código analizados.

    NO es "cantidad de secretos": una métrica de cobertura de archivos.
    "archivos_analizados" es el universo de archivos de código del COD
    (core/code_analysis/secrets_analyzer.py::obtener_archivos_codigo_workspace
    o el perfil del repositorio), NO el JSON de Gitleaks: Gitleaks solo
    aporta qué archivos de ese universo tienen secretos.
    """
    estado_herramienta = (evidencia_gitleaks or {}).get("estado")
    base = {
        "codigo": "MS-07",
        "nombre": "Cobertura de Código sin Secretos Expuestos",
        "umbral": UMBRAL_MS07_SATISFACTORIO,
    }

    if estado_herramienta != "OK":
        return {
            **base,
            "estado": estado_herramienta,
            "valor": None, "porcentaje": None, "numerador": None, "denominador": None,
            "archivos_con_secretos": None, "secretos_detectados": None, "cumple": None,
            "estado_calculo": "no_evaluable",
            "motivo": (evidencia_gitleaks or {}).get("motivo") or f"gitleaks: estado {estado_herramienta!r}.",
        }

    analizados = {str(ruta).replace("\\", "/") for ruta in (archivos_analizados or [])}
    total = len(analizados)
    if total == 0:
        return {
            **base,
            "estado": "OK",
            "valor": None, "porcentaje": None, "numerador": None, "denominador": None,
            "archivos_con_secretos": None,
            "secretos_detectados": evidencia_gitleaks.get("secretos_detectados", 0),
            "cumple": None,
            "estado_calculo": "sin_evidencia",
            "motivo": "No hay archivos de código analizados para calcular MS-07.",
        }

    con_secretos_gitleaks = {
        str(ruta).replace("\\", "/") for ruta in (evidencia_gitleaks.get("archivos_con_secretos") or [])
    }
    con_secretos = con_secretos_gitleaks & analizados
    sin_secretos = total - len(con_secretos)
    valor = sin_secretos / total

    return {
        **base,
        "estado": "OK",
        "valor": valor,
        "porcentaje": round(valor * 100, 2),
        "numerador": sin_secretos,
        "denominador": total,
        "archivos_con_secretos": len(con_secretos),
        "secretos_detectados": evidencia_gitleaks.get("secretos_detectados", 0),
        "cumple": supera_umbral(valor),
        "estado_calculo": "calculada",
    }


def calcular_indice_calidad_codigo(mc05_valor):
    """
    Índice de Calidad del Código = MC-05, mientras MC-06 esté fuera del
    alcance actual (decisión temporal de alcance, no un cálculo definitivo).
    Una métrica no_evaluable (None) no se convierte en 0.
    """
    return mc05_valor


def calcular_indice_seguridad_codigo(ms05_valor_normalizado, ms06_valor, ms07_valor):
    """
    Índice de Seguridad del Código: promedio de MS-05 (ya normalizado a
    [0, 1], no el conteo crudo), MS-06 y MS-07. Una métrica no_evaluable
    (None) no se convierte en 0 ni se promedia sin normalizar.
    """
    valores = [
        valor
        for valor in (ms05_valor_normalizado, ms06_valor, ms07_valor)
        if valor is not None
    ]

    if not valores:
        return None

    return sum(valores) / len(valores)


def determinar_estado_codificacion(
    *,
    indice_calidad,
    indice_seguridad,
    correcciones_necesarias: list,
    precisiones_necesarias: list,
    oportunidades_mejora: list,
    error_tecnico: bool = False,
):
    """
    Estado orientativo determinístico, decidido por los PORCENTAJES (nunca
    por el LLM) con el umbral único de core/umbral_aprobacion.py:

    - Fallo técnico -> ERROR.
    - Algún índice evaluable <= 80 %, o ningún índice evaluable -> CORREGIR.
    - Todos los índices evaluables > 80 % -> CONFORME, o CONFORME CON MEJORAS
      si el Evaluador dejó hallazgos (quedan como mejoras, no cambian el estado).
    Un índice no_evaluable (None) no se convierte en 0.
    """
    if error_tecnico:
        return "ERROR"

    evaluables = [indice for indice in (indice_calidad, indice_seguridad) if indice is not None]
    if not evaluables or not all(supera_umbral(indice) for indice in evaluables):
        return "CORREGIR"

    if correcciones_necesarias or precisiones_necesarias or oportunidades_mejora:
        return "CONFORME CON MEJORAS"

    return "CONFORME"
