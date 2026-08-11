# Plantilla de Issue COD-xxx (Codificación)

Copiar esta estructura al crear un Issue de Codificación en GitLab, dentro
del milestone "Codificación". El título debe contener el identificador
`COD-XXX` (por ejemplo: `COD-001 — Servicio de autenticación`).

`integrations/coding_issue_mapper.py` depende de los encabezados exactos
que aparecen a continuación (el prefijo numérico "## 1." es opcional al
parsear, pero debe conservarse el texto del encabezado).

```markdown
# COD-001 — Nombre de la implementación

## 1. Descripción de la implementación

Descripción en texto libre de qué se implementó y por qué.

## 2. Elementos de Diseño implementados

- ED-01
- ED-02
- ED-03

## 3. Ubicación de la implementación

| Archivo/Módulo | Descripción |
|---|---|
| core/ejemplo_servicio.py | Implementa la lógica principal del elemento ED-01. |
| core/ejemplo_repositorio.py | Acceso a datos para ED-02. |

## 4. Decisiones de implementación

- Decisión relevante 1.
- Decisión relevante 2.

## 5. Observaciones

- Observación adicional (o "Ninguna").
```

## Notas

- La sección **2** solo declara qué Elementos de Diseño (ED-xx) se
  implementaron; no describe cómo. Cada ED declarado aquí debe existir
  previamente en la matriz de Diseño heredada — si no existe, el Issue
  se rechaza en `core/coding_contract.py` antes de llegar a cualquier
  agente.
- La sección **3** es la única fuente de rutas de archivo: solo se
  localizan y analizan (Radon/Semgrep/pip-audit/Gitleaks) los archivos
  aquí declarados, no el repositorio completo.
- Ninguna sección de esta plantilla calcula métricas ni evalúa calidad o
  seguridad: eso ocurre después, con evidencia real de las herramientas.
