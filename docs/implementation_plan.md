# Plan de Arquitectura del Middleware (AERO Framework)

Este documento detalla la estructura propuesta para el Middleware en Python, encargado de recibir el JSON generado por el Agente de Diseño Electrónico, validarlo contra una base de datos local SQLite (Zero-RAM Footprint) e interactuar con KiCad 8 (SKiDL y pcbnew) y Freerouting.

## 1. El Problema de la Memoria
Llamar a `pcbnew.GetLibraries()` y parsear todos los `.kicad_sym` y `.pretty` cada vez que el agente corre destruirá la RAM y tomará varios segundos o minutos.
La solución es la **Indexación en Frío (Cold Indexing) con SQLite**.

## 2. Fase 1: El Crawler (sync_kicad_libs.py) — *PUNTO DE INICIO RECOMENDADO*

Un script independiente que el usuario corre esporádicamente para generar la base de datos `kicad_cache.db`.

### 2.1. Funciones del Crawler
1. Lee las variables de entorno de KiCad (`KICAD_SYMBOL_DIR`, `KICAD_FOOTPRINT_DIR`).
2. Recorre recursivamente todas las librerías oficiales y de terceros instaladas usando la API de pcbnew y parseo de SKiDL/S-expressions.
3. Extrae metadatos topológicos y físicos.

### 2.2. Esquema de SQLite (Zero-RAM) propuesto
- **Tabla `components`:**
  - `id` (PK), `library`, `symbol`, `total_pins`, `total_units`
- **Tabla `pins`:**
  - `id` (PK), `component_id` (FK), `pin_number`, `pin_name`, `electrical_type`
- **Tabla `footprints`:**
  - `id` (PK), `library`, `footprint`, `has_courtyard`, `courtyard_area_mm2`

## 3. Fase 2: Shadow Interrogator (shadow_interrogator.py)

El núcleo del Middleware que ejecuta comprobaciones cuando llega el JSON.

**Paso 1: Validación Sintáctica**
- El JSON se lee y valida contra el esquema.

**Paso 2: Validación Semántica en SQLite**
- Verificación ultra-rápida (SELECTs) de la existencia de `library:symbol`, validación de `pin_map` contra la tabla de `pins`, y chequeo de `unit` lógicos a enteros.

**Paso 3: Feedback Loop al LLM**
- En caso de error, detiene la ejecución, genera el objeto `context` (pines/unidades válidas) y retorna el JSON al agente.

## 4. Fase 3: Síntesis y Motores EDA

Si el JSON pasa las validaciones sin errores, el Middleware inicia la orquestación física:

1. **Compilación y ERC (SKiDL):**
   - Instancia los `Part` y `PartUnit`.
   - **[CRÍTICO] Redes de Poder:** Detecta las redes con `net_class: "power"`. Para evitar errores de red flotante (undriven) en el ERC de SKiDL, inyecta silenciosamente `.drive()` o instancia un `Part('power', 'PWR_FLAG')` en dichas redes.
   - Genera el netlist.
2. **Posicionamiento y Colisiones (pcbnew):**
   - Agrupa componentes por `layout_strategies`.
   - Utiliza polígonos **F_Courtyard** para detección de colisiones.
   - Aplica `collision_fallback` (desplazando todo el clúster) si la huella choca con otra o sale del `board_outline`.
3. **Pre-ruteo Diferencial (pcbnew):**
   - Si existen `differential_pairs`, se rutean manualmente con pistas simétricas y se bloquean (Lock).
4. **Auto-ruteo (Freerouting):**
   - Exporta a Specctra DSN excluyendo los pares diferenciales. Corre Freerouting y re-importa el SES.
5. **Planos de Cobre (pcbnew):**
   - Rellena las redes declaradas en `copper_pours` (ej. GND) creando zonas (Rule Areas) en la placa.

## Siguiente Acción Requerida
Proponer y programar el esqueleto del **Crawler (`sync_kicad_libs.py`)** junto con las sentencias DDL para crear la base de datos SQLite.
