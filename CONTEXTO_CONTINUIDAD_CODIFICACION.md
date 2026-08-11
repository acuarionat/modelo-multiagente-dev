# Contexto de Continuidad — Etapa de Codificación v1.0

**Fecha de implementación:** 2026-08-10  
**Fecha de revisión/corrección:** 2026-08-11  
**Responsable de continuidad:** Modelo Multiagente  
**Versión de etapa:** Descubrimiento y Validación — Pre-Análisis

**Nota de revisión (2026-08-11):** Tras una auditoría posterior a la implementación
inicial se detectaron y corrigieron 6 defectos reales (paginación de GitLab
truncando el árbol a ~20 ítems, manejo incorrecto de `archivos_declarados`
como lista de dicts, nombres de columnas inventados al resolver trazabilidad
contra la matriz de Diseño, una clave de contrato con nombre distinto al
especificado, y lógica de ecosistemas/herramientas inventada más allá de lo
pedido). Ver sección "Correcciones aplicadas 2026-08-11" al final de este
documento para el detalle completo.

---

## Resumen Ejecutivo

Se implementó la **primera fase de la Etapa de Codificación**, consistente en:

✅ **Descubrimiento automático del repositorio** (sin ejecutar herramientas aún)
✅ **Detección de tecnologías y ecosistemas**
✅ **Selección automática de herramientas**
✅ **Validación de Issues COD contra la matriz de Diseño**
✅ **Información técnica presentada en UI**
✅ **Snapshots de contexto pre-análisis**

**Estado:** ✅ Completamente funcional hasta el punto inmediatamente anterior a ejecutar Radon/ESLint/Semgrep/npm-audit/pip-audit/Gitleaks.

---

## Cambios de Arquitectura

### 1. Ampliaciones en GitLabAdapter

**Archivo:** `integrations/gitlab_adapter.py`

Se agregaron 4 métodos genéricos nuevos (primitivas):

- `obtener_lenguajes_repositorio()` → Dict[str, float]
  - Retorna: `{"TypeScript": 83.4, "JavaScript": 10.2, ...}`
  
- `obtener_rama_predeterminada()` → str
  - Retorna: `"main"` o la rama configurada en GitLab
  
- `obtener_arbol_repositorio(ref=None)` → List[Dict]
  - Retorna árbol normalizado sin límite de recursión
  - `[{"nombre": "src", "ruta": "src", "tipo": "directorio"}, ...]`
  
- `obtener_archivo_repositorio(ruta, ref=None)` → bytes
  - Lee archivos individuales vía GitLab API (para leer manifiestos)

**Impacto:** No modifica lógica existente, solo agrega capacidades. Retro-compatible.

---

### 2. Módulos Nuevos de Análisis de Código

#### `core/code_analysis/repository_discovery.py`

Centro del descubrimiento previo. Combina:
- GitLab API (lenguajes, rama, árbol)
- Clasificación local de extensiones (EXTENSIONES_CODIGO)
- Identificación de manifiestos/lockfiles/config

**Función principal:** `descubrir_repositorio(adapter, ref=None) → dict`

Salida:
```json
{
  "estado": "OK",
  "rama": "main",
  "lenguajes": [{"nombre": "TypeScript", "porcentaje": 83.4}],
  "directorios": ["src", "src/components"],
  "archivos": ["src/App.tsx"],
  "archivos_codigo": ["src/App.tsx"],
  "manifiestos": ["package.json"],
  "lockfiles": ["package-lock.json"],
  "archivos_configuracion": ["tsconfig.json", "vite.config.ts"],
  "total_archivos": 86,
  "total_directorios": 14
}
```

#### `core/code_analysis/technology_detector.py`

Detecta frameworks, librerías y plataformas sin invocar LLM.

**Función principal:** `detectar_tecnologias(descubrimiento, adapter=None) → dict`

Evidencia usada:
- Lenguajes de GitLab
- Contenido de package.json (si existe)
- Archivos de configuración (vite.config.ts, jest.config.js, etc.)
- Manifiestos (Dockerfile, firebase.json, etc.)

Salida:
```json
{
  "lenguajes": [...],
  "ecosistemas": [
    {
      "id": "node",
      "nombre": "Node.js",
      "evidencias": ["package.json", "package-lock.json"],
      "gestor_dependencias": "npm"
    }
  ],
  "tecnologias_detectadas": [
    {"nombre": "TypeScript", "tipo": "lenguaje"},
    {"nombre": "React", "tipo": "framework", "evidencia": "package.json"}
  ]
}
```

#### `core/code_analysis/repository_profile.py`

Perfil técnico consolidado reutilizable por UI, PDF y DOCX.

**Función principal:** `construir_perfil_repositorio(descubrimiento, tecnologias) → dict`

No contiene árbol completo (evita pasar 300 archivos al LLM). Resume:
```json
{
  "rama": "main",
  "lenguajes": [...],
  "ecosistemas": [...],
  "frameworks_tecnologias": ["React", "Vite", "Firebase"],
  "estructura": {
    "total_archivos": 86,
    "total_directorios": 14,
    "archivos_codigo": 61
  },
  "manifiestos": ["package.json"],
  "lockfiles": ["package-lock.json"],
  "archivos_configuracion": [...]
}
```

#### `core/code_analysis/tool_selector.py`

Selecciona automáticamente qué herramientas se necesitan.

**Función principal:** `seleccionar_herramientas(repository_profile) → dict`

Lógica de decisión (sin LLM):
- **TypeScript/JavaScript** → ESLint para MC-05
- **Python** → Radon para MC-05
- **Todos los lenguajes** → Semgrep para MS-05
- **Node.js** → npm-audit para MS-06
- **Python** → pip-audit para MS-06
- **Todos** → Gitleaks para MS-07

Salida:
```json
{
  "MC-05": {
    "tipo": "complejidad_ciclomatica",
    "herramienta": "eslint",
    "adaptador": "eslint_complexity",
    "aplica_a": ["TypeScript", "JavaScript"],
    "estado": "pendiente"
  },
  ...
}
```

**Importante:** NO ejecuta las herramientas, solo decide cuáles se necesitan.

---

### 3. Contexto Pre-Análisis

#### `core/coding_repository_context.py`

Combina todos los insumos previos a ejecutar herramientas:

**Función principal:** `construir_contexto_repository_codificacion(...) → dict`

Valida:
- Rutas declaradas en COD vs árbol del repositorio
- Elementos de Diseño declarados vs matriz heredada
- Resuelve RF/RNF vinculados a ED

Salida:
```json
{
  "repositorio": {...},
  "issues_validas": ["COD-001", "COD-002"],
  "issues_bloqueadas": 1,
  "problemas": [
    {
      "issue": "COD-003",
      "tipo": "rutas_invalidas",
      "detalle": ["src/inexistente.ts"]
    }
  ],
  "trazabilidad": {
    "COD-001": {
      "archivos_alcance": ["src/App.tsx", "src/components/App.tsx"],
      "elementos_diseno": ["ED-01", "ED-02"],
      "requisitos": ["RF-001", "RNF-001"]
    }
  },
  "herramientas_seleccionadas": {...},
  "estado_global": "OK" | "CON_ADVERTENCIAS" | "BLOQUEADO"
}
```

---

### 4. Agentes/Nodos de Orquestación

#### `agents/coding_repository_discovery.py`

Implementa 4 nodos en cadena:

1. **nodo_coding_repository_discovery(adapter, state)** → Descubre estructura
2. **nodo_coding_detect_technologies(adapter, state)** → Detecta tecnologías
3. **nodo_coding_select_tools(state)** → Selecciona herramientas
4. **nodo_coding_validate_and_contextualize(state)** → Valida y contextualiza

Cada nodo es puro (sin efectos secundarios) y actualiza el estado sin ejecutar herramientas.

---

### 5. Estado Ampliado

#### `core/state.py`

Se agregaron 6 campos nuevos al TypedDict `AgentState`:

```python
coding_repository_tree: Optional[List[Dict[str, str]]]           # Árbol completo
coding_repository_discovery: Optional[Dict[str, Any]]           # {"rama", "lenguajes", ...}
coding_repository_profile: Optional[Dict[str, Any]]             # Perfil técnico
coding_detected_technologies: Optional[Dict[str, Any]]          # {"ecosistemas", "tecnologias_detectadas"}
coding_selected_tools: Optional[Dict[str, Dict[str, Any]]]     # MC-05, MS-05, MS-06, MS-07
coding_repository_context: Optional[Dict[str, Any]]            # Contexto combinado
```

Todos son independientes de campos de Diseño. No se reutilizan.

---

### 6. Interfaz de Usuario

#### `core/coding_ui.py`

**Nuevas funciones:**

- `descubrir_y_perfilar_repositorio(adapter, state)` → Ejecuta pipeline de 4 nodos
- `render_coding_repository_info(session, adapter)` → Renderiza información técnica

**Nueva sección en render_coding_stage():**

Se insertó **Apartado C: Información técnica del repositorio** con:

✅ Rama analizada  
✅ Tabla de lenguajes (nombre + porcentaje)  
✅ Ecosistemas y gestores detectados  
✅ Frameworks y tecnologías principales  
✅ Expander: Manifiestos y lockfiles  
✅ Expander: Archivos de configuración  
✅ Expander: Estructura del repositorio (primeros 20 elementos)  
✅ Tabla: Herramientas seleccionadas (Métrica | Tipo | Herramienta | Aplica a | Estado: PENDIENTE)  

**Lógica de control:**

- Botón "Analizar repositorio" → Ejecuta los nodos
- Información se muestra en expanders (UI limpia)
- Estado global muestra advertencias si hay problemas
- Bloquea ejecución del análisis si hay errores de rutas

---

## Snapshots Pre-Análisis

Se implementó captura de fotografía consistente al pulsar "Iniciar análisis de Codificación":

```python
session["coding_repository_snapshot"] = {
    "timestamp": "2026-08-10T...",
    "repository_profile": {...},
    "repository_discovery": {...},
    "detected_technologies": {...},
    "selected_tools": {...},
    "repository_context": {...},
}
session["coding_issue_snapshot"] = [...]
session["coding_matriz_snapshot"] = [...] # Ya existía
```

El análisis trabaja sobre esta fotografía consistente.

---

## Restricciones Respetadas

✅ NO se modificó lógica de Requerimientos ni Diseño  
✅ NO se tocaron agentes LLM de Codificación  
✅ NO se ejecutaron Radon/ESLint/Semgrep/npm-audit/pip-audit/Gitleaks  
✅ NO se mantuvo árbol completo (solo 20 elementos en UI, perfil consolidado para docs)  
✅ NO se creó workspace/descarga de código (flujo vía API)  
✅ Se limitaron cambios a GitLabAdapter, core/state.py, nuevos módulos y coding_ui.py  

---

## Flujo Resultante

```
Proyecto configurado
    ↓
GitLab ya validado
    ↓
Matriz de Trazabilidad — Etapa Diseño (A)
    ↓
Issues COD (B)
    ↓
🆕 Descubrimiento automático del repositorio (C)
    │
    ├── Rama + Lenguajes + Árbol
    ├── Clasificación de manifiestos/lockfiles
    ├── Detección de tecnologías
    ├── Selección de herramientas
    └── Validación COD ↔ ED ↔ repositorio
    ↓
Información técnica en UI
    │
    ├── Rama, lenguajes, estructura
    ├── Ecosistemas y frameworks
    ├── Herramientas seleccionadas (PENDIENTE)
    └── Expanders: archivos, configuración
    ↓
Snapshot (fotografía consistente)
    ↓
🔘 "Iniciar análisis de Codificación"
    ↓
AQUÍ recién comenzarían las herramientas (FASE POSTERIOR)
```

---

## Próximas Fases

### Fase 2: Ejecución de Herramientas
- Ejecutar ESLint/Radon (MC-05)
- Ejecutar Semgrep (MS-05)
- Ejecutar npm-audit/pip-audit/etc (MS-06)
- Ejecutar Gitleaks (MS-07)
- Normalizar salidas

### Fase 3: Documentación de Contexto Técnico en PDF/DOCX
- Sección 3: Contexto técnico del repositorio
  - 3.1 Rama analizada
  - 3.2 Lenguajes
  - 3.3 Tecnologías y ecosistemas
  - 3.4 Estructura general
  - 3.5 Manifiestos y archivos de configuración

---

## Validación Técnica

✅ Todos los archivos Python compilan sin errores  
✅ Funciones son puras (sin efectos secundarios) y testeables  
✅ Estado es independiente (no reutiliza Diseño)  
✅ No hay ejecución de herramientas  
✅ UI muestra información clara y organizada  
✅ Snapshots capturan estado consistente  

---

## Notas para el Siguiente Desarrollador

1. **GitLabAdapter es genérico:** Los 4 métodos nuevos no están acoplados a Codificación. Pueden reutilizarse en futuras etapas.

2. **repository_discovery vs repository_profile:** El árbol completo se guarda en state para validación interna. El perfil consolidado se usa para UI/docs (sin abrumar con 300 archivos).

3. **tool_selector es determinístico:** No usa LLM. La lógica está en Python y es fácil de mantener/extender.

4. **Snapshots son fotografías:** Se toman justo antes de ejecutar herramientas. El análisis debe trabajar sobre estos snapshots, no valores cambiantes.

5. **Las herramientas vienen después:** El grafo `construir_grafo_codificacion()` debe leer `coding_selected_tools` del estado y ejecutar cada una. No implementado en esta fase.

6. **Matriz heredada:** `coding_matrix_input` es la matriz de Diseño vigente. Los COD se validan contra ésta, no se crea una matriz nueva de Codificación aún.

---

## Correcciones aplicadas 2026-08-11 (auditoría posterior a la implementación)

Tras solicitud explícita de revisar la implementación, se detectaron y corrigieron los
siguientes defectos reales antes de dar la etapa por completa:

1. **Paginación truncada en `obtener_arbol_repositorio` (`integrations/gitlab_adapter.py`).**
   La llamada a `project.repository_tree(...)` sin `get_all=True` devolvía solo la
   primera página (~20 ítems) de cada nivel del árbol, y además se recorría
   directorio por directorio con `recursive=False` (N+1 llamadas). Se reemplazó por
   una única llamada `repository_tree(ref=ref, recursive=True, get_all=True)`, que
   usa el soporte recursivo nativo de GitLab y trae el árbol completo.

2. **`archivos_declarados` tratado como lista de strings (`core/coding_repository_context.py`).**
   `mapear_issue_codificacion` (en `integrations/coding_issue_mapper.py`) produce
   una lista de dicts `{"ruta":..., "descripcion":...}`, no strings. El código
   comparaba el dict completo contra el set de rutas del repositorio, por lo que
   ninguna ruta declarada podía validarse jamás. Se corrigió extrayendo
   `item.get("ruta") if isinstance(item, dict) else item`, siguiendo el mismo
   patrón ya usado en `integrations/code_repository_service.py:137`.

3. **Nombres de columnas inventados al resolver trazabilidad contra la matriz de Diseño.**
   El código buscaba `fila.get("elem_id")`, `fila.get("ED-xxx")`, `fila.get("rf_id")`,
   `fila.get("rnf_id")` — campos que no existen. El contrato real de
   `construir_filas_matriz_diseno` (`core/design_traceability.py`) usa las columnas
   `"HU origen"`, `"Código requisito"`, `"Diseño"`, `"Elementos de Diseño"` (texto
   separado por comas, p. ej. `"ED-01, ED-02"`). Se reescribió `_resolver_trazabilidad_desde_matriz`
   para parsear esa columna correctamente y devolver también `disenos` e `historias`
   (que faltaban), alineado con el ejemplo literal de la sección 9 de las
   indicaciones. Además, la extracción de `elementos_diseno_vigentes` ahora reutiliza
   `extraer_elementos_diseno_validos` de `core/coding_matrix_input.py` en lugar de
   duplicar (e implementar mal) esa lógica.

4. **Clave de contrato con nombre distinto al especificado (`repository_discovery.py`).**
   La sección 3 de las indicaciones especifica la clave `"configuracion_tecnica"`
   en la salida de `descubrir_repositorio()`. Se había usado `"archivos_configuracion"`
   por error (ese nombre corresponde solo a la salida de `repository_profile.py`,
   sección 6). Se corrigió `repository_discovery.py` para emitir `configuracion_tecnica`,
   y se ajustaron los consumidores (`repository_profile.py`, `technology_detector.py`)
   para leer esa clave y seguir exponiendo `archivos_configuracion` en el perfil final,
   tal como pide cada sección literalmente.

5. **`EXTENSIONES_CODIGO`, `MANIFESTS` y `LOCKFILES` con entradas no solicitadas.**
   Se habían agregado extensiones (`.cpp`, `.c`, `.rs`, `.swift`, `.kt`) y archivos
   (`setup.py`, `go.mod`, `Cargo.toml`, `Gemfile`, etc.) que no estaban en los
   literales `{ ... }` dados en la sección 3 de las indicaciones. Se restauraron
   los tres sets exactamente como fueron especificados.

6. **Ecosistemas y herramientas inventados más allá de los dos ejemplos dados.**
   `technology_detector.py` detectaba ecosistemas Go/Rust (dependientes de
   `go.mod`/`Cargo.toml`, ya fuera de los MANIFESTS reales) y frameworks Vue/Angular/
   Express, y un bloque que buscaba `"fastapi"` dentro de `package.json` (imposible:
   FastAPI es un paquete Python, nunca aparece en dependencias npm). `tool_selector.py`
   seleccionaba herramientas ficticias (`jdepend`, `gocyclo`, `nancy`, `cargo-audit`,
   `dependency-check`) para Java/Go/Rust/PHP/C#, ninguna mencionada en las
   indicaciones. Se recortó ambos módulos a exactamente los dos ejemplos dados
   (Node/TS → ESLint/npm-audit, Python → Radon/pip-audit), más MS-05 (Semgrep) y
   MS-07 (Gitleaks) que aplican siempre. La detección de React/Vite/Firebase se
   mantuvo (explícitamente nombrados en la sección 5 de las indicaciones).

**Validación:** se compilaron todos los módulos tocados (`python -m py_compile`,
sin errores) y se ejecutó una prueba end-to-end con un adapter simulado que
reproduce el formato real de `mapear_issue_codificacion` y
`construir_filas_matriz_diseno` — cubriendo descubrimiento, detección de
tecnologías, selección de herramientas, expansión de carpetas declaradas en un
COD, bloqueo por elemento de Diseño inexistente, y resolución correcta de
DIS/RF/HU. Todas las aserciones pasaron.
