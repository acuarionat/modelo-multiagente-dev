"""
Fixtures de regresión para el módulo de Diseño (trazabilidad, exportación,
comentario de GitLab).

Estos valores NO son inventados: son capturas literales de respuestas reales
de NVIDIA (Design_Central) y Groq (Design_Quality/Design_Security), obtenidas
en ejecuciones reales previas de tests/test_design_full_flow.py durante esta
misma sesión (DIS-001 = issue_iid 16, DIS-002 = issue_iid 17, proyecto real
de GitLab "elanvital"). Se congelan aquí para poder probar la lógica de
trazabilidad/exportación/comentario sin volver a consumir la cuota diaria de
Groq. Las pruebas de integración reales contra Groq/NVIDIA siguen existiendo
en tests/test_design_full_flow.py, tests/test_design_quality.py,
tests/test_design_security.py y tests/test_design_evaluator.py.
"""

RESULTADOS_CENTRAL_DISENO = [
    {
        "issue_iid": 16,
        "diseno_id": "DIS-001",
        "trazabilidad_diseno": [
            {
                "requisito": "RF-001",
                "elementos_relacionados": ["ED-01", "ED-02", "ED-03"],
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-001): responsabilidad documentada de los elementos cubre el requisito.",
                "confianza": "alta",
            },
            {
                "requisito": "RF-002",
                "elementos_relacionados": ["ED-01"],
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-001): responsabilidad documentada del elemento cubre el requisito.",
                "confianza": "alta",
            },
            {
                "requisito": "RF-003",
                "elementos_relacionados": ["ED-02", "ED-03"],
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-001): responsabilidad documentada de los elementos cubre el requisito.",
                "confianza": "alta",
            },
        ],
        "requisitos_sin_relacion_evidente": [
            {
                "requisito": "RNF-001",
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-001): no existe evidencia suficiente en este Issue para relacionarlo con un elemento concreto.",
                "confianza": "alta",
            },
            {
                "requisito": "RNF-002",
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-001): no existe evidencia suficiente en este Issue para relacionarlo con un elemento concreto.",
                "confianza": "alta",
            },
        ],
    },
    {
        "issue_iid": 17,
        "diseno_id": "DIS-002",
        "trazabilidad_diseno": [
            {
                "requisito": "RF-004",
                "elementos_relacionados": ["ED-05"],
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-002): responsabilidad documentada del elemento cubre el requisito.",
                "confianza": "alta",
            },
            {
                "requisito": "RF-005",
                "elementos_relacionados": ["ED-04", "ED-05", "ED-06"],
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-002): responsabilidad documentada de los elementos cubre el requisito.",
                "confianza": "alta",
            },
            {
                "requisito": "RF-006",
                "elementos_relacionados": ["ED-05", "ED-06"],
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-002): responsabilidad documentada de los elementos cubre el requisito.",
                "confianza": "alta",
            },
        ],
        "requisitos_sin_relacion_evidente": [
            {
                "requisito": "RF-007",
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-002): no existe evidencia suficiente en este Issue para relacionarlo con un elemento concreto.",
                "confianza": "alta",
            },
            {
                "requisito": "RF-008",
                "justificacion": "Captura real de Design_Central (NVIDIA, DIS-002): no existe evidencia suficiente en este Issue para relacionarlo con un elemento concreto.",
                "confianza": "alta",
            },
        ],
    },
]

EVALUACION_POR_DISENO = {
    "DIS-001": "CORREGIR",
    "DIS-002": "CORREGIR",
}

DESIGN_SUMMARY_POR_DISENO = {
    "DIS-001": {
        "issue_iid": 16,
        "diseno_id": "DIS-001",
        "metricas": {
            "MC-03": {"valor": 1.0, "numerador": 3, "denominador": 3, "estado": "calculada"},
            "MC-04": {"valor": 1.0, "numerador": 3, "denominador": 3, "estado": "calculada"},
            "MS-03": {"valor": 0.6666666666666666, "numerador": 2, "denominador": 3, "estado": "calculada"},
            "MS-04": {"valor": 0.75, "numerador": 3, "denominador": 4, "estado": "calculada"},
        },
        "indice_calidad_diseno": 1.0,
        "indice_seguridad_diseno": 0.7083333333333333,
        "estado_orientativo": "CORREGIR",
        "correcciones_necesarias": [
            "Definir y documentar un tratamiento específico para la amenaza de exposición innecesaria de información relacionada con los usuarios durante la consulta.",
            "Incorporar una medida de seguridad que cubra el control de protección del acceso a información sensible para garantizar la confidencialidad e integridad de los datos de horarios y pacientes.",
        ],
        "precisiones_necesarias": [],
        "oportunidades_mejora": [
            "Implementar técnicas de enmascaramiento o cifrado de datos en tránsito y reposo para mitigar la exposición de información sensible.",
            "Establecer un control de acceso a nivel de datos y un registro de acceso detallado para fortalecer la trazabilidad y seguridad de la información mostrada durante las consultas.",
        ],
    },
    "DIS-002": {
        "issue_iid": 17,
        "diseno_id": "DIS-002",
        "metricas": {
            "MC-03": {"valor": 1.0, "numerador": 3, "denominador": 3, "estado": "calculada"},
            "MC-04": {"valor": 1.0, "numerador": 3, "denominador": 3, "estado": "calculada"},
            "MS-03": {"valor": 1.0, "numerador": 4, "denominador": 4, "estado": "calculada"},
            "MS-04": {"valor": 0.75, "numerador": 3, "denominador": 4, "estado": "calculada"},
        },
        "indice_calidad_diseno": 1.0,
        "indice_seguridad_diseno": 0.875,
        "estado_orientativo": "CORREGIR",
        "correcciones_necesarias": [
            "Definir e incorporar una medida de seguridad concreta para el control faltante de protección de la información almacenada, asignando el elemento responsable correspondiente.",
        ],
        "precisiones_necesarias": [],
        "oportunidades_mejora": [
            "Mantener la documentación de los tratamientos de las amenazas y revisar periódicamente que las medidas continúen alineadas con los requisitos de seguridad.",
            "Considerar la implementación de cifrado en reposo o controles de acceso estrictos a la base de datos como medida específica para la protección de datos.",
        ],
    },
}

# Conclusiones reales del Evaluador de Diseño (NVIDIA), capturadas en la
# misma ejecución que DESIGN_SUMMARY_POR_DISENO. No forman parte de
# design_summary (nodo_design_central_final no las copia), por eso se
# fixturan aparte para los generadores de documentos.
CONCLUSIONES_EVALUADOR_DISENO = {
    "DIS-001": {
        "conclusion_calidad": "La calidad del diseño alcanza el máximo valor en las métricas MC-03 y MC-04 con un valor de 1.0 en ambas. La evidencia de MC-03 muestra que los elementos ED-01, ED-02 y ED-03 están completamente documentados, cubriendo sus responsabilidades e interacciones. Para MC-04, la evidencia confirma un acoplamiento aceptable entre los componentes, con dependencias unidireccionales y baja dependencia.",
        "conclusion_seguridad": "La seguridad del diseño presenta brechas parciales evidenciadas en los valores de MS-03 (0.67) y MS-04 (0.75). En MS-03, una de las tres amenazas documentadas —la exposición innecesaria de información de los usuarios— carece de tratamiento definido. En MS-04, falta un control específico de protección de datos para la información de horarios y pacientes.",
    },
    "DIS-002": {
        "conclusion_calidad": "La calidad del diseño muestra un cumplimiento total en la documentación de elementos y relaciones (MC-03 = 1.0) y en el acoplamiento de componentes (MC-04 = 1.0). La evidencia confirma que los elementos ED-04, ED-05 y ED-06 están documentados con sus responsabilidades y relaciones, cubriendo los requisitos RF-004, RF-005 y RF-006.",
        "conclusion_seguridad": "La seguridad del diseño presenta una cobertura completa en la identificación y tratamiento de amenazas (MS-03 = 1.0). No obstante, la definición de controles de seguridad (MS-04 = 0.75) no está totalmente cumplida: falta una medida explícita para la protección del acceso a la información personal almacenada en ED-06.",
    },
}

# Salida real (estructura) del Agente de Seguridad de Diseño (Groq), misma
# ejecución de referencia que produjo MS-03/MS-04 en DESIGN_SUMMARY_POR_DISENO:
# DIS-001 = 3 amenazas (2 con tratamiento, 1 sin), 4 controles aplicables
# (3 definidos, falta "Protección de datos"). DIS-002 = 4 amenazas (todas con
# tratamiento), 4 controles aplicables (3 definidos, falta "Protección de
# datos" otra vez, ahora sobre ED-06).
RESULTADOS_SECURITY_DISENO = {
    "DIS-001": {
        "cobertura_amenazas": {
            "codigo": "MS-03",
            "amenazas_identificadas": [
                {"identidad": "Un usuario no autenticado podría intentar acceder a la consulta", "elementos_afectados": ["ED-01"], "tratamiento_documentado": True},
                {"identidad": "Un usuario podría intentar acceder a funciones de consulta sin estar autorizado", "elementos_afectados": ["ED-01", "ED-02"], "tratamiento_documentado": True},
                {"identidad": "Información relacionada con los usuarios podría quedar expuesta innecesariamente durante la consulta", "elementos_afectados": ["ED-01", "ED-02"], "tratamiento_documentado": False},
            ],
            "amenazas_con_tratamiento": [
                "Un usuario no autenticado podría intentar acceder a la consulta",
                "Un usuario podría intentar acceder a funciones de consulta sin estar autorizado",
            ],
            "amenazas_sin_tratamiento": [
                "Información relacionada con los usuarios podría quedar expuesta innecesariamente durante la consulta",
            ],
            "amenazas_necesarias_faltantes": [],
        },
        "cobertura_controles": {
            "codigo": "MS-04",
            "controles_aplicables": [
                {"control": "Verificación de sesión autenticada antes de la consulta", "aspecto_relacionado": "Autenticación", "confianza": "alta"},
                {"control": "Verificación de permisos de acceso a la funcionalidad de consulta", "aspecto_relacionado": "Autorización", "confianza": "alta"},
                {"control": "Registro de operaciones relevantes de consulta y actualización", "aspecto_relacionado": "Auditoría", "confianza": "alta"},
                {"control": "Protección del acceso a información de horarios y datos personales", "aspecto_relacionado": "Protección de datos", "confianza": "alta"},
            ],
            "controles_definidos": [
                {"control": "Verificación de sesión autenticada antes de la consulta", "medida_documentada": "Verificar que el usuario tenga una sesión autenticada antes de permitir la consulta", "elementos_responsables": ["ED-01"]},
                {"control": "Verificación de permisos de acceso a la funcionalidad de consulta", "medida_documentada": "Verificar que el usuario esté autorizado para acceder a la funcionalidad de consulta", "elementos_responsables": ["ED-02"]},
                {"control": "Registro de operaciones relevantes de consulta y actualización", "medida_documentada": "Registrar las consultas consideradas relevantes para mantener trazabilidad", "elementos_responsables": ["ED-02"]},
            ],
            "controles_faltantes": [
                {"control": "Protección del acceso a información de horarios y datos personales", "justificacion": "Se necesita una medida que garantice la confidencialidad e integridad de los datos de horarios y datos personales durante la consulta."},
            ],
        },
    },
    "DIS-002": {
        "cobertura_amenazas": {
            "codigo": "MS-03",
            "amenazas_identificadas": [
                {"identidad": "Un usuario no autorizado podría intentar registrar pacientes", "elementos_afectados": ["ED-04", "ED-05"], "tratamiento_documentado": True},
                {"identidad": "Un usuario no autorizado podría intentar modificar información existente", "elementos_afectados": ["ED-04", "ED-05"], "tratamiento_documentado": True},
                {"identidad": "Podría registrarse información incompleta o inválida", "elementos_afectados": ["ED-04", "ED-05"], "tratamiento_documentado": True},
                {"identidad": "Podría modificarse información sin conservar evidencia de la operación", "elementos_afectados": ["ED-05"], "tratamiento_documentado": True},
            ],
            "amenazas_con_tratamiento": [
                "Un usuario no autorizado podría intentar registrar pacientes",
                "Un usuario no autorizado podría intentar modificar información existente",
                "Podría registrarse información incompleta o inválida",
                "Podría modificarse información sin conservar evidencia de la operación",
            ],
            "amenazas_sin_tratamiento": [],
            "amenazas_necesarias_faltantes": [],
        },
        "cobertura_controles": {
            "codigo": "MS-04",
            "controles_aplicables": [
                {"control": "Verificación de sesión autenticada antes de acceder a la gestión de pacientes", "aspecto_relacionado": "Autenticación", "confianza": "alta"},
                {"control": "Comprobación de permisos para registrar o modificar información", "aspecto_relacionado": "Autorización", "confianza": "alta"},
                {"control": "Registro de operaciones relevantes de registro y modificación", "aspecto_relacionado": "Auditoría", "confianza": "alta"},
                {"control": "Protección del acceso a datos personales almacenados", "aspecto_relacionado": "Protección de datos", "confianza": "alta"},
            ],
            "controles_definidos": [
                {"control": "Verificación de sesión autenticada antes de acceder a la gestión de pacientes", "medida_documentada": "Verificar que exista una sesión autenticada antes de acceder a la gestión de pacientes", "elementos_responsables": ["ED-04"]},
                {"control": "Comprobación de permisos para registrar o modificar información", "medida_documentada": "Comprobar que el usuario tenga permiso para registrar o modificar información", "elementos_responsables": ["ED-05"]},
                {"control": "Registro de operaciones relevantes de registro y modificación", "medida_documentada": "Registrar las operaciones relevantes de registro y modificación", "elementos_responsables": ["ED-05"]},
            ],
            "controles_faltantes": [
                {"control": "Protección del acceso a datos personales almacenados", "justificacion": "No se ha documentado una medida de seguridad concreta que garantice la confidencialidad e integridad de los datos personales almacenados en ED-06."},
            ],
        },
    },
}
