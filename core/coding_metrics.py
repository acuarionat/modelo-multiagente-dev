"""
Cálculo determinístico (solo Python) de las métricas de Codificación, a
partir de la evidencia YA NORMALIZADA por core/code_analysis/ (nunca de
afirmaciones de un agente LLM). Ningún agente calcula estos valores: los
agentes de Calidad y Seguridad de Codificación solo los interpretan.

MC-06 está fuera de alcance en esta fase: el Índice de Calidad del Código
se define temporalmente como MC-05 (decisión de alcance documentada aquí,
no un cálculo definitivo).
"""

UMBRAL_MC05_SATISFACTORIO = 0.90
UMBRAL_MS06_SATISFACTORIO = 0.90
UMBRAL_MS07_SATISFACTORIO = 0.90


def calcular_mc05(evidencia_radon: dict) -> dict:
    """MC-05 Adecuación de la Complejidad Ciclomática = funciones con CC aceptable / funciones analizadas (Radon)."""
    estado_herramienta = (evidencia_radon or {}).get("estado")
    if estado_herramienta != "OK":
        return {
            "codigo": "MC-05", "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable",
            "motivo": (evidencia_radon or {}).get("detalle_error") or f"radon: estado {estado_herramienta!r}.",
        }

    funciones = (evidencia_radon.get("datos") or {}).get("funciones") or []
    denominador = len(funciones)
    if denominador == 0:
        return {
            "codigo": "MC-05", "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable", "motivo": "Radon no reportó funciones evaluables.",
        }

    numerador = sum(1 for funcion in funciones if funcion.get("aceptable") is True)
    valor = numerador / denominador

    return {
        "codigo": "MC-05", "valor": valor, "numerador": numerador, "denominador": denominador,
        "estado_calculo": "calculada",
        "satisfactorio": valor >= UMBRAL_MC05_SATISFACTORIO,
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
        "satisfactorio": valor >= UMBRAL_MS06_SATISFACTORIO,
    }


def calcular_ms07(evidencia_gitleaks: dict) -> dict:
    """MS-07 Cobertura de Código sin Secretos Expuestos = archivos sin secretos / archivos analizados (Gitleaks)."""
    estado_herramienta = (evidencia_gitleaks or {}).get("estado")
    if estado_herramienta != "OK":
        return {
            "codigo": "MS-07", "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable",
            "motivo": (evidencia_gitleaks or {}).get("detalle_error") or f"gitleaks: estado {estado_herramienta!r}.",
        }

    datos = evidencia_gitleaks.get("datos") or {}
    denominador = len(datos.get("archivos_analizados") or [])
    if denominador == 0:
        return {
            "codigo": "MS-07", "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable", "motivo": "Gitleaks no reportó archivos analizados.",
        }

    con_secretos = len(datos.get("archivos_con_secretos") or [])
    numerador = denominador - con_secretos
    valor = numerador / denominador

    return {
        "codigo": "MS-07", "valor": valor, "numerador": numerador, "denominador": denominador,
        "estado_calculo": "calculada",
        "satisfactorio": valor >= UMBRAL_MS07_SATISFACTORIO,
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
    correcciones_necesarias: list,
    precisiones_necesarias: list,
    oportunidades_mejora: list,
    error_tecnico: bool = False,
):
    """Estado orientativo determinístico: el Evaluador solo entrega categorías, Python decide el estado oficial."""
    if error_tecnico:
        return "ERROR"

    if correcciones_necesarias:
        return "CORREGIR"

    if precisiones_necesarias or oportunidades_mejora:
        return "CONFORME CON MEJORAS"

    return "CONFORME"
