# Auditoría Crítica: Prompt v3.1 — Antigravity (Claude Opus 4.6)

> Basada en investigación técnica real de SKiDL, KiCad 8 pcbnew API y Freerouting.
> No hay cumplidos gratuitos aquí. Solo evidencia verificada.

---

## 🟢 Validaciones CONFIRMADAS con evidencia real

### 1. ✅ SKiDL ES compatible con KiCad 8
**Fuente:** [GitHub SKiDL](https://github.com/devbisme/skidl) + documentación ReadTheDocs

SKiDL soporta KiCad 5 a 9. Parsea archivos `.kicad_sym` nativos. El Middleware PUEDE instanciar `Part('Device', 'R', footprint='Resistor_SMD:R_0805_2012Metric')` y funciona.

**Dato crítico para el Middleware:** SKiDL necesita la variable de entorno `KICAD_SYMBOL_DIR` apuntando a los símbolos de KiCad 8. Sin esto, falla silenciosamente con "No libraries found".

### 2. ✅ `GetCourtyard()` EXISTE en KiCad 8 y es SUPERIOR a `GetBoundingBox()`
**Fuente:** [KiCad Doxygen Python API 8.0](https://docs.kicad.org/doxygen-python-8.0/)

```python
# API real confirmada:
courtyard = footprint.GetCourtyard(pcbnew.F_Courtyard)  # Retorna SHAPE_POLY_SET
bbox = footprint.GetBoundingBox()  # Retorna BOX2I
```

**Veredicto:** El análisis de tu auditor sobre usar Courtyard en lugar de BoundingBox es **CORRECTO y mandatorio**. El BoundingBox incluye silkscreen y texto, lo que lo hace más grande de lo necesario. El Courtyard es el estándar IPC para separación DFM.

### 3. ✅ Keepout zones embebidas en huellas de RF son reales
**Fuente:** [KiCad Library Conventions + Espressif Design Guidelines](https://www.espressif.com/en/support/documents/technical-documents)

Las huellas oficiales de KiCad para ESP32-WROOM-32E **YA incluyen** Rule Areas (keepout) embebidas. El Middleware NO necesita crearlas manualmente si usa las huellas oficiales. Solo necesita NO sobrescribirlas al posicionar.

### 4. ✅ `VECTOR2I` y `EDA_ANGLE` son la API correcta para KiCad 8
**Fuente:** KiCad Doxygen

```python
footprint.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(110.0), pcbnew.FromMM(100.0)))
footprint.SetOrientation(pcbnew.EDA_ANGLE(90.0, pcbnew.DEGREES_T))
```

**Unidades internas:** 1 IU = 1 nanómetro. Usar `pcbnew.FromMM()` y `pcbnew.ToMM()` para conversiones.

### 5. ✅ SKiDL soporta multi-unidad con `PartUnit`
**Fuente:** [SKiDL docs - ReadTheDocs](https://skidl.readthedocs.io/)

```python
u = Part("74xx", "74HC00")
gate_a = PartUnit(u, unit=1)  # Primera puerta NAND
gate_b = PartUnit(u, unit=2)  # Segunda puerta NAND
```

---

## 🔴 VULNERABILIDADES CRÍTICAS DETECTADAS

### Vulnerabilidad 1: SKiDL usa `unit=1,2,3,4` (enteros), NO `unit="A","B","C","D"` (letras)

> **Severidad: CRÍTICA** — Rompe el pipeline silenciosamente

**El problema en el prompt v3.1:**
El prompt instruye al LLM a usar `"unit": "A"` en las conexiones:
```json
{"ref": "U1", "pin": "3", "unit": "A"}
```

**La realidad en SKiDL:**
SKiDL usa `PartUnit(part, unit=1)`, no `unit="A"`. Las unidades son **enteros**, no letras. La API de SKiDL mapea internamente `unit=1` → puerta A, `unit=2` → puerta B, etc.

**Impacto:** Si el Middleware pasa `unit="A"` directamente a SKiDL, obtendrá un `TypeError` o un `IndexError`.

**Parche necesario:** El Middleware debe implementar un mapeo `{"A": 1, "B": 2, "C": 3, "D": 4}`. Pero el prompt TAMBIÉN debería documentar esto para que el LLM sepa qué convención usar. Hay dos opciones:

| Opción | En el Prompt | En el Middleware |
|--------|-------------|-----------------|
| A: Mantener letras | `"unit": "A"` (más legible para humanos) | Middleware traduce A→1, B→2 |
| B: Usar enteros | `"unit": 1` (alineado con SKiDL) | Middleware pasa directo |

**Mi recomendación:** Opción A. Las letras son más naturales para un LLM. Pero **documenta explícitamente** que las unidades son secuenciales (A=primera, B=segunda).

---

### Vulnerabilidad 2: Freerouting NO soporta pares diferenciales — CONFIRMADO

> **Severidad: CRÍTICA** — El prompt promete una capacidad que el pipeline no puede cumplir

**El problema en el prompt v3.1:**
```
▸ PARES DIFERENCIALES
  Declara los pares en "differential_pairs" dentro de design_rules.
  El Middleware configurará Freerouting para rutearlos con impedancia controlada.
```

**La realidad verificada:**
Según múltiples fuentes (GitHub Freerouting, foros de KiCad), Freerouting **NO tiene soporte nativo para pares diferenciales**. Trata cada red del par como independiente. No puede:
- Mantener gap constante entre trazas
- Controlar impedancia
- Hacer length matching
- Respetar skew

**Impacto:** Si el LLM declara `differential_pairs` y el Middleware se las pasa a Freerouting, las trazas USB/CAN quedarán con impedancia descontrolada → la placa no funcionará en alta velocidad.

**Parche necesario en el prompt:**
Cambiar la regla a:
> "El Middleware ruteará manualmente los pares diferenciales usando la API de pcbnew (PCB_TRACK simétricos) ANTES de invocar Freerouting. Las redes declaradas como differential_pairs serán EXCLUIDAS del archivo DSN para que Freerouting no las toque."

---

### Vulnerabilidad 3: `grid_origin` rompe Zero-Geometry — GLM 5.2 tiene razón

> **Severidad: MEDIA** — No rompe el pipeline pero es incoherente

**El problema:** El prompt prohíbe al LLM pensar en coordenadas absolutas (Regla 2), pero luego le pide que defina `grid_origin: {"x": 100.0, "y": 100.0}`.

**Contradicción:** ¿Por qué un LLM "Zero-Geometry" decide el origen de la grilla? El valor `(100, 100)` es una convención arbitraria de KiCad.

**Parche:** Eliminar `grid_origin` del schema del LLM. Hardcodearlo en el Middleware como `board_outline.width/2, board_outline.height/2` (centrar el diseño en la placa). Si no hay `board_outline`, usar `(100, 100)` por defecto.

---

### Vulnerabilidad 4: `keepout_zones` es una idea válida PERO innecesaria si usas huellas oficiales

> **Severidad: BAJA** — Buena idea, pero la solución ya existe

**La realidad:** Las huellas oficiales de KiCad para módulos RF (ESP32, nRF52, etc.) **YA contienen** Rule Areas embebidas que prohiben cobre/vías/tracks en la zona de antena. El Middleware solo necesita NO destruir estas zonas al posicionar.

**Veredicto:** No agregar `keepout_zones` al prompt. Sobrecargar al LLM con esto es innecesario. El Middleware debe respetar las Rule Areas existentes en las huellas. Si la huella no tiene keepout (componente genérico), el Middleware puede auto-generarlo basándose en el `part_def` consultando una tabla de reglas predefinida.

---

### Vulnerabilidad 5: `pin_map` con arrays rompe la gramática de `nets.connections`

> **Severidad: ALTA** — Ambigüedad en la resolución de conexiones

**El problema:** El prompt v3.1 permite:
```json
"pin_map": {"GND": ["1", "15", "38"]}
```

Pero en `nets.connections`:
```json
{"ref": "U2", "pin": "GND"}
```

**La ambigüedad:** ¿Qué pines conecta esto? ¿Los 3 pines GND del ESP32 van a la misma red? ¿O solo el primero?

**La realidad en SKiDL:** Cada pin se conecta individualmente a una Net. Si "GND" mapea a ["1", "15", "38"], el Middleware debe hacer:
```python
net_gnd += u2[1]
net_gnd += u2[15]
net_gnd += u2[38]
```

**Pero esto crea una carga cognitiva oculta:** El LLM escribe UNA conexión y el Middleware la expande a TRES. Si hay un error en la expansión, el feedback loop mostrará pines que el LLM nunca escribió explícitamente.

**Parche recomendado:** Documentar explícitamente en el prompt:
> "Si un alias en pin_map apunta a un array de pines físicos, UNA sola conexión en nets que use ese alias conectará TODOS los pines físicos del array a la misma red."

---

### Vulnerabilidad 6: Ausencia de `layer_count` — placa simple cara vs doble

> **Severidad: ALTA** — Afecta directamente a Freerouting

**El problema:** El prompt no define cuántas capas de cobre tiene la placa. Freerouting necesita saber si puede rutear en F.Cu + B.Cu (2 capas) o si tiene 4/6 capas disponibles.

**Impacto:** Si el diseño es denso y Freerouting solo tiene 2 capas, puede fallar el ruteo completo. El Middleware necesita este dato para generar el DSN correctamente.

**Parche:** Agregar campo opcional a `project_metadata`:
```json
"layer_count": 2  // Opcional. Default: 2. Valores válidos: 1, 2, 4, 6
```

---

## 🎯 Resumen de Parches para v3.2

| # | Parche | Severidad | Esfuerzo |
|---|--------|-----------|----------|
| 1 | Documentar que `unit` A/B/C/D se traduce a enteros 1/2/3/4 en el Middleware | Crítica | Bajo |
| 2 | Corregir regla de `differential_pairs`: Middleware rutea manualmente ANTES de Freerouting, no delegado | Crítica | Bajo |
| 3 | Eliminar `grid_origin` del schema (hardcodear en Middleware) | Media | Bajo |
| 4 | Documentar semántica de `pin_map` arrays → expansión automática a todos los pines | Alta | Bajo |
| 5 | Agregar `layer_count` opcional a project_metadata | Alta | Bajo |
| 6 | NO agregar `keepout_zones` al prompt (las huellas oficiales ya las tienen) | Info | Ninguno |

---

## 🏆 Veredicto Final

El prompt v3.1 es **genuinamente bueno** — mejor que el 95% de lo que he visto en prompt engineering para EDA. Pero tiene **2 vulnerabilidades críticas** verificadas con evidencia real:

1. **Freerouting no soporta diferenciales** → el prompt promete algo imposible
2. **SKiDL usa enteros para unidades** → el Middleware necesita un traductor

Con los 5 parches propuestos, el sistema estará blindado para fabricación real. Sin ellos, funcionará para circuitos simples pero fallará en diseños con USB, CAN, o chips multi-gate.

**¿Integro estos parches en un prompt v3.2, o prefieres evaluar primero con los otros auditores?**
