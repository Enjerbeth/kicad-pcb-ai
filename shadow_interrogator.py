import json
import sqlite3
import jsonschema
from pathlib import Path

DB_PATH = Path(__file__).parent / "kicad_cache.db"

# Esquema JSON estricto (alineado con V3.2 FINAL)
HAC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["project_metadata", "components", "nets", "layout_strategies"],
    "properties": {
        "project_metadata": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "units"],
            "properties": {
                "name": {"type": "string"},
                "units": {"type": "string"},
                "board_outline": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "width": {"type": "number"},
                        "height": {"type": "number"}
                    },
                    "required": ["width", "height"]
                },
                "layer_count": {"type": "integer"},
                "copper_pours": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "design_rules": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "default_track_width": {"type": "number"},
                        "power_track_width": {"type": "number"},
                        "min_clearance": {"type": "number"},
                        "via_diameter": {"type": "number"},
                        "via_drill": {"type": "number"},
                        "differential_pairs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "net_p": {"type": "string"},
                                    "net_n": {"type": "string"}
                                },
                                "required": ["net_p", "net_n"]
                            }
                        }
                    }
                },
                "footprint_policy": {"type": "string"}
            }
        },
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ref", "part_def", "footprint"],
                "properties": {
                    "ref": {"type": "string"},
                    "part_def": {"type": "string"},
                    "footprint": {"type": "string"},
                    "value": {"type": "string"},
                    "pin_map": {
                        "type": "object",
                        "additionalProperties": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}}
                            ]
                        }
                    },
                    "circuit_group": {"type": "string"}
                }
            }
        },
        "nets": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "connections"],
                "properties": {
                    "name": {"type": "string"},
                    "net_class": {"type": "string"},
                    "connections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["ref", "pin"],
                            "properties": {
                                "ref": {"type": "string"},
                                "pin": {"type": "string"},
                                "unit": {"type": "string"}
                            }
                        }
                    }
                }
            }
        },
        "layout_strategies": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["strategy_id", "strategy_type", "target_refs", "parameters", "collision_fallback"],
                "properties": {
                    "strategy_id": {"type": "string"},
                    "strategy_type": {"type": "string"},
                    "target_refs": {"type": "array", "items": {"type": "string"}},
                    "parameters": {"type": "object"},
                    "collision_fallback": {"type": "string"}
                }
            }
        },
        "unresolved_parts": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}

class ShadowInterrogator:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def disconnect(self):
        if self.conn:
            self.conn.close()

    def validate_json(self, json_data):
        """Valida la sintaxis del JSON y la coherencia semántica contra la DB de KiCad."""
        self.connect()
        errors = []
        
        # 1. Validación de Esquema (Sintáctica)
        try:
            jsonschema.validate(instance=json_data, schema=HAC_SCHEMA)
        except jsonschema.exceptions.ValidationError as e:
            errors.append({
                "code": "VALIDATION_FAILED",
                "severity": "error",
                "description": f"Error de esquema JSON: {e.message}",
                "instruction": "Corrige el JSON para cumplir con el esquema v3.2 estricto."
            })
            self.disconnect()
            return self._build_feedback(errors)

        # Mapeos internos para búsquedas rápidas
        components_map = {}
        for comp in json_data.get("components", []):
            components_map[comp["ref"]] = comp
            
        # 2. Validación Semántica contra SQLite
        cursor = self.conn.cursor()
        
        for ref, comp in components_map.items():
            part_def = comp["part_def"]
            if ":" not in part_def:
                errors.append({
                    "code": "LIBRARY_NOT_FOUND",
                    "severity": "error",
                    "description": f"El part_def '{part_def}' en {ref} no sigue el formato Librería:Símbolo.",
                    "affected_refs": [ref],
                    "instruction": "Usa el formato estándar de KiCad 8."
                })
                continue
                
            lib_name, sym_name = part_def.split(":", 1)
            
            # Consultar si el componente existe en la cache
            cursor.execute("SELECT id, total_pins, total_units FROM components WHERE library=? AND symbol=?", (lib_name, sym_name))
            db_comp = cursor.fetchone()
            
            if not db_comp:
                errors.append({
                    "code": "LIBRARY_NOT_FOUND",
                    "severity": "error",
                    "description": f"Componente {part_def} no encontrado en la base de datos local de KiCad.",
                    "affected_refs": [ref],
                    "instruction": "Verifica el nombre en KiCad 8 o muévelo a unresolved_parts."
                })
                continue
            
            # Extraer pines válidos para el contexto
            cursor.execute("SELECT pin_number, pin_name FROM pins WHERE component_id=?", (db_comp["id"],))
            db_pins = [row["pin_number"] for row in cursor.fetchall()]
            
            # Validar footprint en DB
            fp_def = comp["footprint"]
            if ":" in fp_def:
                fp_lib, fp_name = fp_def.split(":", 1)
                cursor.execute("SELECT id FROM footprints WHERE library=? AND footprint=?", (fp_lib, fp_name))
                if not cursor.fetchone():
                    # Para el interrogador, solo es un warning si la huella no está (podría instalarse luego)
                    pass

        # 3. Validación de Redes y Conexiones
        for net in json_data.get("nets", []):
            net_name = net["name"]
            connections = net.get("connections", [])
            
            if len(connections) < 2 and net.get("net_class") != "power":
                errors.append({
                    "code": "FLOATING_NET",
                    "severity": "warning",
                    "description": f"La red {net_name} tiene menos de 2 conexiones.",
                    "affected_nets": [net_name],
                    "instruction": "Conecta la red a otro pin o márcala como power si es un power flag."
                })

            for conn in connections:
                c_ref = conn.get("ref")
                c_pin = conn.get("pin")
                c_unit = conn.get("unit")
                
                if c_ref not in components_map:
                    errors.append({
                        "code": "VALIDATION_FAILED",
                        "severity": "error",
                        "description": f"La red {net_name} hace referencia a {c_ref}, que no existe en components.",
                        "affected_refs": [c_ref],
                        "instruction": "Agrega el componente al array components."
                    })
                    continue
                    
                # Evaluar alias vs pin físico
                comp_def = components_map[c_ref]
                pin_map = comp_def.get("pin_map", {})
                
                # Resolviendo expansión de alias (ej. GND -> ["1", "15"])
                physical_pins = []
                if c_pin in pin_map:
                    mapped = pin_map[c_pin]
                    if isinstance(mapped, list):
                        physical_pins.extend(mapped)
                    else:
                        physical_pins.append(mapped)
                else:
                    physical_pins.append(c_pin)

                # Verificar contra la DB (solo si el componente existe en DB)
                part_def = comp_def["part_def"]
                if ":" in part_def:
                    lib_name, sym_name = part_def.split(":", 1)
                    cursor.execute("SELECT id, total_pins, total_units FROM components WHERE library=? AND symbol=?", (lib_name, sym_name))
                    db_comp = cursor.fetchone()
                    
                    if db_comp:
                        if db_comp["total_pins"] == -1:
                            # Saltamos la validación estricta de pines físicos para los componentes derivados (extends)
                            # Dejamos que SKiDL lo verifique en la fase de síntesis.
                            pass
                        else:
                            cursor.execute("SELECT pin_number, pin_name FROM pins WHERE component_id=?", (db_comp["id"],))
                            valid_pins = [row["pin_number"] for row in cursor.fetchall()]
                            valid_pin_names = [row["pin_name"] for row in cursor.fetchall()] # A veces se usan nombres de pines en lugar de números
                            all_valid = valid_pins + valid_pin_names
                            
                            for p in physical_pins:
                                if p not in all_valid:
                                    errors.append({
                                        "code": "PIN_NOT_FOUND",
                                        "severity": "error",
                                        "description": f"El pin físico '{p}' no existe en {comp_def['part_def']} ({c_ref}).",
                                        "affected_refs": [c_ref],
                                        "affected_nets": [net_name],
                                        "instruction": "Usa uno de los pines válidos.",
                                        "context": {
                                            "failing_connection": {"ref": c_ref, "pin": p},
                                            "valid_pins_from_library": valid_pins
                                        }
                                    })
                                
                        # Verificar multi-unidad
                        if db_comp["total_units"] > 1 and not c_unit:
                            # Convertimos 1, 2, 3 a A, B, C para el LLM
                            valid_units_letters = [chr(64 + i) for i in range(1, db_comp["total_units"] + 1)]
                            errors.append({
                                "code": "UNIT_MISMATCH",
                                "severity": "error",
                                "description": f"El componente {c_ref} ({comp_def['part_def']}) es multi-puerta y requiere el campo 'unit'.",
                                "affected_refs": [c_ref],
                                "instruction": "Agrega 'unit' a la conexión.",
                                "context": {
                                    "valid_units": valid_units_letters
                                }
                            })

        self.disconnect()
        
        if errors:
            return self._build_feedback(errors)
        return {"status": "SUCCESS", "message": "JSON Validado y Listo para Síntesis (SKiDL/pcbnew)"}

    def _build_feedback(self, errors):
        return {
            "feedback_status": errors[0]["code"] if errors else "VALIDATION_FAILED",
            "retry_number": 1, # Deberá ser inyectado por el orquestador principal
            "max_retries": 3,
            "errors": errors
        }

if __name__ == "__main__":
    print("[*] Iniciando Shadow Interrogator V1")
    # Para probar el validador, aquí se puede inyectar un JSON de prueba
    interrogator = ShadowInterrogator()
    print("[+] Validador listo. Esperando JSON...")
