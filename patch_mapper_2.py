import os
import re

filepath = r"c:\Users\PC\Desktop\PROYECTO DE GRADO\modelo-multiagente-dev\integrations\issue_mapper.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. VALORES_DESCONOCIDOS
old_valores = 'VALORES_DESCONOCIDOS = {"", "desconocido", "desconocida", "n/a", "no especificado", "sin información"}'
new_valores = 'VALORES_DESCONOCIDOS = {\n    "", "desconocido", "desconocida", "n/a", "no especificado",\n    "sin información", "ninguna", "ninguna.", "ninguno", "ninguno."\n}'
content = content.replace(old_valores, new_valores)

# 2. extraer_lista
old_extraer_lista = '''    def extraer_lista(text: str) -> list:
        # La plantilla oficial admite viñetas Markdown o un elemento por línea.
        items = []
        for line in text.split('\\n'):
            line = line.strip()
            if not line or re.fullmatch(r"---+", line):
                continue
            clean_item = re.sub(r"^(?:[-*+]\\s+|\\d+[.)]\\s*)", "", line).strip()
            if clean_item:
                items.append(clean_item)
        return items'''

new_extraer_lista = '''    def extraer_lista(text: str) -> list:
        # La plantilla oficial admite viñetas Markdown o un elemento por línea.
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line or re.fullmatch(r"---+", line):
                continue
            clean_item = re.sub(
                r"^(?:[-*+]\\s+|\\d+[.)]\\s*)",
                "",
                line,
            ).strip()
            if not clean_item:
                continue
            if clean_item.casefold() in VALORES_DESCONOCIDOS:
                continue
            items.append(clean_item)
        return items'''
content = content.replace(old_extraer_lista, new_extraer_lista)

# 3. historia_id
old_historia = '''    historia_id = (
        f"HU-{int(historia_match.group(1)):03d}"
        if historia_match else f"HU-{int(issue.iid):03d}"
    )'''
new_historia = '''    historia_id = (
        f"HU-{int(historia_match.group(1)):03d}"
        if historia_match else ""
    )'''
content = content.replace(old_historia, new_historia)

# 4. parsed_json issue_iid
old_parsed = '''    parsed_json = {
        "id": str(issue.iid),
        "historia_id": historia_id,'''
new_parsed = '''    parsed_json = {
        "id": str(issue.iid),
        "issue_iid": int(issue.iid),
        "historia_id": historia_id,'''
content = content.replace(old_parsed, new_parsed)

# 5. add preparar_payload_central at the end of the file
payload_func = '''
def preparar_payload_central(issue_data: dict) -> dict:
    return {
        "issue_iid": issue_data["issue_iid"],
        "historia_id": issue_data.get("historia_id", ""),
        "titulo": issue_data.get("titulo", ""),
        "actor": issue_data.get("actor", ""),
        "funcionalidad": issue_data.get("funcionalidad", ""),
        "objetivo": issue_data.get("objetivo", ""),
        "criterios_aceptacion": issue_data.get(
            "criterios_aceptacion", []
        ),
        "restricciones": issue_data.get("restricciones", []),
        "seguridad": issue_data.get("seguridad", {}),
        "prioridad": issue_data.get("prioridad", ""),
        "observaciones": issue_data.get("observaciones", ""),
        "validacion_entrada": issue_data.get(
            "validacion_entrada", {}
        ),
    }
'''
if "def preparar_payload_central" not in content:
    content += payload_func

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched issue_mapper.py")
