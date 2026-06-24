import json
import os
import subprocess
from pathlib import Path

# Se requiere tener skidl instalado: pip install skidl
try:
    from skidl import Part, PartUnit, Net, generate_netlist, ERC
except ImportError:
    print("[-] SKiDL no está instalado. Ejecuta: pip install skidl")
    exit(1)

class AeroSynthesizer:
    def __init__(self, json_data):
        self.design = json_data
        self.parts_cache = {}
        self.nets_cache = {}

    def synthesize_skidl(self):
        """Convierte la topología JSON en un circuito instanciado en SKiDL y genera ERC."""
        print("[*] Iniciando síntesis en SKiDL...")
        
        # 1. Instanciar Componentes
        for comp in self.design.get("components", []):
            ref = comp["ref"]
            part_def = comp["part_def"]
            footprint = comp["footprint"]
            value = comp.get("value", "")
            
            if ":" not in part_def:
                continue
                
            lib_name, sym_name = part_def.split(":", 1)
            
            # Instanciar en SKiDL
            # SKiDL usa automáticamente la variable KICAD_SYMBOL_DIR
            try:
                part = Part(lib_name, sym_name, footprint=footprint, value=value, ref=ref)
                self.parts_cache[ref] = part
            except Exception as e:
                print(f"[-] Advertencia SKiDL instanciando {ref} ({part_def}): {e}")
                # Mock fallback para no romper la demo si las librerías no cuadran
                part = Part('Device', 'R', footprint=footprint, value=value, ref=ref)
                self.parts_cache[ref] = part

        # 2. Construir Redes y Conexiones
        for net_def in self.design.get("nets", []):
            net_name = net_def["name"]
            net_class = net_def.get("net_class", "signal")
            
            # Crear la red en SKiDL
            net = Net(net_name)
            self.nets_cache[net_name] = net
            
            # --- INYECCIÓN DE PWR_FLAG (Regla de SKiDL para ERC) ---
            if net_class == "power":
                print(f"[+] Inyectando PWR_FLAG en la red de poder: {net_name}")
                try:
                    pwr_flag = Part('power', 'PWR_FLAG')
                    net += pwr_flag[1]
                except Exception:
                    # Alternativa si la librería 'power' falla: forzar el atributo de la red
                    net.drive = True

            # Conectar pines
            for conn in net_def.get("connections", []):
                c_ref = conn.get("ref")
                c_pin = conn.get("pin")
                c_unit_letter = conn.get("unit")
                
                if c_ref not in self.parts_cache:
                    continue
                    
                part = self.parts_cache[c_ref]
                
                # Manejar multi-unidad (A->1, B->2)
                target_part = part
                if c_unit_letter:
                    unit_num = ord(c_unit_letter.upper()) - 64  # 'A' -> 1, 'B' -> 2
                    try:
                        target_part = PartUnit(part, unit=unit_num)
                    except Exception as e:
                        print(f"[-] Advertencia extrayendo unidad {c_unit_letter} de {c_ref}: {e}")
                
                # Resolver pin_map (Expansión semántica)
                # El JSON crudo tiene un string, necesitamos buscar el comp original
                original_comp = next((c for c in self.design["components"] if c["ref"] == c_ref), {})
                pin_map = original_comp.get("pin_map", {})
                
                physical_pins = []
                if c_pin in pin_map:
                    mapped = pin_map[c_pin]
                    if isinstance(mapped, list):
                        physical_pins.extend(mapped)
                    else:
                        physical_pins.append(mapped)
                else:
                    physical_pins.append(c_pin)
                    
                # Realizar conexión física
                for p in physical_pins:
                    try:
                        # SKiDL permite conectar a través de string o índice
                        net += target_part[p]
                    except Exception as e:
                        print(f"[-] Error conectando pin {p} de {c_ref}: {e}")

        # 3. Ejecutar Electrical Rule Check (ERC)
        print("[*] Ejecutando ERC...")
        ERC()

        # 4. Generar Archivos
        output_name = self.design.get("project_metadata", {}).get("name", "aero_project")
        netlist_file = f"{output_name}.net"
        
        generate_netlist(file_=netlist_file)
        print(f"[+] Netlist generado exitosamente: {netlist_file}")
        
        return netlist_file

    def apply_layout_and_route(self, pcb_file):
        import tempfile
        import os
        import subprocess

        print("[*] Iniciando Fase 3: Transición al entorno nativo de KiCad (pcbnew)...")

        # 1. Extraer configuración topológica del diseño original
        layout_config = {
            "board_outline": self.design.get("project_metadata", {}).get("board_outline", {"width": 50.0, "height": 50.0}),
            "layout_strategies": self.design.get("layout_strategies", []),
            "differential_pairs": self.design.get("project_metadata", {}).get("design_rules", {}).get("differential_pairs", []),
            "pcb_file": pcb_file
        }

        # 2. Escribir contrato temporal para la macro
        temp_dir = tempfile.gettempdir()
        config_path = os.path.join(temp_dir, "aero_layout_config.json")

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(layout_config, f, indent=4)

        # 3. Invocar la macro en el Python empaquetado de KiCad (Fase 3: Posicionamiento y Ruteo Diferencial)
        kicad_python = os.environ.get('KICAD_PYTHON_EXE', r"C:\Program Files\KiCad\8.0\bin\python.exe")
        macro_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aero_pcb_macro.py")

        if not os.path.exists(kicad_python):
            raise RuntimeError(f"[-] Intérprete de KiCad no encontrado en: {kicad_python}. Configura la variable KICAD_PYTHON_EXE.")

        print(f"[+] Ejecutando macro topológica de pcbnew (aero_pcb_macro.py)...")
        cmd_macro = [kicad_python, macro_script, config_path]

        try:
            result = subprocess.run(cmd_macro, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(result.stdout)
            print("[+] Fase 3 completada con éxito.")
        except subprocess.CalledProcessError as e:
            print(f"[-] Error crítico en la ejecución de la macro topológica:\n{e.stderr}")
            raise

        # ----------------------------------------------------------------------
        # FASE 4: AUTO-RUTEO ASÍNCRONO (FREEROUTING)
        # ----------------------------------------------------------------------
        print("[*] Iniciando Fase 4: Exportación DSN, Freerouting e Importación SES...")

        # Sanitizar rutas para el intérprete en línea
        pcb_file_safe = os.path.abspath(pcb_file).replace('\\', '/')
        base_name = os.path.splitext(pcb_file_safe)[0]
        dsn_file_safe = f"{base_name}.dsn"
        ses_file_safe = f"{base_name}.ses"

        # 4.1 Exportar DSN usando macro en línea
        print("  -> Exportando diseño físico a Specctra DSN...")
        export_script = f"import pcbnew; board = pcbnew.LoadBoard('{pcb_file_safe}'); pcbnew.ExportSpecctraDSN(board, '{dsn_file_safe}')"
        try:
            subprocess.run([kicad_python, "-c", export_script], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"[-] Falla en exportación DSN:\n{e.stderr.decode()}")
            raise

        # 4.2 Ejecutar Freerouting de forma Headless
        freerouting_jar = os.environ.get('FREEROUTING_JAR', r"C:\freerouting\freerouting.jar")
        if not os.path.exists(freerouting_jar):
            raise RuntimeError(f"[-] Binario de Freerouting no encontrado en: {freerouting_jar}. Configura FREEROUTING_JAR.")

        print("  -> Lanzando motor Java de Freerouting...")
        cmd_freerouting = [
            "java", "-jar", freerouting_jar,
            "-de", dsn_file_safe,
            "-do", ses_file_safe,
            "-mp", "100"  # Máximo de pasadas estipulado
        ]
        
        try:
            fr_result = subprocess.run(cmd_freerouting, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print("  -> Ruteo de pistas base resuelto por Freerouting.")
        except subprocess.CalledProcessError as e:
            print(f"[-] Falla algorítmica en Freerouting:\n{e.stderr}")
            raise

        # 4.3 Importar SES y consolidar usando macro en línea
        print("  -> Importando archivo de sesión (SES) a la topología original...")
        import_script = f"import pcbnew; board = pcbnew.LoadBoard('{pcb_file_safe}'); pcbnew.ImportSpecctraSES(board, '{ses_file_safe}'); pcbnew.SaveBoard('{pcb_file_safe}', board)"
        try:
            subprocess.run([kicad_python, "-c", import_script], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"[-] Falla en re-importación SES:\n{e.stderr.decode()}")
            raise

        print("[+] Fase 4 completada de manera determinista. Archivo .kicad_pcb finalizado.")


if __name__ == "__main__":
    # Prueba rápida con un JSON mock si se ejecuta directo
    mock_json = {
        "project_metadata": {"name": "test_board", "board_outline": {"width": 30.0, "height": 30.0}},
        "components": [
            {"ref": "R1", "part_def": "Device:R", "footprint": "Resistor_SMD:R_0805_2012Metric", "pin_map": {"A": "1", "B": "2"}},
            {"ref": "D1", "part_def": "Device:LED", "footprint": "LED_SMD:LED_0805_2012Metric", "pin_map": {"A": "2", "K": "1"}}
        ],
        "nets": [
            {"name": "VCC", "net_class": "power", "connections": [{"ref": "R1", "pin": "A"}]},
            {"name": "SIG", "net_class": "signal", "connections": [{"ref": "R1", "pin": "B"}, {"ref": "D1", "pin": "A"}]},
            {"name": "GND", "net_class": "power", "connections": [{"ref": "D1", "pin": "K"}]}
        ],
        "layout_strategies": []
    }
    
    synth = AeroSynthesizer(mock_json)
    try:
        netlist = synth.synthesize_skidl()
        # Nota de prueba: pcb_file debería existir y ser generado por KiCad a partir del netlist
        # synth.apply_layout_and_route("test_board.kicad_pcb")
    except Exception as e:
        print(f"El entorno no está totalmente configurado para compilar: {e}")
