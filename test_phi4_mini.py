import json
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama


def main() -> None:
    llm = ChatOllama(
        model="phi4-mini",
        base_url="http://localhost:11434",
        temperature=0,
        format="json",
        num_ctx=4096,
    )

    system_prompt = """
Eres un analista de requisitos de software.

Tu tarea consiste únicamente en extraer y verificar información explícita
de una historia de usuario.

Definiciones obligatorias:

1. actor_identificado:
   Es verdadero cuando existe un valor después del campo "Como".

2. funcionalidad_identificada:
   Es verdadero cuando existe una acción después del campo "Quiero".

3. objetivo_identificado:
   Es verdadero cuando existe un beneficio después del campo "Para".

4. cantidad_criterios:
   Es el número exacto de elementos numerados incluidos bajo
   "Criterios de aceptación".

5. criterios_verificables:
   Es verdadero cuando cada criterio describe un resultado observable,
   una condición comprobable o un cambio de estado que pueda validarse
   mediante una prueba manual o automatizada.

   Son verificables, por ejemplo:
   - mostrar u ocultar información;
   - permitir o impedir una acción;
   - registrar, actualizar o eliminar datos;
   - comprobar que un valor cambió;
   - validar una condición específica.

   No son verificables expresiones vagas como:
   - "el sistema debe ser fácil";
   - "la aplicación debe funcionar bien";
   - "la respuesta debe ser rápida", sin indicar un límite medible.

   Evalúa cada criterio individualmente.
   Si todos los criterios son observables o comprobables,
   criterios_verificables debe ser true.

6. historia_completa:
   Es verdadero cuando están presentes actor, funcionalidad y objetivo.

Debes evaluar exclusivamente el texto recibido.
No debes reinterpretar la historia ni cuestionar si representa una
interacción real con el sistema.
No inventes información.
No omitas datos explícitos.

Responde exclusivamente con un objeto JSON válido.
No uses Markdown ni bloques de código.
"""

    historia = """
HISTORIA DE USUARIO

Descripción:
El paciente necesita consultar los horarios disponibles de los médicos
antes de solicitar una cita.

Como:
Paciente

Quiero:
Consultar los horarios disponibles de los médicos.

Para:
Programar una cita médica sin conflictos de horario.

Criterios de aceptación:
1. Mostrar únicamente horarios disponibles.
2. Mostrar el nombre y especialidad del médico.
3. Actualizar la disponibilidad después de registrar una cita.
"""

    human_prompt = f"""
Analiza la siguiente historia de usuario:

{historia}

Devuelve exactamente esta estructura:

{{
  "historia_completa": true,
  "actor_identificado": true,
  "funcionalidad_identificada": true,
  "objetivo_identificado": true,
  "cantidad_criterios": 3,
  "criterios_verificables": true,
  "justificacion": "Explicación basada únicamente en los datos encontrados"
}}

Los valores mostrados en la estructura representan el formato esperado,
pero debes obtenerlos examinando el texto proporcionado.
"""

    inicio = time.perf_counter()

    try:
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt),
            ]
        )
    except Exception as exc:
        print("\nRESULTADO: ERROR AL INVOCAR EL MODELO")
        print(f"Error: {exc}")
        return

    duracion = time.perf_counter() - inicio
    content = str(response.content).strip()

    print("\n--- RESPUESTA ORIGINAL ---")
    print(content)
    print(f"\nTiempo: {duracion:.2f} segundos")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        print("\nRESULTADO: JSON INVÁLIDO")
        print(f"Error: {exc}")
        return

    print("\n--- JSON INTERPRETADO ---")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))

    campos_requeridos = {
        "historia_completa",
        "actor_identificado",
        "funcionalidad_identificada",
        "objetivo_identificado",
        "cantidad_criterios",
        "criterios_verificables",
        "justificacion",
    }

    faltantes = campos_requeridos - parsed.keys()

    if faltantes:
        print(f"\nRESULTADO: FALTAN CAMPOS: {sorted(faltantes)}")
        return

    resultado_esperado = {
        "historia_completa": True,
        "actor_identificado": True,
        "funcionalidad_identificada": True,
        "objetivo_identificado": True,
        "cantidad_criterios": 3,
        "criterios_verificables": True,
    }

    errores = []

    for campo, valor_esperado in resultado_esperado.items():
        valor_recibido = parsed.get(campo)

        if valor_recibido != valor_esperado:
            errores.append(
                f"{campo}: esperado={valor_esperado}, "
                f"recibido={valor_recibido}"
            )

    if errores:
        print("\nRESULTADO: ANÁLISIS INCORRECTO")

        for error in errores:
            print(f"- {error}")

        return

    print("\nRESULTADO: PRUEBA COMPLETA SUPERADA")


if __name__ == "__main__":
    main()