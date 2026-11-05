# TraceDev — Modelo Multiagente

Herramienta web (Streamlit) que evalúa la **calidad**, la **seguridad** y la
**trazabilidad** de los artefactos de un proyecto de software registrados en
GitLab, a lo largo de cuatro etapas: **Requerimientos**, **Diseño**,
**Codificación** y **Pruebas**. Incluye además un **Panel del proyecto**
(solo lectura) con avance, indicadores, trazabilidad y versiones de matrices.

Cada etapa se orquesta con LangGraph mediante cuatro agentes:

| Agente | Función | Proveedor LLM |
|---|---|---|
| Central | Prepara y consolida el análisis | NVIDIA NIM |
| Calidad | Evalúa métricas de calidad | Groq |
| Seguridad | Evalúa métricas de seguridad | Groq |
| Evaluador | Emite el dictamen final | NVIDIA NIM |

En la etapa de Codificación, además, se ejecutan herramientas de análisis
estático sobre el código del repositorio GitLab: Radon, ESLint, Semgrep,
pip-audit, npm audit y Gitleaks.

---

## 1. Requisitos previos

### Software

| Componente | Versión | Uso |
|---|---|---|
| Python | 3.11 o superior (probado con 3.12 y 3.14) | Aplicación |
| Node.js + npm | 18 o superior (probado con 22) | ESLint y npm audit (Codificación) |
| Gitleaks | 8.x, en el `PATH` | Detección de secretos (Codificación) |
| Git | cualquiera | Clonar este repositorio |

Gitleaks no se instala con `pip`/`npm`: descargar el binario desde
<https://github.com/gitleaks/gitleaks/releases> y agregar su carpeta al `PATH`.
Comprobar con `gitleaks version`.

### Cuentas y credenciales

1. **GitLab**: token de acceso personal o de proyecto con alcance `api` sobre
   el proyecto a evaluar.
2. **NVIDIA NIM**: API key en <https://build.nvidia.com>.
3. **Groq**: API key en <https://console.groq.com>.
4. **Microsoft Entra ID (Microsoft 365)**: registro de aplicación para el
   inicio de sesión institucional (ver paso 4 de la instalación).

---

## 2. Instalación

```bash
git clone https://github.com/acuarionat/modelo-multiagente-dev.git
cd modelo-multiagente-dev
```

### 2.1 Entorno de Python

```bash
python -m venv .venv
```

Activar el entorno:

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- Linux / macOS: `source .venv/bin/activate`

Instalar dependencias:

```bash
pip install -r requirements.txt
```

### 2.2 Dependencias de Node.js (ESLint)

Desde la raíz del proyecto (instala las versiones fijadas en
`package-lock.json` dentro de `node_modules/`):

```bash
npm ci
```

### 2.3 Variables de entorno

Copiar la plantilla y completar las claves marcadas como OBLIGATORIO
(`NVIDIA_API_KEY`, `GROQ_API_KEY` y, opcionalmente, los valores de GitLab):

```bash
cp .env.example .env
```

En Windows: `copy .env.example .env`. Cada variable está documentada dentro
de `.env.example`.

### 2.4 Inicio de sesión con Microsoft 365

La aplicación exige iniciar sesión con una cuenta institucional
(`st.login()` de Streamlit sobre OpenID Connect).

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Luego, en Azure Portal → **Microsoft Entra ID → Registros de aplicaciones**:

1. Crear un registro con *"Solo cuentas en este directorio organizativo"*.
2. URI de redirección (tipo Web): `http://localhost:8501/oauth2callback`
   (si se publica en un servidor, agregar también
   `https://SU-DOMINIO/oauth2callback` y usar ese valor en `redirect_uri`).
3. Copiar el *Id. de aplicación (cliente)* en `client_id` y el
   *Id. de directorio (inquilino)* en `server_metadata_url`.
4. Crear un secreto de cliente y copiar su **valor** en `client_secret`.
5. Generar `cookie_secret`:
   `python -c "import secrets; print(secrets.token_hex(32))"`

Las instrucciones detalladas están en `.streamlit/secrets.toml.example`.

---

## 3. Ejecución

```bash
streamlit run app.py
```

Abrir <http://localhost:8501>, iniciar sesión con Microsoft 365 y, la primera
vez, completar **Configuración del proyecto** (barra lateral): nombre, URL de
GitLab, ID o ruta del proyecto y token. Después se puede trabajar en cada
etapa desde la navegación superior.

---

## 4. Persistencia

- **Por defecto (SQLite):** la base `database/database.db` se crea
  automáticamente en el primer arranque. Guarda el historial de análisis,
  la configuración del proyecto (incluido el token de GitLab) y las versiones
  de matrices. **No debe subirse al repositorio** (está en `.gitignore`).
- **PostgreSQL (opcional):** definir `DATABASE_URL` en `.env`. Para copiar
  los datos de un SQLite existente:

  ```bash
  python scripts/migrar_sqlite_a_postgres.py
  ```

Las carpetas `logs/` y `output/xlsx/` (matrices exportadas) también se
generan en tiempo de ejecución.

---

## 5. Estructura del proyecto

```
app.py                 Punto de entrada Streamlit (login, navegación, etapas)
project_config.py      Configuración del proyecto (GitLab) y su versionado
agents/                Agentes Central, Calidad, Seguridad y Evaluador por etapa
prompts/               Prompts de cada agente
core/                  Grafo LangGraph, fábrica de LLM, interfaces por etapa,
                       métricas, trazabilidad, exportación y panel
core/code_analysis/    Integración con Radon, ESLint, Semgrep, pip-audit,
                       npm audit y Gitleaks
integrations/          Cliente GitLab, lectura/escritura de Issues y matrices
database/              Conexión SQLite/PostgreSQL y repositorio de datos
scripts/               Migración SQLite → PostgreSQL
assets/                Logos e imágenes de la interfaz
.streamlit/            Tema visual y plantilla de secretos
package.json           Versiones de ESLint usadas en Codificación
```

---

## 6. Solución de problemas

| Síntoma | Causa probable |
|---|---|
| `NVIDIA_API_KEY no está configurada` | Falta la clave en `.env` |
| Error de autenticación al iniciar sesión | `.streamlit/secrets.toml` incompleto o URI de redirección distinta a la registrada en Entra ID |
| Herramienta `gitleaks`/`eslint` en estado de error | Gitleaks no está en el `PATH` o no se ejecutó `npm ci` |
| `401 Unauthorized` de GitLab | Token vencido, revocado o sin alcance `api` |
| Respuestas lentas o *timeout* | Límites del plan gratuito de NVIDIA/Groq; ajustar los tiempos en `.env` |
