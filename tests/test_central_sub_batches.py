import json
import os

from agents.central_agent import procesar_central_en_sublotes


# ---------------------------------------------------------
# Configuración controlada
# ---------------------------------------------------------

os.environ["CENTRAL_BATCH_SIZE"] = "1"
os.environ["CENTRAL_MAX_TECHNICAL_RETRIES"] = "0"


# ---------------------------------------------------------
# HU-001 ya estructurada como la entrega IssueMapper
# ---------------------------------------------------------

issues = [
    {
        "id": "6",                 # compatibilidad legacy
        "issue_iid": 6,            # identidad técnica GitLab
        "historia_id": "HU-001",   # identidad documental
        "titulo": "HU-001 - Consultar horarios disponibles",
        "descripcion_original": """
# Historia de Usuario

## Descripción
El paciente necesita consultar los horarios disponibles de los médicos antes de solicitar una cita.

## Como
Paciente

## Quiero
Consultar los horarios disponibles de los médicos.

## Para
Programar una cita médica sin conflictos de horario.
""".strip(),

        "actor": "Paciente",

        "funcionalidad": (
            "Consultar los horarios disponibles de los médicos."
        ),

        "objetivo": (
            "Programar una cita médica sin conflictos de horario."
        ),

        "criterios_aceptacion": [
            "Mostrar únicamente horarios disponibles.",
            "Mostrar el nombre y especialidad del médico.",
            "Actualizar la disponibilidad inmediatamente después de registrar una cita.",
        ],

        "restricciones": [
            "Solo pacientes autenticados pueden acceder.",
            "La información debe mostrarse en tiempo real.",
        ],

        "seguridad": {
            "descripcion": "",
            "maneja_datos_sensibles": True,
            "tipos_datos_sensibles": [
                "Datos personales"
            ],
            "autenticacion": "Usuario y contraseña.",
            "autorizacion_roles": "Paciente.",
            "auditoria": "Sí. Registrar las consultas realizadas.",
        },

        "prioridad": "Desconocida",

        "observaciones": (
            "La consulta debe responder en menos de tres segundos."
        ),

        "labels": ["Pendiente"],

        "validacion_entrada": {
            "estado": "entrada_con_advertencias",
            "campos_faltantes": [],
            "advertencias": [
                "prioridad no especificada"
            ],
        },
    }
]


# ---------------------------------------------------------
# Ejecutar EXCLUSIVAMENTE Central
# ---------------------------------------------------------

resultado, diagnostico = procesar_central_en_sublotes(
    project_name="modelo-multiagente-dev",
    issues=issues,
    sprint_context="Recepción de Requerimientos",
    batch_size=1,
)


# ---------------------------------------------------------
# Mostrar resultado
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("RESULTADO CENTRAL")
print("=" * 70)

print(
    json.dumps(
        resultado,
        ensure_ascii=False,
        indent=2,
    )
)


print("\n" + "=" * 70)
print("RESUMEN DE EJECUCIÓN")
print("=" * 70)

summary = diagnostico.get("summary", {})

print(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    )
)


print("\n" + "=" * 70)
print("VALIDACIÓN PRINCIPAL")
print("=" * 70)

print("Expected:     ", summary.get("expected_issue_ids"))
print("Traceable:    ", summary.get("traceable_issue_ids"))
print("Successful:   ", summary.get("successful_issue_ids"))
print("Insufficient: ", summary.get("insufficient_issue_ids"))
print("Error:        ", summary.get("error_issue_ids"))
print("Missing:      ", summary.get("missing_issue_ids"))
print("Calls:        ", summary.get("total_calls"))
print("Retries:      ", summary.get("technical_retries"))
print("Repairs:      ", summary.get("selective_repairs"))