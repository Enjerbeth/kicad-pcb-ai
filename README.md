# AERO Framework: Zero-Geometry Hardware-as-Code (V1.0)

AERO Framework es un ecosistema de compilación y orquestación diseñado para cerrar la brecha entre los Modelos de Lenguaje Grandes (LLMs) y la manufactura electrónica física (EDA). 

El sistema retira toda la carga de cálculo espacial y geométrico de la Inteligencia Artificial, delegándola a un motor determinista en Python que orquesta **KiCad 8**, **SKiDL** y **Freerouting** mediante un contrato JSON estricto.

## 🏗️ Arquitectura del Sistema

El flujo de trabajo implementa un lazo de control cerrado (Closed-Loop) de tres niveles para garantizar que cualquier alucinación del LLM sea capturada, tipada y devuelta como un error accionable.

```mermaid
graph TD
    %% Entidades Externas
    LLM[Agente LLM / Frontend Cognitivo]
    User((Usuario))

    %% Artefactos de Interfaz
    JSON_IN[Topología JSON v3.2]
    JSON_OUT[aero_feedback.json]
    PCB_OUT[aero_board.kicad_pcb]

    %% Middleware (AERO Backend)
    subgraph AERO Backend [Orquestador Central - aero_orchestrator.py]
        direction TB
        SI[Nivel 1: Shadow Interrogator\nValidación Semántica]
        SK[Nivel 2: Sintetizador SKiDL\nCompilación Lógica y ERC]
        PC[Nivel 3: Macro pcbnew\nTopología y Colisiones]
        FR[Nivel 4: Freerouting\nAuto-ruteo Asíncrono DRC]
    end

    %% Base de Datos
    DB[(kicad_cache.db\nCold Indexing)]
    Crawler[sync_kicad_libs.py]

    %% Relaciones
    User -->|Prompt Natural| LLM
    LLM -->|Genera| JSON_IN
    JSON_IN --> AERO Backend

    SI <-->|Consulta librerías/pines| DB
    Crawler -->|Popula (Offline)| DB

    SI -->|Si Falla| JSON_OUT
    SI -->|Si Pasa| SK
    
    SK -->|Si Falla ERC| JSON_OUT
    SK -->|Genera .net| PC
    
    PC -->|Si Colisiona| JSON_OUT
    PC -->|Exporta .dsn| FR
    
    FR -->|Falla DRC| JSON_OUT
    FR -->|Importa .ses| PCB_OUT

    JSON_OUT -.->|Inyecta contexto| LLM

```

## ⚙️ Prerrequisitos y Dependencias

El entorno de ejecución debe contar con:

* Python 3.10+ (Entorno estándar)
* **KiCad 8.0** (Debe estar en el PATH del sistema)
* **Java JRE/JDK 17+** (Para la ejecución de Freerouting)
* Paquetes Python: `pip install skidl jsonschema`
* Binario de [Freerouting](https://github.com/freerouting/freerouting) (`freerouting.jar`)

### Variables de Entorno Requeridas

Configura las siguientes variables de entorno para que el framework sea agnóstico al sistema operativo:

* `KICAD_SYMBOL_DIR`: Ruta a los símbolos de KiCad (Ej. `C:\Program Files\KiCad\8.0\share\kicad\symbols`)
* `KICAD_FOOTPRINT_DIR`: Ruta a las huellas de KiCad (Ej. `C:\Program Files\KiCad\8.0\share\kicad\footprints`)
* `KICAD_PYTHON_EXE`: Intérprete Python embebido de KiCad (Ej. `C:\Program Files\KiCad\8.0\bin\python.exe`)
* `FREEROUTING_JAR`: Ruta absoluta al ejecutable de Freerouting.

## 🚀 Guía de Despliegue

### 1. Indexación en Frío (Cold Indexing)

Para cumplir con la premisa *Zero-RAM*, el framework requiere una base de datos local SQLite con los metadatos de las librerías físicas de KiCad 8.
Se debe ejecutar una única vez (o tras instalar nuevas librerías):

```bash
python sync_kicad_libs.py

```

*Output esperado: `kicad_cache.db` generado en el directorio raíz.*

### 2. Ejecución del Orquestador

El agente LLM (o el usuario) debe generar un archivo JSON cumpliendo el **Prompt V3.2**. Para inyectar este archivo en el pipeline:

```bash
python aero_orchestrator.py <ruta_del_json.json> [retry_number]

```

### 3. El Bucle de Retroalimentación (Feedback Loop)

El orquestador **nunca** emite un *Stack Trace* crudo. Si el diseño falla en cualquier nivel (pines inexistentes, redes flotantes, colisiones físicas), el proceso se aborta y se genera un archivo `aero_feedback.json` con la siguiente estructura:

```json
{
  "feedback_status": "ERC_FAILED",
  "retry_number": 1,
  "max_retries": 3,
  "errors": [
    {
      "code": "UNIT_MISMATCH",
      "severity": "error",
      "description": "El componente U1 (74HC00) es multi-puerta y requiere el campo 'unit'.",
      "instruction": "Agrega 'unit' a la conexión.",
      "context": {
        "valid_units": ["A", "B", "C", "D"]
      }
    }
  ]
}

```

*Este archivo debe ser interceptado por el Frontend Cognitivo y devuelto al contexto del LLM para forzar una auto-corrección determinista.*

## 🧩 Componentes del Core

* `shadow_interrogator.py`: Validador sintáctico (JSON Schema) y semántico (cruce contra SQLite).
* `aero_synthesizer.py`: Traductor a la API de SKiDL y enlazador asíncrono.
* `aero_pcb_macro.py`: Macro inyectada en el Python de KiCad. Opera la matemática espacial (Espiral de Bounding Boxes) y bloquea pares diferenciales.
* `aero_orchestrator.py`: Wrapper principal y gestor de estados de excepción.
