"""
Test real (con conexión a GitLab) de obtener_arbol_repositorio().

NO ejecuta LLM.
NO ejecuta agentes.
NO genera métricas.
NO modifica Issues.
"""

from integrations.gitlab_adapter import GitLabAdapter

adapter = GitLabAdapter()

tree = adapter.obtener_arbol_repositorio()

print("TOTAL:", len(tree))

for item in tree:
    print(item["tipo"], item["ruta"])

rutas = {item["ruta"] for item in tree}

assert "src/App.tsx" in rutas
assert "src/App.css" in rutas
assert "package.json" in rutas
assert "package-lock.json" in rutas
assert "vite.config.ts" in rutas
