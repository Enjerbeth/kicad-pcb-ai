# Tareas Middleware AERO (Hardware-as-Code)

- [/] Crear el script de indexación en frío (`sync_kicad_libs.py`)
  - [x] Definir esquema de la base de datos SQLite (`kicad_cache.db`).
  - [x] Lógica para parsear librerías de símbolos de KiCad 8 (`.kicad_sym`).
  - [x] Lógica para extraer footprint data (Courtyard/Keepout) de KiCad 8.
- [x] Construir la clase principal del `Shadow Interrogator` (`shadow_interrogator.py`)
  - [x] Validaciones JSON contra esquema.
  - [x] Consultas rápidas a SQLite para verificación semántica (Zero-RAM).
  - [x] Generación de `context` para el feedback loop.
- [x] Orquestación final (`aero_synthesizer.py`)
  - [x] Instanciación SKiDL e inyección de `PWR_FLAG`.
  - [x] Posicionamiento y reglas en `pcbnew`.
  - [x] Invocación a Freerouting y re-importación.
