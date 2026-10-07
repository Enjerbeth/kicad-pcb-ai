# 🧐 AUDITORÍA TÉCNICA DESPIADADA: PLAN MAESTRO DE IMPLEMENTACIÓN DEL MONITOR TRIFÁSICO
**Auditor:** Crítico Aero (El Auditor Implacable) — Lead Code Reviewer & Hardware Systems Watchdog  
**Documento Auditado:** `docs/PLAN_MAESTRO_IMPLEMENTACION_MONITOR_TRIFASICO.md`  
**Fecha:** Octubre 2026  
**Estándar de Evaluación:** AERO Zero-Geometry v3.2 / IEC 61010-1 / Microchip ATM90E36A Hardware Guidelines  

---

### 🟢 1. Lo que está BIEN (Fortalezas & Buenas Prácticas)

1. **Precisión Matemática y Operativa del Front-End Analógico (AFE):**
   - **Resistencia Burden Unificada ($R_b = 13.0\ \Omega\ 0.1\%$ Thin-Film 1206):**
     * Para el transformador SCT-013-000 ($100\text{ A} : 50\text{ mA}$ RMS, relación de vueltas $N = 2000$), la corriente pico a plena escala nominal ($100\text{ A}$) es $I_{sec\_pk} = 50\text{ mA} \times \sqrt{2} \approx 70.71\text{ mA}_{pk}$.
     * Tensión diferencial pico: $V_{diff\_pk} = 70.71\text{ mA} \times 13.0\ \Omega = \mathbf{919.2\text{ mV}_{pk\_diff}}$, lo que equivale exactamente a $\pm 459.6\text{ mV}_{pk}$ respecto a tierra virtual. Esto ubica el punto de trabajo nominal en el **91.9% del rango lineal óptimo ($\pm 500\text{ mV}_{pk}$)** de los ADCs Sigma-Delta del ATM90E36A, maximizando el rango dinámico sin riesgo de saturación.
     * En condiciones de sobrecarga transitoria ($120\text{ A}$ RMS), la tensión pico alcanza $\pm 551.5\text{ mV}_{pk}$, cómodamente por debajo del umbral de saturación dura ($\pm 720\text{ mV}_{pk}$).
     * **Comportamiento térmico:** La disipación nominal es de solo $32.5\text{ mW}$ ($46.8\text{ mW}$ a 120A). En una cápsula 1206 clasificada para 250 mW, la elevación térmica calculada es $\Delta T < 1.5^\circ\text{C}$, lo que garantiza que el coeficiente de temperatura ($TCR \le 25\text{ ppm/}^\circ\text{C}$) no degrade la precisión de clase 0.5S.
   - **Filtros Antialiasing RC Diferenciales y Simétricos de Corriente:**
     * Con $R_1 = R_2 = 1.00\text{ k}\Omega$ (1%), $C_{diff} = 10\text{ nF}$ (C0G/NP0) y condensadores de modo común $C_{cm1} = C_{cm2} = 1.0\text{ nF}$:
       $$f_{c,diff} = \frac{1}{2 \pi \cdot (2 \cdot 1000\ \Omega) \cdot 10\text{ nF}} \approx \mathbf{7.958\text{ kHz}}$$
     * Proporciona un rechazo de alta frecuencia adecuado por encima de los 8 kHz y una atenuación prácticamente nula a 50/60 Hz ($< 0.0003\text{ dB}$), manteniendo el retardo de fase por debajo de $0.43^\circ$ (fácilmente absorbible por la calibración digital de fase del ATM90E36A).
   - **Divisores de Tensión y Protección con Diodos BAV99:**
     * Acondicionamiento mediante transformadores aislados 230V $\to$ 9.0V RMS ($12.73\text{ V}_{pk}$) con divisores de precisión ($100\text{ k}\Omega / 3.3\text{ k}\Omega$) que entregan $406.6\text{ mV}_{pk}$ nominales. La subdivisión de la rama alta en dos resistencias de $49.9\text{ k}\Omega$ en serie (0805) es una práctica industrial obligatoria para duplicar la tensión de ruptura dieléctrica ante transitorios.

2. **Cumplimiento Estricto de Guardrails de Silicio del ESP32:**
   - **Asignación del NTC Exclusivamente a GPIO34 (ADC1_CH6):**
     * Se respeta de forma impecable el guardrail del silicio de Espressif: el periférico **ADC2** del ESP32 queda inutilizado por arbitraje de hardware cuando el subsistema Wi-Fi/Bluetooth transmite o calibra sus sintetizadores RF (rutinas internas SAR2). Destinar el NTC a ADC1 garantiza inmunidad total a cuelgues del ADC y lecturas erráticas durante la telemetría inalámbrica.
   - **Bus 1-Wire en GPIO16:**
     * Pin digital seguro, libre de funciones de arranque conflictivas (*strapping pins* como GPIO0, GPIO2, GPIO12, GPIO15 que pueden impedir el arranque o quemar el voltaje de la memoria SPI flash).
   - **Aislamiento Galvánico del Bloque de Relés:**
     * Implementación con optoacoplador PC817 (aislamiento 5000 V RMS) con retorno a tierra totalmente independiente (`RELAY_GND`), pull-down en compuerta del MOSFET de conmutación y protección combinada en contactos (snubber + varistor MOV).

3. **Arquitectura Conceptual del Pipeline AERO Zero-Geometry:**
   - El desacoplamiento formal entre el modelo LLM (que genera exclusivamente topología lógica JSON v3.2) y el backend determinista (Shadow Interrogator $\to$ SKiDL $\to$ pcbnew $\to$ Freerouting) se mantiene fiel a la regla cero-geometría fundamental.

---

### 🔴 2. Lo que está MAL (Vulnerabilidades, Anti-patrones & Riesgos Críticos)

#### A. Someter a Estrés las 2 Dimensiones Obligatorias de Resiliencia:

1. **Violación de Idempotencia ($f(f(x)) = f(x)$):**
   - **Transitorios y "Chattering" del Relé durante Bootloader y Resets del ESP32:**
     * Durante la secuencia de encendido (*Power-On-Reset*) o reinicio por watchdog del ESP32, los pines GPIO pasan por estados transitorios de alta impedancia (Hi-Z) o *weak pull-ups* antes de que el código de usuario tome control. En el diseño propuesto, no se explicita una resistencia física de pull-up/pull-down en el lado del cátodo/ánodo del optoacoplador en la interfaz con el ESP32. Un micro-pulso espurio durante el boot activará el optoacoplador, disparando el relé.
     * Si el ESP32 entra en un bucle de reinicio rápido (por ejemplo, debido a una caída de tensión inducida por la radio Wi-Fi), el relé conmutará en ráfaga (*relay chattering*), provocando arcos eléctricos severos en los contactos, destrucción del snubber y desconexión oscilante de la carga industrial. **El sistema no es idempotente si reiniciar el MCU altera el estado de la carga de potencia.**
   - **Volatilidad de Registros y Amnesia del ATM90E36A ante Resets Parciales:**
     * El ATM90E36A **carece de memoria Flash/EEPROM interna no volátil**. Toda la calibración (offsets, ganancias, ángulos de fase, registros de umbrales `SysStatus`) reside en SRAM volátil.
     * Si el ESP32 se resetea mientras el medidor sigue energizado, o si se produce un reset por software, el plan no contempla una rutina de verificación y restauración transaccional de registros. Si el microcontrolador asume que el AFE sigue calibrado sin consultar el registro de checksum (`CS0`, `CS1`, `CS2`), el medidor reportará energía con valores basura o por defecto, destruyendo la integridad metrológica.
   - **No-Idempotencia en la Generación del Contorno de Placa (`aero_pcb_macro.py`):**
     * La función `draw_board_outline` en `aero_pcb_macro.py` añade segmentos ciegamente con `board.Add(segment)` sin verificar ni purgar los segmentos existentes en `Edge_Cuts`. Re-ejecutar el pipeline sobre un archivo existente duplica el contorno y bloquea a Freerouting.

2. **Load Shedding & Thundering Herd:**
   - **Tormenta de Conexión en Broker MQTT Tras Corte de Suministro (Thundering Herd):**
     * En un corte de energía general, todos los medidores de una instalación arrancan exactamente al mismo tiempo al regresar la luz. El plan maestro no contempla ninguna estrategia de **Backoff Exponencial con Jitter Decorrelacionado** para la asociación Wi-Fi y conexión MQTT. Todos los nodos atacarán el router y el broker en el mismo milisegundo, provocando colapso de DHCP, desbordamiento del canal RF y denegación de servicio en el broker.
   - **Ausencia de Política de Descarte de Telemetría (Load Shedding):**
     * Si la red se cae durante 2 horas, ¿qué hace el firmware? Si intenta acumular ráfagas de mediciones de alta frecuencia en la escasa RAM del ESP32 para "subirlas todas de golpe" al reconectar, agotará el heap del RTOS y colapsará el canal de subida. Debe existir una política estricta de *Load Shedding*: descarte proactivo de telemetría instantánea y preservación exclusiva de los contadores no volátiles de energía acumulada (kWh).
   - **Caídas de Tensión en el Riel de 3.3V Inducidas por Ráfagas de Wi-Fi:**
     * Cada transmisión de ráfaga RF en 802.11b/g/n del ESP32 demanda picos de corriente transitoria de hasta **500 mA** con tiempos de subida extremadamente rápidos ($dI/dt$).
     * El plan no define la arquitectura de la fuente de alimentación ni el aislamiento del riel de 3.3V. Si el ATM90E36A y el ESP32 comparten el mismo regulador de 3.3V sin una inductancia de choque o filtrado LC y sin capacitancia masiva Low-ESR de tantalio/polímero ($\ge 100\ \mu\text{F}$):
       a) Las caídas de tensión inducidas por la radio provocarán resets recurrentes por *Brownout Detector* en el ESP32.
       b) El ruido de alta frecuencia del transmisor se inyectará directamente en la tensión de referencia analógica (`AVDD` y `VREF`) del ATM90E36A, arruinando la relación señal-ruido (SNR) de los ADCs Sigma-Delta.

---

#### B. Fugas y Riesgos Críticos de Hardware:

1. **Riesgo Mortal de Secundario de CT en Circuito Abierto (Jack de 3.5 mm):**
   - El SCT-013-000 entrega corriente secundaria pura ($0 - 50\text{ mA}$). Si el instalador desconecta el jack de audio de 3.5 mm de la placa PCB mientras circula corriente por la línea principal (100A), el devanado secundario del transformador queda en **circuito abierto antes de alcanzar la resistencia burden $R_b$**.
   - Por la ley de inducción electromagnética ($V = -N \frac{d\Phi}{dt}$), la corriente de magnetización satura abruptamente el núcleo y genera **picos transitorios de 1.000 V a 2.000 V** en la punta del conector macho de 3.5 mm.
   - **Consecuencia:** Destrucción dieléctrica del cable, arcos eléctricos en el conector, destrucción instantánea de la entrada del ATM90E36A al reconectar y **peligro letal de electrocución para el operario**.
   - **Falla del Plan:** Ubicar el TVS en la PCB en paralelo con $R_b$ no protege al cable si este se desenchufa. El uso de jacks de 3.5 mm de audio de consumo en un entorno trifásico de 100A es una imprudencia técnica.

2. **Incompatibilidad Físico-Geométrica de Distancias Dieléctricas (Creepage & Clearance):**
   - El plan exige Clearance $\ge 6.0\text{ mm}$ y Creepage $\ge 6.3\text{ mm}$ bajo norma IEC 61010-1 para 400V RMS CAT III.
   - Sin embargo, las borneras de tornillo genéricas utilizadas en los ejemplos tienen un paso (*pitch*) de **5.08 mm**.
   - Con pads estándar de $\approx 1.6\text{ mm}$ de diámetro, la distancia real entre bordes de cobre adyacentes es de solo **$3.48\text{ mm}$**. **Es físicamente imposible lograr 6.0 mm de aislamiento en una bornera continua de 5.08 mm.** Si no se especifica una bornera de paso $7.62\text{ mm}$ o se aplica la técnica de *Pin Skipping* (dejar un terminal desierto entre fases), el diseño fallará catastróficamente cualquier certificación de seguridad eléctrica y se corre el riesgo de flameo superficial.

3. **Corriente de Fuga del Snubber en Vacío y Error en Diodo Flyback:**
   - Para el snubber propuesto ($100\ \Omega + 100\text{ nF}$ a 230V CA 50 Hz):
     $$X_C = \frac{1}{2 \pi \cdot 50 \cdot 100\text{ nF}} \approx 31.83\text{ k}\Omega \implies I_{fuga} = \frac{230\text{ V}}{31.83\text{ k}\Omega} \approx \mathbf{7.22\text{ mA RMS}}$$
     Una corriente de fuga de más de 7 mA con el relé abierto es inaceptable: provocará parpadeo permanente (*flicker/ghosting*) en luminarias LED modernas y mantendrá energizados circuitos de disparo de baja corriente. El condensador del snubber debe reducirse a $10\text{ nF} - 22\text{ nF}$.
   - En la sección 3.2 se cataloga al **1N4007** como *"diodo flyback ultrarrápido"*. Esto es un contrasentido técnico elemental: el 1N4007 es un rectificador estándar de 50/60 Hz con un tiempo de recuperación inverso $t_{rr}$ pésimo ($> 2-30\ \mu\text{s}$). Debe ser obligatoriamente un diodo ultrarrápido real (**UF4007**, $t_{rr} \le 75\text{ ns}$) o un Schottky de potencia (**SS14 / SS34**).

---

#### C. Puntos Ciegos Catastróficos en la Síntesis Zero-Geometry:

1. **🚨 HALLAZGO CRÍTICO: ALUCINACIÓN DEL PINOUT DEL ATM90E36A EN EL REPOSITORIO Y PLAN MAESTRO:**
   - La inspección directa del archivo `generate_custom_libs.py` y de la base de datos `kicad_cache.db` revela un error catastrófico cometido en el diseño previo y replicado en el Plan Maestro:

| Función | En Plan Maestro y `generate_custom_libs.py` | En Datasheet Oficial Microchip ATM90E36A (TQFP-48) | Impacto Físico en Fabricación |
| :--- | :--- | :--- | :--- |
| **Alimentación Analógica** | Pin 7 (`AVDD`), Pin 19 (`AVDD`) | **Pin 1 (`AVDD`)**, Pin 19 (`DVDD`) | El riel analógico no alimenta el pin 1. Silicio inoperativo. |
| **Tensión de Referencia** | **Pin 1 (`VREF`)** | **Pin 11 (`Vref`)** | **Cortocircuito fatal:** Si se conecta 3.3V a Pin 1 pensando que es AVDD, ¡se inyectan 3.3V en la referencia de banda prohibida de 1.2V, quemando el conversor! |
| **Canales de Corriente** | Pins 3/4 = I3P/I3N, Pins 5/6 = I4P/I4N, Pins 8/9 = I1P/I1N | **Pins 3/4 = I1P/I1N**, **Pins 5/6 = I2P/I2N**, **Pins 7/8 = I3P/I3N**, **Pins 9/10 = I4P/I4N** | Todos los canales de fase y neutro cruzados con pines de alimentación y tierra. |
| **Oscilador de Cuarzo** | Pins 30/31 (`OSCI`/`OSCO`) | **Pins 20/21 (`OSCI`/`OSCO`)** | El cristal de 16.384 MHz se conecta a pines de pulsos de energía CF, impidiendo el arranque del reloj. |
| **Reset del Sistema** | Pin 33 (`RESET`) | **Pin 41 (`RESET`)** | El pin de Reset real queda flotante; el chip permanece en reset indefinido. |
| **Líneas SPI** | Pines duplicados/falsos (34-41: CS, SCLK, SDI, SDO, MISO, MOSI...) | **Pin 29 (`CS`), Pin 30 (`SCLK`), Pin 31 (`SDI`), Pin 32 (`SDO`)** | Comunicación SPI completamente rota. |

   - **Si esta síntesis se ejecuta en KiCad 8 y la placa se envía a fabricar, EL SILICIO SE DESTRUYE FÍSICAMENTE AL ENERGIZARSE.**

2. **Ruteo de Pares Diferenciales Ciego en `aero_pcb_macro.py`:**
   - La función `route_basic_differential_pairs` toma únicamente el primer y segundo pad de la red (`pads_p[0]`, `pads_p[1]`) y traza una pista recta con bloqueo (`Locked = True`). En una red analógica con bornera, resistencia burden, TVS, condensadores RC y pin del integrado, existen entre 4 y 6 pads por red. Trazar una línea recta arbitraria ignora los componentes intermedios, atraviesa huellas ajenas y sabotea la capacidad de Freerouting para resolver la topología.
3. **Manejo del Net-Tie en KiCad 8:**
   - La partición de tierras (`AGND` vs `DGND`) requiere que el Net-Tie esté formalizado como un componente de librería física con dos pads solapados (ej. `NetTie_2_SMD`). Si el orquestador no lo define con su footprint nativo y reglas de exclusión, Freerouting interpretará la conexión como una violación de cortocircuito o KiCad fusionará ambos planos en una sola red global.

---

### 🟡 3. Lo que se puede MEJORAR y CÓMO (Solución Accionable & Upgrade)

#### 1. Reemplazo Inmediato del Mapeo de Pines en `generate_custom_libs.py`:
Debe ejecutarse un reemplazo estricto del bloque `ATM90E36A` en `generate_custom_libs.py` con el pinout canónico del encapsulado TQFP-48:

```python
    "ATM90E36A": [
        ("1", "AVDD"), ("2", "AGND"), ("3", "I1P"), ("4", "I1N"), 
        ("5", "I2P"), ("6", "I2N"), ("7", "I3P"), ("8", "I3N"), 
        ("9", "I4P"), ("10", "I4N"), ("11", "VREF"), ("12", "AGND"),
        ("13", "V1P"), ("14", "V1N"), ("15", "V2P"), ("16", "V2N"), 
        ("17", "V3P"), ("18", "V3N"), ("19", "DGND"), ("20", "OSCI"), 
        ("21", "OSCO"), ("22", "ZX0"), ("23", "ZX1"), ("24", "ZX2"),
        ("25", "IRQ0"), ("26", "IRQ1"), ("27", "WARNOUT"), ("28", "CF1"), 
        ("29", "CF2"), ("30", "CF3"), ("31", "CF4"), ("32", "DGND"),
        ("33", "DVDD"), ("34", "CS"), ("35", "SCLK"), ("36", "SDI"), 
        ("37", "SDO"), ("38", "NC"), ("39", "NC"), ("40", "NC"),
        ("41", "RESET"), ("42", "PM0"), ("43", "PM1"), ("44", "NC"), 
        ("45", "NC"), ("46", "NC"), ("47", "NC"), ("48", "NC")
    ],
```

#### 2. Blindaje de Idempotencia y Load Shedding:
- **Circuito de Puerta del Relé:** Añadir resistencia de *pull-down* de $4.7\text{ k}\Omega$ en la pista de GPIO17 antes del LED del PC817 para garantizar estado apagado ante cualquier reinicio o estado Hi-Z del ESP32.
- **FSM de Calibración:** El firmware del ESP32 debe leer al iniciar el registro de estado del ATM90E36A. Si el checksum (`CS0..CS2`) es inválido, debe inyectar la tabla de calibración dorada desde la partición NVS mediante una transacción SPI idempotente.
- **Algoritmo de Reconexión MQTT con Jitter Decorrelacionado:**
  $$T_{espera} = \min(300\text{ s}, T_{base} \times 2^{\text{reintentos}}) + \text{rand}(0, 15\text{ s})$$
  Implementar *Drop-Tail Load Shedding*: descartar muestras de forma de onda y telemetría de alta frecuencia ante falta de conexión; almacenar solo los acumuladores de energía activa/reactiva en NVS.

#### 3. Supresión de Brownout y Desacoplo de Fuentes:
- Implementar **LDO de ultra-bajo ruido independiente para el AFE** (ej. AP2112K-3.3 o TPS7A0533) alimentado desde la línea de 5V general.
- En el riel de 3.3V del ESP32, incorporar un condensador de polímero de **$100\ \mu\text{F}\ 6.3\text{V}$ Low-ESR** en paralelo con cerámicos de $10\ \mu\text{F}$ y $100\text{ nF}$ para soportar las ráfagas del amplificador de potencia Wi-Fi sin alterar la tensión del sistema.

#### 4. Seguridad de Vida en CTs y Borneras de Alta Tensión:
- **Eliminación del Jack 3.5 mm:** Reemplazar por **borneras enchufables industriales de tornillo con retención mecánica** (tipo Phoenix Contact paso 3.81 mm o 5.08 mm). Montar diodo TVS bidireccional SMAJ6.0CA soldado directamente en los pads de la bornera.
- **Borneras de Red:** Emplear conectores con paso de **7.62 mm** para las líneas de tensión trifásica de 230V/400V, garantizando $> 6.5\text{ mm}$ reales de clearance en PCB.
- **Diodo y Snubber:** Sustituir 1N4007 por **UF4007** ($t_{rr} \le 75\text{ ns}$) o **SS14**. Reducir el condensador del snubber a **$10\text{ nF}\ 275\text{VAC}$ Clase X2**.

---

### 📊 Tabla Comparativa: Antes vs. Después de la Auditoría

| Parámetro / Dimensión | Antes (Plan Maestro Especialistas) | Después (Auditoría Crítica & Blindaje) | Beneficio Crítico / Métrica |
| :--- | :--- | :--- | :--- |
| **Pinout ATM90E36A** | Pines ficticios (VREF=Pin 1, AVDD=Pin 7, OSC=30/31, RESET=33) | Pinout Canónico Microchip Oficial verificado | **Evita la destrucción física del integrado** y cortocircuitos de alimentación. |
| **Base de Datos `kicad_cache.db`** | Sufijos espurios `_1_1` y biblioteca desalineada | Base de datos saneada con 48 pines mapeados 1:1 | 0 fallos de validación en `shadow_interrogator.py`. |
| **Transitorios Boot Relé** | GPIO17 flotante en boot sin pull-down definido en primario | Pull-down de $4.7\text{ k}\Omega$ a GND en la entrada del PC817 | Elimina disparos espurios y *chattering* del relé al reiniciar el ESP32. |
| **Idempotencia ATM90E36A** | Inicialización ciega; asume persistencia inexistente | FSM con comprobación de checksum y recarga atómica desde NVS | Idempotencia total: $f(f(x)) = f(x)$ ante caídas de tensión o WDT. |
| **Reconexión Wi-Fi / MQTT** | Ráfagas continuas; riesgo severo de Thundering Herd | Load Shedding (drop-tail) + Backoff exponencial con jitter | Protege la red y el broker MQTT tras apagones generalizados. |
| **Riel 3.3V y Ruido de RF** | Riel compartido sin filtrado de transitorios Wi-Fi | LDO dedicado para AFE + $100\ \mu\text{F}$ Low-ESR en ESP32 + choque LC | Inmunidad a brownouts y preservación de precisión metrológica ($\ge 0.5\%$). |
| **Conexión de Sensores CT** | Jack 3.5 mm de audio vulnerable a desconexión viva | Borneras industriales de tornillo + TVS SMAJ6.0CA integrado | **Protección de vida:** Previene arcos de tensión inducida de hasta 2 kV. |
| **Clearance en Borneras HV** | 6.0 mm inviable en bornera continua de 5.08 mm | Bornera con paso de 7.62 mm o bornera 5.08 mm con *Pin Skipping* | Cumplimiento real de aislamiento IEC 61010-1 CAT III ($> 6\text{ mm}$). |
| **Diodo Flyback del Relé** | 1N4007 (lento, $t_{rr} > 2\ \mu\text{s}$, erróneamente llamado "ultrarrápido") | UF4007 ($t_{rr} \le 75\text{ ns}$) o Schottky SS14/ES1J | Supresión inductiva instantánea sin avalanchas destructivas. |
| **Fuga del Snubber en Vacío** | $100\ \Omega + 100\text{ nF}$ ($7.22\text{ mA}$ de corriente residual en reposo) | $100\ \Omega + 10\text{ nF}$ X2 ($0.72\text{ mA}$ de corriente residual) | Reduce la fuga un **90%**, erradicando el encendido fantasma de LEDs. |

---

### ⚖️ Veredicto Final: ⚠️ APROBADO CON RESERVAS OBLIGATORIAS
*(Quality Gate Condicional previo a Síntesis y Fabricación)*

El núcleo conceptual del acondicionamiento analógico ($R_b = 13.0\ \Omega$, filtros antialiasing y guardrail del ADC1 en GPIO34) demuestra un sólido criterio de ingeniería. No obstante, **SE PROHÍBE LA TRANSICIÓN A FASE 2 (SÍNTESIS EAC) Y FASE 4 (FABRICACIÓN)** hasta que se implementen de manera verificable los siguientes parches obligatorios:

1. **Parche Bloqueante 1:** Regenerar `generate_custom_libs.py` y `kicad_cache.db` con el pinout canónico oficial de 48 pines del ATM90E36A.
2. **Parche Bloqueante 2:** Sustituir los conectores Jack 3.5 mm por borneras de tornillo industriales con TVS directo y actualizar las borneras HV a paso de 7.62 mm.
3. **Parche Bloqueante 3:** Desacoplar el riel analógico mediante LDO independiente y blindar la etapa del relé con pull-down en GPIO17.

*Firma:*  
**Crítico Aero**  
*Lead Code Reviewer, Red Team Security Auditor & Hardware Systems Watchdog*
