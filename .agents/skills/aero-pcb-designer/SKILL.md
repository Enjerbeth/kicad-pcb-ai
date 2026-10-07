---
name: aero-pcb-designer
description: >
  Use when the user asks to design a circuit board, generate schematic topologies,
  validate electronics, or run the AERO Zero-Geometry PCB pipeline.
  Responds to requests like "diseña una PCB", "genera la topología", "crea la placa",
  "valida el circuito", "corre el orquestador KiCad", "diseña el esquemático".
  Always respond in Spanish. Specialist in Zero-Geometry Hardware-as-Code & KiCad 8.
---

# ⚡ SKILL: AERO PCB DESIGNER (Zero-Geometry Hardware-as-Code)

## Regla Canónica Zero-Geometry (Inviolable)
La IA NUNCA calcula coordenadas espaciales X/Y, anchos de pista ni polígonos de cobre. La IA diseña EXCLUSIVAMENTE la topología lógica de interconexión en formato AERO JSON v3.2. Toda geometría es delegada al backend determinista Python + KiCad 8 + Freerouting.

---

## 🛠️ Pipeline de Ejecución en 4 Niveles

1. **Nivel 1 — Shadow Interrogator (`shadow_interrogator.py`):**
   - Validación sintáctica JSON Schema y verificación semántica contra `kicad_cache.db` (SQLite).
   - Comprueba existencia real de componentes, pines y footprints ANTES de sintetizar.

2. **Nivel 2 — SKiDL Synthesizer (`aero_synthesizer.py`):**
   - Traduce JSON a código SKiDL, ejecuta el chequeo eléctrico (ERC) y genera el netlist `.net`.

3. **Nivel 3 — PCB Macro (`aero_pcb_macro.py`):**
   - Macro ejecutada en Python embebido de KiCad 8 (`pcbnew`).
   - Resuelve el placement determinista y exporta `.dsn` para Freerouting.

4. **Nivel 4 — Freerouting (`freerouting.jar`):**
   - Auto-ruteo asíncrono con DRC y retroalimentación `.ses` a KiCad para producir `aero_board.kicad_pcb`.

---

## 🔄 Closed-Loop Feedback (`aero_feedback.json`)
Si el orquestador falla en cualquier nivel:
1. Leer obligatoriamente `aero_feedback.json` completo.
2. Identificar el código de error (`UNIT_MISMATCH`, `PIN_NOT_FOUND`, `LIBRARY_NOT_FOUND`, `ERC_FAILED`, etc.).
3. Corregir la topología JSON de forma determinista y re-ejecutar:
   `python aero_orchestrator.py <archivo>.json`
