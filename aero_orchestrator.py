import json
import os
import sys
import subprocess
from shadow_interrogator import ShadowInterrogator
from aero_synthesizer import AeroSynthesizer

class AeroOrchestrator:
    def __init__(self, pcb_filename="aero_board.kicad_pcb", max_retries=3):
        self.pcb_filename = pcb_filename
        self.max_retries = max_retries
        self.feedback_file = "aero_feedback.json"

    def _write_feedback(self, status, errors, retry_number):
        """Escribe el contrato de error estricto para el Agente LLM."""
        feedback = {
            "feedback_status": status,
            "retry_number": retry_number,
            "max_retries": self.max_retries,
            "errors": errors
        }
        with open(self.feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedback, f, indent=4)
        print(f"[-] Feedback loop generado en: {self.feedback_file}")
        return feedback

    def execute_pipeline(self, llm_json_path, current_retry=1):
        """Ejecuta el pipeline completo de 3 niveles y maneja el control de estado."""
        
        if current_retry > self.max_retries:
            print("[!] MAX RETRIES ALCANZADO. Proceso abortado. Requiere intervención humana.")
            return None

        print(f"\n========== AERO FRAMEWORK: ITERACIÓN {current_retry}/{self.max_retries} ==========")
        
        # Ingesta del JSON generado por el Agente
        try:
            with open(llm_json_path, 'r', encoding='utf-8') as f:
                design_data = json.load(f)
        except Exception as e:
            return self._write_feedback("VALIDATION_FAILED", [{
                "code": "JSON_PARSE_ERROR",
                "severity": "error",
                "description": f"El archivo JSON es inválido o corrupto: {str(e)}",
                "instruction": "Genera un bloque JSON sintácticamente válido sin texto adicional."
            }], current_retry)

        # ---------------------------------------------------------
        # NIVEL 1: Shadow Interrogator (Validación Temprana)
        # ---------------------------------------------------------
        print("[*] Nivel 1: Validación Semántica y Sintáctica...")
        interrogator = ShadowInterrogator()
        val_result = interrogator.validate_json(design_data)
        
        if val_result.get("feedback_status"): 
            # Se detectaron errores semánticos, re-empaquetar con estado de retry
            val_result["retry_number"] = current_retry
            val_result["max_retries"] = self.max_retries
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(val_result, f, indent=4)
            print(f"[-] Fallo en Nivel 1. Retornando control al Agente.")
            return val_result

        # ---------------------------------------------------------
        # NIVEL 2: SKiDL (Validación de Síntesis Lógica / ERC)
        # ---------------------------------------------------------
        print("[*] Nivel 2: Síntesis Lógica y Reglas Eléctricas...")
        synth = AeroSynthesizer(design_data)
        try:
            synth.synthesize_skidl()
        except Exception as e:
            error_str = str(e)
            # Traducción heurística de excepciones lógicas
            code = "ERC_FAILED"
            instruction = "Revisa las conexiones lógicas. Corrige pines incompatibles o redes cortocircuitadas."
            
            if "Floating" in error_str or "unconnected" in error_str:
                code = "FLOATING_NET"
                instruction = "Asegúrate de que la red tenga una fuente motriz (driver) o aplica un power flag."

            return self._write_feedback(code, [{
                "code": code,
                "severity": "error",
                "description": f"El motor ERC detectó una violación estructural: {error_str}",
                "instruction": instruction
            }], current_retry)

        # ---------------------------------------------------------
        # NIVEL 3: pcbnew & Freerouting (Validación Física y DRC)
        # ---------------------------------------------------------
        print("[*] Nivel 3: Síntesis Física y Enrutamiento Automático...")
        try:
            synth.apply_layout_and_route(self.pcb_filename)
        except subprocess.CalledProcessError as e:
            error_str = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
            
            # Traducción heurística de colisiones o fallos de Freerouting
            code = "DRC_POST_ROUTE"
            instruction = "Reduce el 'default_track_width' en design_rules o aumenta la separación."
            
            if "spiral" in error_str.lower() or "collision" in error_str.lower():
                code = "BOARD_OVERFLOW"
                instruction = "El bloque topológico colisiona sin espacio libre. Aumenta las dimensiones en 'board_outline' o reduce el 'spacing' en layout_strategies."

            return self._write_feedback("DRC_FAILED", [{
                "code": code,
                "severity": "error",
                "description": f"Fallo en la resolución física o enrutamiento: {error_str}",
                "instruction": instruction
            }], current_retry)
        except Exception as e:
            return self._write_feedback("DRC_FAILED", [{
                "code": "EXECUTION_ERROR",
                "severity": "error",
                "description": f"Excepción crítica en la macro de pcbnew: {str(e)}",
                "instruction": "Evalúa las dimensiones de la placa y los vectores topológicos suministrados."
            }], current_retry)

        # ---------------------------------------------------------
        # ÉXITO: Diseño Completado
        # ---------------------------------------------------------
        print("[+] PIPELINE COMPLETADO EXITOSAMENTE. Placa lista para manufactura.")
        if os.path.exists(self.feedback_file):
            os.remove(self.feedback_file) # Limpiar feedback anterior para no contaminar
            
        return {"feedback_status": "SUCCESS", "message": "Placa generada y ruteada correctamente."}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python aero_orchestrator.py <ruta_del_json_del_agente.json> [retry_number]")
        sys.exit(1)
        
    target_json = sys.argv[1]
    retry = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    orchestrator = AeroOrchestrator()
    orchestrator.execute_pipeline(target_json, retry)
