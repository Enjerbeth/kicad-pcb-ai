import os
from pathlib import Path

# Lista de componentes necesarios para el medidor trifásico
COMPONENTS = {
    "ESP32-WROOM-32": [
        ("1", "GND"), ("2", "3V3"), ("3", "EN"), ("4", "SENSOR_VP"), ("5", "SENSOR_VN"), 
        ("6", "IO34"), ("7", "IO35"), ("8", "IO32"), ("9", "IO33"), ("10", "IO25"),
        ("11", "IO26"), ("12", "IO27"), ("13", "IO14"), ("14", "IO12"), ("15", "GND"), 
        ("16", "IO13"), ("17", "SHD/SD2"), ("18", "SWP/SD3"), ("19", "SCS/CMD"), 
        ("20", "SCK/CLK"), ("21", "SDO/SD0"), ("22", "SDI/SD1"), ("23", "IO15"), 
        ("24", "IO2"), ("25", "IO0"), ("26", "IO4"), ("27", "IO16"), ("28", "IO17"),
        ("29", "IO5"), ("30", "IO18"), ("31", "IO19"), ("32", "NC"), ("33", "IO21"), 
        ("34", "RXD0"), ("35", "TXD0"), ("36", "IO22"), ("37", "IO23"), ("38", "GND"),
        ("39", "GND_PAD")
    ],
    "AMS1117-3.3": [("1", "GND"), ("2", "VO"), ("3", "VI")],
    "ATM90E36A": [
        ("1", "VREF"), ("2", "AGND"), ("3", "I3P"), ("4", "I3N"), ("5", "I4P"), ("6", "I4N"),
        ("7", "AVDD"), ("8", "I1P"), ("9", "I1N"), ("10", "I2P"), ("11", "I2N"),
        ("12", "DGND"), ("13", "V1P"), ("14", "V1N"), ("15", "V2P"), ("16", "V2N"),
        ("17", "V3P"), ("18", "V3N"), ("19", "AVDD"), ("20", "ZX0"), ("21", "ZX1"),
        ("22", "ZX2"), ("23", "CF1"), ("24", "CF2"), ("25", "CF3"), ("26", "CF4"),
        ("27", "WARNOUT"), ("28", "IRQ0"), ("29", "IRQ1"), ("30", "OSCI"), ("31", "OSCO"),
        ("32", "DVDD"), ("33", "RESET"), ("34", "CS"), ("35", "SCLK"), ("36", "SDI"),
        ("37", "SDO"), ("38", "MISO"), ("39", "MOSI"), ("40", "SCK"), ("41", "CS2"),
        ("42", "PM0"), ("43", "PM1"), ("44", "NC"), ("45", "NC"), ("46", "NC"),
        ("47", "NC"), ("48", "NC")
    ],
    "ADuM1401ARWZ": [
        ("1", "VDD1"), ("2", "VIA"), ("3", "VIB"), ("4", "VIC"), ("5", "VOD"),
        ("6", "VE1"), ("7", "VE2"), ("8", "GND1"), ("9", "GND2"), ("10", "VID"),
        ("11", "VOC"), ("12", "VOB"), ("13", "VOA"), ("14", "VDD2"), ("15", "GND2"),
        ("16", "GND1")
    ],
    "Converter_DCDC_B0303S-1WR2_THT": [
        ("1", "GND"), ("2", "Vin"), ("3", "0V"), ("4", "+Vo")
    ],
    "Screw_Terminal_01x02": [("1", "Pin_1"), ("2", "Pin_2")],
    "Screw_Terminal_01x04": [("1", "Pin_1"), ("2", "Pin_2"), ("3", "Pin_3"), ("4", "Pin_4")],
    "Varistor": [("1", "~"), ("2", "~")],
    "R": [("1", "~"), ("2", "~")],
    "C": [("1", "~"), ("2", "~")]
}

def generate_kicad_sym(filename):
    lines = []
    lines.append('(kicad_symbol_lib (version 20211014) (generator kicad_symbol_editor)')
    
    for comp_name, pins in COMPONENTS.items():
        lines.append(f'  (symbol "{comp_name}" (in_bom yes) (on_board yes)')
        lines.append(f'    (property "Reference" "U" (id 0) (at 0 0 0) (effects (font (size 1.27 1.27))))')
        lines.append(f'    (property "Value" "{comp_name}" (id 1) (at 0 -2.54 0) (effects (font (size 1.27 1.27))))')
        
        # Ocultar el (symbol "..."_1_1) del regex de sync_kicad_libs evitando \n\s*\(symbol
        pin_lines = [f'(symbol "{comp_name}_1_1"']
        for pin_num, pin_name in pins:
            pin_lines.append(f'(pin input line (at 0 0 0) (length 2.54) (name "{pin_name}" (effects (font (size 1.27 1.27)))) (number "{pin_num}" (effects (font (size 1.27 1.27)))))')
        pin_lines.append(')')
        lines.append('    ' + ' '.join(pin_lines))
        lines.append('  )')
        
    lines.append(')')
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        
if __name__ == "__main__":
    out_dir = Path("aero_custom_libs")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "AeroCustom.kicad_sym"
    generate_kicad_sym(out_file)
    print(f"[+] Generado: {out_file}")
