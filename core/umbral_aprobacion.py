"""
Umbral único de aprobación para todas las etapas (Requerimientos, Diseño,
Codificación y Pruebas). Es la ÚNICA fuente del umbral: ningún módulo debe
declarar su propio valor ni comparar "a mano".

Regla (estricta):
- porcentaje  > 80 %  -> se aprueba  (etiqueta GitLab "Revisada").
- porcentaje <= 80 %  -> se corrige  (etiqueta GitLab "Requiere modificación").

La comparación se hace sobre el porcentaje redondeado a 2 decimales, el
mismo que se muestra en la interfaz y en los documentos. Así un valor que
se presenta como "80.0 %" nunca se aprueba por un residuo de coma flotante
(p. ej. 0.1 * 8 = 0.8000000000000002).
"""

UMBRAL_APROBACION = 0.80


def porcentaje(valor):
    """Valor en [0, 1] -> porcentaje redondeado a 2 decimales (None si no hay valor numérico)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return round(valor * 100, 2)


def supera_umbral(valor):
    """True si el porcentaje es estrictamente mayor al 80 %, False si es menor
    o igual, None si no hay valor evaluable (no se convierte en 0)."""
    valor_porcentaje = porcentaje(valor)
    if valor_porcentaje is None:
        return None
    return valor_porcentaje > porcentaje(UMBRAL_APROBACION)
