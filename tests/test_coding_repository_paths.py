"""
Test unitario de normalizar_ruta() y de la comparación de rutas COD
contra el árbol real del repositorio (core/coding_repository_context.py).

Reproduce el árbol tal como lo entrega
integrations.gitlab_adapter.GitLabAdapter.obtener_arbol_repositorio()
({"nombre", "ruta", "tipo"}) para las 9 rutas reales declaradas en
COD-001/COD-002.
"""

from core.coding_repository_context import normalizar_ruta

REPOSITORY_TREE_REAL = [
    {"nombre": ".env", "ruta": ".env", "tipo": "archivo"},
    {"nombre": ".firebaserc", "ruta": ".firebaserc", "tipo": "archivo"},
    {"nombre": ".gitignore", "ruta": ".gitignore", "tipo": "archivo"},
    {"nombre": "README.md", "ruta": "README.md", "tipo": "archivo"},
    {"nombre": "eslint.config.js", "ruta": "eslint.config.js", "tipo": "archivo"},
    {"nombre": "firebase.json", "ruta": "firebase.json", "tipo": "archivo"},
    {"nombre": "firestore.indexes.json", "ruta": "firestore.indexes.json", "tipo": "archivo"},
    {"nombre": "firestore.rules", "ruta": "firestore.rules", "tipo": "archivo"},
    {"nombre": "index.html", "ruta": "index.html", "tipo": "archivo"},
    {"nombre": "package-lock.json", "ruta": "package-lock.json", "tipo": "archivo"},
    {"nombre": "package.json", "ruta": "package.json", "tipo": "archivo"},
    {"nombre": "tsconfig.json", "ruta": "tsconfig.json", "tipo": "archivo"},
    {"nombre": "vite.config.ts", "ruta": "vite.config.ts", "tipo": "archivo"},
    {"nombre": "logo elanvita.jpeg", "ruta": "public/logo elanvita.jpeg", "tipo": "archivo"},
    {"nombre": "vite.svg", "ruta": "public/vite.svg", "tipo": "archivo"},
    {"nombre": "App.css", "ruta": "src/App.css", "tipo": "archivo"},
    {"nombre": "App.tsx", "ruta": "src/App.tsx", "tipo": "archivo"},
    {"nombre": "logo.jpg", "ruta": "src/assets/logo.jpg", "tipo": "archivo"},
    {"nombre": "react.svg", "ruta": "src/assets/react.svg", "tipo": "archivo"},
]

RUTAS_ESPERADAS = [
    "src/App.tsx",
    "src/App.css",
    "src/assets/logo.jpg",
    "public/logo elanvita.jpeg",
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    "tsconfig.json",
    "eslint.config.js",
]


def test_normalizar_rutas_cod_contra_arbol_real():
    rutas_repo = {
        normalizar_ruta(item["ruta"])
        for item in REPOSITORY_TREE_REAL
        if item["tipo"] == "archivo"
    }

    for ruta in RUTAS_ESPERADAS:
        resultado = "OK" if normalizar_ruta(ruta) in rutas_repo else "INVALIDA"
        print(ruta, resultado)
        assert resultado == "OK"
