# INFORME ARQUITECTÓNICO Y BENCHMARK EXHAUSTIVO
## Tooling, Servidores MCP y Automatización de IA para KiCad vs. Framework AERO v3.2

**Fecha:** 7 de Octubre de 2026  
**Autor:** Arquitecto de Software y Tooling EaC (Electronics-as-Code) de AERO  
**Licencia:** Apache-2.0 — Copyright (c) 2026 Rengil Multiservicios C.A. / Enjerbeth  
**Destinatario:** Orquestador Maestro / Agente Principal AERO

---

## 1. RESUMEN EJECUTIVO Y ESTADO DEL ARTE (EaC)

El diseño electrónico asistido por Inteligencia Artificial (AI-driven EDA / Electronics-as-Code) se encuentra en una encrucijada crítica entre dos paradigmas diametralmente opuestos:

1. **El Paradigma Visual/Imperativo (Alucinación Espacial):** Herramientas que intentan hacer que el LLM opere como un usuario humano manipulando la GUI de KiCad, colocando pistas con coordenadas X/Y en milímetros, o interactuando mediante navegadores web y plugins interactivos. Este enfoque sufre invariablemente de errores de solapamiento, violaciones de clearance, desbordamiento del context window e impredecibilidad catastrófica.
2. **El Paradigma Topológico/Declarativo (Zero-Geometry):** El estándar de oro implementado por **AERO**, donde el LLM es restringido exclusivamente a su mayor fortaleza: el razonamiento lógico, la selección de partes y la definición de la red de interconexión (netlist), delegando el 100% del cálculo espacial, el placement y el auto-enrutamiento a motores matemáticos deterministas (`pcbnew` + algoritmos de colisión + Freerouting).

A continuación se presenta la auditoría técnica profunda y matriz exhaustiva de las 7 herramientas y repositorios clave del ecosistema KiCad/EaC:
1. `rjwalters/kicad-tools`
2. `Seeed-Studio/ai-skills` (`schematic-analyzer`)
3. `paul356/KiCad-AI-Assistant`
4. `nickkraakman/skidl-skills`
5. `colaco1123/K-AI`
6. `atopile/atopile`
7. `devbisme/skidl`

---

## 2. ANÁLISIS INDIVIDUAL Y MATRIZ EXHAUSTIVA DE 4 CUADRANTES

```
+--------------------------------------------------------------------------+
|                            MATRIZ OPERATIVA AERO                         |
+------------------------------------+-------------------------------------+
| 🟢 QUÉ COPIAR                      | 🛠️ QUÉ IMPLEMENTAR                  |
| (Arquitectura de datos, formatos)  | (Nuevas capacidades para AERO v3.2) |
+------------------------------------+-------------------------------------+
| 🔴 QUÉ ELIMINAR                    | 🔄 QUÉ CAMBIAR                      |
| (Fragilidad, GUI, alucinaciones X/Y)| (Ajustes para Zero-Geometry 100%)  |
+------------------------------------+-------------------------------------+
```

---

### HERRAMIENTA 1: `rjwalters/kicad-tools`
**Stack:** Python, S-Expressions Parser, `kicad-cli`, `shapely`, C++/Rust Router backend, MCP Server.  
**Propósito:** CLI (`kct`) y servidor MCP para parsing, inspección y manipulación headless de archivos KiCad sin interfaz gráfica.

* 🟢 **QUÉ COPIAR (Arquitectura de datos y parseo):**
  - **Parser nativo de S-Expressions:** Habilidad de leer y emitir árboles S-expression (`.kicad_sch` y `.kicad_pcb`) de forma standalone sin invocar `pcbnew` ni levantar el entorno C++ de KiCad para tareas de solo lectura.
  - **Extracción de esquemas a JSON:** Representación formal estructurada de símbolos, pines, redes y BOM en JSON plano.
  - **Integración con `kicad-cli`:** Invocación limpia y sin cabeza (`kicad-cli pcb drc --format json` / `kicad-cli sch erc`) para auditorías oficiales del motor de KiCad.
  - **Geometría computacional con `shapely`:** Uso de polígonos 2D para calcular intersecciones complejas, distancias euclidianas y vaciado de planos de masa (copper clearances).

* 🛠️ **QUÉ IMPLEMENTAR (Integración en AERO v3.2):**
  - **Auditoría DRC Post-Enrutamiento con `kicad-cli`:** Integrar en el Nivel 4 de AERO una llamada de verificación DRC oficial con `kicad-cli` una vez que Freerouting importa el archivo `.ses` de vuelta a KiCad. Si existen violaciones DRC de KiCad, alimentar automáticamente `aero_feedback.json`.
  - **Ingeniería Inversa / Ingesta de Proyectos Existentes:** Incorporar el parser de `kicad-tools` para que AERO pueda leer placas `.kicad_pcb` o `.kicad_sch` creadas por humanos y convertirlas a contratos AERO JSON v3.2.

* 🔴 **QUÉ ELIMINAR (Antipatrones detectados):**
  - **LLM Routing Loops:** El repositorio experimenta permitiendo que el LLM intente rutar pistas o resolver colisiones espaciales mediante sugerencias iterativas de coordenadas. Esto viola frontalmente el principio Zero-Geometry de AERO.
  - **Compilación C++/Rust compleja:** Obligar al usuario a ejecutar `uv run kct build-native` con toolchains nativos C++ agrega puntos de fallo en entornos de despliegue ligeros.

* 🔄 **QUÉ CAMBIAR (Ajuste a Zero-Geometry):**
  - **Confinar `shapely` al Nivel 3:** `shapely` jamás debe ser expuesto al LLM como una herramienta de toma de decisiones geométricas. Debe residir exclusivamente dentro de `aero_pcb_macro.py` como un acelerador vectorial de colisiones AABB y polígonos no rectangulares para el placement automático.

---

### HERRAMIENTA 2: `Seeed-Studio/ai-skills` (`schematic-analyzer`)
**Stack:** Python, KiCad CLI, OrCAD Parser, JSON Summarizer, MCP Integration.  
**Propósito:** Skill para LLMs especializada en extraer y analizar esquemáticos KiCad/Cadence evitando la saturación del context window.

* 🟢 **QUÉ COPIAR (Arquitectura de datos y parseo):**
  - **Particionamiento por Subsistemas Funcionales:** Algoritmo de clustering que agrupa componentes en dominios de alto nivel (Power Management, MCU/Processing, Communication Buses, Analog Frontend).
  - **Detección Automática de Buses de Señal:** Detección basada en patrones para interfaces estándar (I2C: SDA/SCL; SPI: MOSI/MISO/SCK/CS; UART: TX/RX; USB: D+/D-).
  - **Token Budget Optimization:** Compresión extrema de esquemáticos masivos en resúmenes JSON concisos, evitando que un diseño de 50 hojas consuma cientos de miles de tokens de contexto.

* 🛠️ **QUÉ IMPLEMENTAR (Integración en AERO v3.2):**
  - **Auditoría de Guardrails Electrónicos Mejorada en Nivel 1:** Utilizar la lógica de detección de buses de Seeed en `shadow_interrogator.py`. Si el LLM diseña un bus I2C sin resistencias pull-up a VCC, o cruza una señal de 5V hacia un pin MCU de 3.3V, el analizador detecta el bus y rechaza la síntesis antes de invocar SKiDL.
  - **Atributo `circuit_group` obligatorio y enriquecido:** Forzar a que cada componente en AERO JSON v3.2 pertenezca a un subsistema validado.

* 🔴 **QUÉ ELIMINAR (Antipatrones detectados):**
  - **Cadena de dependencias externa pesada:** Dependencia obligatoria de la skill `pdf`, `ee-datasheet-master`, `pcbparts` MCP y almacenamiento local masivo de PDFs.
  - **Formatos propietarios legados:** Soporte para Cadence OrCAD/Allegro (`pstxnet.dat`), que introduce complejidad innecesaria para un pipeline enfocado en KiCad 8/9 open-source.

* 🔄 **QUÉ CAMBIAR (Ajuste a Zero-Geometry):**
  - **De Análisis Pasivo a Guía de Placement Físico:** En Seeed, los subsistemas son solo texto informativo para el LLM. En AERO, el `circuit_group` extraído debe transferirse directamente a `aero_pcb_macro.py` para aplicar clustering espacial de centro de gravedad (los componentes de un mismo grupo se colocan cerca entre sí automáticamente).

---

### HERRAMIENTA 3: `paul356/KiCad-AI-Assistant`
**Stack:** Python, KiCad 10 Action Plugin (WxWidgets), MCP Server (115+ herramientas), Dynamic Tool Loading (`uv`).  
**Propósito:** Asistente conversacional embebido directamente en la GUI de KiCad mediante panel lateral y herramientas de edición interactiva.

* 🟢 **QUÉ COPIAR (Arquitectura de datos y parseo):**
  - **Dynamic / On-Demand MCP Tool Loading:** Patrón arquitectónico donde el servidor MCP no satura la ventana de contexto enviando más de 100 esquemas de herramientas en cada turno. En su lugar, expone meta-herramientas (`enable_tool`, `disable_tool`, `get_tool_schema`) cargando solo lo estrictamente necesario.
  - **Inspección de Propiedades Físicas:** Herramientas de consulta profunda de las capas de cobre, stackups, netclasses y reglas de DRC existentes en el archivo nativo de KiCad.

* 🛠️ **QUÉ IMPLEMENTAR (Integración en AERO v3.2):**
  - **Servidor MCP Nativo de AERO (`aero-mcp`):** Diseñar un servidor MCP para AERO que implemente carga bajo demanda de herramientas de consulta semántica de librerías (`query_symbol_cache`, `query_footprint_pins`, `validate_topology_json`).
  - **Inyección de Net Classes en PCB:** Tomar la lógica de manipulación de Net Classes de KiCad para que `aero_synthesizer.py` y `aero_pcb_macro.py` asignen anchos de pista específicos a redes de potencia y RF automáticamente.

* 🔴 **QUÉ ELIMINAR (Antipatrones detectados):**
  - **EL MAYOR ANTIPATRÓN: Manipulación Espacial Imperativa por el LLM:** El asistente permite al LLM ejecutar `move_footprint(x, y)`, `rotate`, `flip`, `align` y trazar cables con coordenadas. Los LLMs carecen de razonamiento espacial 2D continuo; esto provoca solapamientos absurdos y destrucción de la integridad del diseño.
  - **Acoplamiento a la GUI y WxWidgets:** Requiere tener KiCad abierto con interfaz gráfica en pantalla. Esto rompe la integración en servidores headless, GitHub Actions CI/CD y pipelines automatizados.
  - **Dependencia de KiCad 10 (Bleeding Edge):** Diseñado para una versión no estable o preliminar, perdiendo compatibilidad con la versión LTS actual (KiCad 8.0).

* 🔄 **QUÉ CAMBIAR (Ajuste a Zero-Geometry):**
  - **Inversión de Control de Coordenadas:** Sustituir todas las herramientas MCP del tipo `move(x, y)` por directivas topológicas de alto nivel (`cluster_with: "U1"`, `shield_net: "RF_IN"`). El LLM nunca debe ver ni emitir números en milímetros de posición.

---

### HERRAMIENTA 4: `nickkraakman/skidl-skills`
**Stack:** Claude Code CLI, Python, SKiDL, `netlistsvg`, Node.js.  
**Propósito:** Flujo multi-agente para Claude Code que divide el diseño de circuitos en fases especializadas desde la especificación hasta el netlist verificado con ERC.

* 🟢 **QUÉ COPIAR (Arquitectura de datos y parseo):**
  - **Especialización de Agentes en Cadena de Suministro Lógica:**
    1. *Requirements Interviewer*: Convierte requerimientos difusos en un `SPEC.md` estructurado y sin ambigüedades.
    2. *Circuit Architect*: Traduce `SPEC.md` en diagrama de bloques y lista preliminar de componentes (BOM).
    3. *Coder/Synthesizer*: Genera la topología formal.
    4. *ERC Reviewer*: Audita exhaustivamente el log de reglas eléctricas y genera un reporte estructurado de fallos.
  - **Renderizado Visual Determinista con `netlistsvg`:** Compila el netlist a un gráfico vectorial SVG limpio y legible automáticamente, sin necesidad de abrir KiCad Eeschema.

* 🛠️ **QUÉ IMPLEMENTAR (Integración en AERO v3.2):**
  - **Pipeline Visual SVG Post-Nivel 2:** Incorporar la exportación automática a SVG mediante `netlistsvg` al finalizar la síntesis de SKiDL. Esto permite al usuario (y a agentes multimodales) auditar visualmente el circuito lógico antes de pasar a la fase de placement físico.
  - **Agente Auditor ERC Dedicado:** Integrar un parser especializado del log de ERC de SKiDL que traduzca mensajes crudos de advertencia en objetos JSON accionables para `aero_feedback.json`.

* 🔴 **QUÉ ELIMINAR (Antipatrones detectados):**
  - **Generación de Código Python Crudo por el LLM:** En el flujo de Kraakman, el LLM escribe scripts `.py` de SKiDL ejecutables directamente. Esto produce frecuentes `SyntaxError`, `NameError`, fallos de importación y riesgos de seguridad.
  - **Incompletitud del Pipeline ("80% of the way"):** El proyecto se detiene tras generar el netlist. Deja el 20% más difícil (placement de footprints, resolución de colisiones y ruteo de pistas) a la intervención manual humana en KiCad GUI.

* 🔄 **QUÉ CAMBIAR (Ajuste a Zero-Geometry):**
  - **El LLM solo escribe AERO JSON v3.2:** Reemplazar la escritura de scripts Python por la generación de datos puros JSON. El backend `aero_synthesizer.py` de AERO es quien genera el código SKiDL de manera 100% determinista e inmune a errores de sintaxis.
  - **Pipeline Completo al 100%:** AERO no se detiene en el netlist; completa el Nivel 3 (Placement físico algorítmico) y Nivel 4 (Freerouting DRC) para entregar el archivo `.kicad_pcb` completamente terminado.

---

### HERRAMIENTA 5: `colaco1123/K-AI`
**Stack:** Python, KiCad 9 Action Plugin, Chrome Automation (Selenium/Playwright style bridge hacia `claude.ai` web).  
**Propósito:** Plugin que permite pedir modificaciones esquemáticas en lenguaje natural a Claude utilizando una sesión web activa de Chrome en lugar de pagar API keys.

* 🟢 **QUÉ COPIAR (Arquitectura de datos y parseo):**
  - **Intención Conversacional en Lenguaje Natural:** Capacidad de entender comandos directos y coloquiales del usuario ("agrega un capacitor de desacoplo de 100nF al riel VCC de U1") y mapearlos a modificaciones de ingeniería.
  - **Concepto de Modificación Diferencial (Delta):** Reconocimiento de que la mayoría de los comandos de diseño son adiciones o modificaciones incrementales sobre un diseño existente, no regeneraciones completas.

* 🛠️ **QUÉ IMPLEMENTAR (Integración en AERO v3.2):**
  - **Mecanismo de Delta / Patch en AERO JSON:** Admitir un contrato `aero_diff.json` con operaciones atómicas (`add_component`, `remove_component`, `connect_net`, `disconnect_pin`), permitiendo modificar un diseño existente sin tener que reenviar ni reprocesar la topología completa.

* 🔴 **QUÉ ELIMINAR (Antipatrones críticos):**
  - **EL PEOR ANTIPATRÓN: Scraping y Automatización Web de `claude.ai`:**
    - Se rompe ante cualquier cambio mínimo en el DOM/HTML del frontend de Claude.
    - Viola los Términos de Servicio de Anthropic.
    - Sufre de caídas de sesión, re-autenticaciones de Cloudflare y latencias inmanejables.
    - Cero determinismo, sin trazabilidad ni compatibilidad con entornos headless.
  - **Ausencia de Validación Formal:** Modifica el esquemático sin un paso intermedio de validación semántica o verificación de reglas eléctricas.

* 🔄 **QUÉ CAMBIAR (Ajuste a Zero-Geometry):**
  - **Inferencia Exclusiva por API / Protocolos MCP:** Cualquier interacción con modelos debe ser estrictamente a través de APIs oficiales estructuradas (Anthropic API, Google Gemini, OpenAI, NVIDIA NIM) garantizando esquemas JSON tipados y disponibilidad 24/7.

---

### HERRAMIENTA 6: `atopile/atopile`
**Stack:** Compilador propio en Python, Gramática Tree-sitter / ANTLR, Lenguaje DSL `.ato`, Integración KiCad.  
**Propósito:** Framework líder de Electronics-as-Code orientado a objetos; permite escribir código declarativo modular con resolución paramétrica de restricciones.

* 🟢 **QUÉ COPIAR (Arquitectura de datos y parseo):**
  - **Concepto de Interfaces de Señal Reusables:** Abstracciones formales para interfaces eléctricas estándar (`interface I2C`, `interface SPI`, `interface Power`, `interface DifferentialPair`) que empaquetan múltiples señales en una sola entidad lógica.
  - **Resolución de Restricciones Paramétricas (Constraint Solving):** Capacidad de definir requerimientos numéricos ("V_out = 3.3V +/- 2%, I_load = 500mA") y dejar que el compilador calcule los componentes pasivos óptimos (resistencias E96, inductores).
  - **Encapsulación y Jerarquía Estricta:** Reusabilidad de submódulos de hardware como si fueran paquetes de software (ej. `from "regulators.ato" import BuckRegulator`).

* 🛠️ **QUÉ IMPLEMENTAR (Integración en AERO v3.2):**
  - **Biblioteca de Macros y Plantillas Modulares en AERO:** Crear un catálogo de macros pre-validadas en AERO JSON v3.2:
    - `macro_decoupling_pair`: inyecta automáticamente 100nF (0402/0603) + 10uF (0805) en los pines de alimentación de un IC.
    - `macro_i2c_bus`: conecta automáticamente resistencias pull-up de 4.7k a la red VCC correspondiente.
    - `macro_crystal_resonator`: añade el cristal y los dos capacitores de carga a GND.
  - **Solucionador de Componentes Pasivos en el Nivel 1:** Integrar en `shadow_interrogator.py` un calculador matemático para divisores de tensión, filtros RC y resistencias de pull-up según la serie E24/E96 estándar.

* 🔴 **QUÉ ELIMINAR (Antipatrones detectados):**
  - **Invención de un DSL Propietario (`.ato`):** Forzar a los ingenieros y a los LLMs a aprender un nuevo lenguaje de programación con su propia sintaxis y dependencias genera fricción de adopción masiva. Los LLMs ya son expertos universales en Python y JSON; un DSL propietario limita la compatibilidad agéntica y dificulta el debugging.
  - **Round-Trip Problem:** La sincronización bidireccional entre el código `.ato` y los cambios manuales en la PCB de KiCad genera conflictos de fusión y desincronización de la fuente única de verdad.

* 🔄 **QUÉ CAMBIAR (Ajuste a Zero-Geometry):**
  - **Expresar las Abstracciones en JSON Estándar + Python SKiDL:** En lugar de compilar un archivo `.ato`, AERO encapsula las interfaces y restricciones dentro de su esquema JSON v3.2 y su base de datos SQLite pre-indexada (`kicad_cache.db`), manteniendo el stack 100% nativo de Python y compatible con cualquier LLM.

---

### HERRAMIENTA 7: `devbisme/skidl`
**Stack:** Python puro, API de Netlists, Motor ERC interno, Mapeador de Símbolos KiCad.  
**Propósito:** La biblioteca pionera y canónica de Electronics-as-Code en Python. Reemplaza la captura esquemática por programación procedural que compila a netlists de KiCad.

* 🟢 **QUÉ COPIAR (Arquitectura de datos y parseo):**
  - **Álgebra de Interconexión Confiable:** Sintaxis de sobrecarga de operadores en Python (`net += part[pin]`, `part1[1] += part2[2]`) que proporciona una construcción de netlist robusta e infalible.
  - **Matriz de Compatibilidad ERC:** Sistema riguroso de reglas eléctricas basado en tipos de pines (Input, Output, Power Input, Power Output, Open Collector, Tri-State, etc.) que detecta cortocircuitos entre salidas o entradas flotantes.
  - **Manejo Nativo de Multi-Unit / Multi-Gate:** Soporte transparente para encapsulados con múltiples submódulos (ej. compuertas lógicas A, B, C, D o amplificadores operacionales duales/cuádruples).
  - **Indexación Directa de Símbolos KiCad:** Carga nativa de símbolos `.kicad_sym` de KiCad 6, 7, 8 y 9.

* 🛠️ **QUÉ IMPLEMENTAR (Integración en AERO v3.2):**
  - **Parser Estricto de Reportes `.erc` de SKiDL:** Actualmente `aero_synthesizer.py` captura excepciones generales. Debemos parsear formalmente el archivo `aero_orchestrator.erc` que emite SKiDL para extraer códigos de error granulares (`PIN_DRIVE_CONFLICT`, `POWER_PIN_UNDRIVEN`, `INPUT_UNCONNECTED`) y alimentar `aero_feedback.json`.
  - **Aprovechamiento de la Clase `Bus` de SKiDL:** Utilizar `skidl.Bus` para manejar de manera ultracompacta buses de datos de 8/16/32 bits y buses SPI/I2C en el sintetizador.

* 🔴 **QUÉ ELIMINAR (Antipatrones detectados):**
  - **Estado Global Compartido (`default_circuit`):** SKiDL almacena el circuito por defecto en un singleton global mutable. Si el pipeline falla o se re-ejecuta en el mismo proceso de Python, se produce contaminación de estado y componentes fantasma.
  - **Incapacidad Espacial y Física:** SKiDL es estrictamente un generador de netlists lógicos. No tiene noción de placement físico, colisiones de footprints ni enrutamiento de cobre. Dejar al usuario solo con SKiDL es dejar la PCB a mitad de camino.

* 🔄 **QUÉ CAMBIAR (Ajuste a Zero-Geometry):**
  - **Aislamiento e Idempotencia:** En `aero_synthesizer.py`, ejecutar obligatoriamente `default_circuit.reset()` al inicio de cada síntesis para garantizar que cada iteración del pipeline AERO sea completamente pura e idempotente.
  - **Fusión con los Niveles 3 y 4 de AERO:** Tratar a SKiDL como el motor de paso intermedio (Nivel 2) que alimenta al verdadero motor de resolución física de AERO (`aero_pcb_macro.py` + Freerouting).

---

## 3. MATRIZ COMPARATIVA CONSOLIDADA (TABLA RESUMEN)

| Dimensión Técnica | rjwalters/kicad-tools | Seeed schematic-analyzer | paul356 KiCad-AI-Assistant | nickkraakman skidl-skills | colaco1123 K-AI | atopile/atopile | devbisme/skidl | **AERO Framework v3.2 (Propuesto)** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Paradigma Geométrico** | Mixto (CLI + LLM router) | Agnóstico (solo lectura) | **Violación:** LLM manipula X/Y | Agnóstico (se detiene en netlist) | No aplica (GUI interactiva) | Resuelve restricciones lógicas | Agnóstico (solo netlist) | **100% Zero-Geometry Determinista** |
| **Entrada del LLM** | Comandos CLI / Herramientas MCP | Prompts de análisis | Chat conversacional en KiCad | Prompts a agentes Claude | Texto libre vía Chrome | Código `.ato` propietario | Código Python `.py` | **AERO JSON v3.2 Estricto** |
| **Validación Previa** | `kicad-cli` | Heurística por patrones | DRC interactivo en GUI | Agente ERC Reviewer | Ninguna | Compilador `.ato` | Verificación en tiempo de ejecución | **Shadow Interrogator + SQLite Cache** |
| **Motor de Síntesis** | S-Expressions directas | No sintetiza (analiza) | KiCad Python API directa | Scripts SKiDL generados | Manipulación DOM / KiCad | Compilador propio atopile | Python SKiDL nativo | **SKiDL Determinista + pcbnew Macro** |
| **Resolución de Placement**| Parcial / Experimental | No realiza placement | LLM posiciona manualmente | Manual humano en KiCad | Manual humano en KiCad | Agrupamiento por bloques | No realiza placement | **Algoritmo Espiral BBox + NumPy AABB** |
| **Enrutamiento** | C++/Rust router en pruebas| No enruta | Manual / Auto-router KiCad | Manual humano en KiCad | No enruta | Delega a KiCad | No enruta | **Freerouting Headless Asíncrono** |
| **Feedback Loop** | Text / JSON output | Respuestas en chat | Chat en tiempo real | Retroalimentación en Claude | No estructurado | Errores de compilación | Excepciones Python crudas | **Contrato JSON `aero_feedback.json`** |
| **Ejecución Headless / CI** | ✅ Excelente (CLI/MCP) | ✅ Bueno | ❌ Requiere KiCad 10 GUI | ⚠️ Depende de Claude Code | ❌ Requiere Chrome en pantalla | ✅ Excelente (CLI) | ✅ Excelente (Python) | **✅ 100% Headless y reproducible** |

---

## 4. CONCLUSIONES Y RECOMENDACIONES ARQUITECTÓNICAS PARA EL ORQUESTADOR AERO

Tras este análisis riguroso, se concluye que **el diseño arquitectónico de AERO v3.2 es conceptualmente superior** al de las iniciativas existentes porque resuelve la debilidad crítica de todas ellas: **elimina de raíz las alucinaciones espaciales delegando la física al backend y manteniendo un pipeline de 4 niveles cerrado y formal.**

Para elevar el framework AERO al estado del arte definitivo (hacia la versión **AERO v3.3 / v4.0**), se emiten las siguientes recomendaciones directas de implementación:

### Recomendación 1: Auditoría Dual (ERC SKiDL + DRC Headless con `kicad-cli`)
- **Origen de la idea:** `rjwalters/kicad-tools` y `nickkraakman/skidl-skills`.
- **Acción:**
  1. En el **Nivel 2**, parsear exhaustivamente el archivo `aero_orchestrator.erc` generado por SKiDL en lugar de depender únicamente de capturas de excepciones genéricas. Mapear cada violación de pin o red flotante a códigos tipados en `aero_feedback.json`.
  2. En el **Nivel 4**, tras importar el archivo `.ses` ruteado por Freerouting, invocar headless:
     ```bash
     kicad-cli pcb drc --format json --output aero_drc_report.json aero_board.kicad_pcb
     ```
     Si el informe contiene violaciones de clearance o pistas no conectadas, el orquestador captura el JSON oficial de KiCad y activa el bucle de feedback antes de entregar la placa al usuario.

### Recomendación 2: Ingesta de Macros Funcionales e Interfaces Declarativas
- **Origen de la idea:** `atopile/atopile` y `Seeed-Studio/ai-skills`.
- **Acción:**
  - Enriquecer el schema de AERO JSON v3.2 con soporte para `macros` e `interfaces`.
  - El LLM podrá declarar bloques de alta abstracción como:
    ```json
    {
      "macro": "decoupling_pair",
      "target_ic": "U1",
      "power_net": "+3V3",
      "gnd_net": "GND"
    }
    ```
  - `shadow_interrogator.py` y `aero_synthesizer.py` expandirán deterministamente esta macro a componentes físicos reales (C1: 100nF 0402, C2: 10uF 0805) y garantizarán que se ubiquen en el mismo `circuit_group` espacial para colocación contigua en el Nivel 3.

### Recomendación 3: Prevención de Contaminación de Estado en SKiDL
- **Origen de la idea:** `devbisme/skidl`.
- **Acción:**
  - En `aero_synthesizer.py`, antes de instanciar cualquier parte, ejecutar obligatoriamente:
    ```python
    from skidl import default_circuit
    default_circuit.reset()
    ```
  - Esto garantiza que en ciclos de reintento (`retry_number > 1`), el circuito previo se destruya por completo de la memoria RAM de Python, previniendo referencias cruzadas duplicadas o falsos positivos de ERC.

### Recomendación 4: Servidor MCP AERO de Carga Dinámica (On-Demand)
- **Origen de la idea:** `paul356/KiCad-AI-Assistant`.
- **Acción:**
  - Exponer un servidor MCP nativo para AERO (`aero_mcp_server.py`) que permita a agentes como Claude Code, Gemini o Cursor consultar la base de datos `kicad_cache.db` y validar topologías sobre la marcha.
  - Implementar el patrón de carga bajo demanda para evitar desbordar el context window del agente con herramientas superfluas.
  - **Regla inmutable:** Las herramientas MCP de AERO solo permitirán operaciones de **consulta semántica, validación de reglas y despacho de topología en JSON**; jamás herramientas de movimiento de coordenadas X/Y.

### Recomendación 5: Visualización de Esquemático en SVG sin GUI
- **Origen de la idea:** `nickkraakman/skidl-skills`.
- **Acción:**
  - Tras la finalización exitosa del Nivel 2 (SKiDL ERC OK), invocar headless `netlistsvg aero_project.net -o aero_schematic.svg`.
  - Esto genera un artefacto gráfico inmediato que el usuario puede visualizar en el navegador o en el IDE sin necesidad de abrir KiCad Eeschema.

---
*Fin del Informe Técnico de Arquitectura.*
