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

_SCHEMA_VALIDATOR = jsonschema.Draft202012Validator(HAC_SCHEMA) if hasattr(jsonschema, "Draft202012Validator") else jsonschema.Draft7Validator(HAC_SCHEMA)

class ShadowInterrogator:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None
        self._comp_cache = {}
        self._pins_cache = {}
        self._fp_cache = {}

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA cache_size = -16000;")
        self.conn.execute("PRAGMA mmap_size = 67108864;")

    def disconnect(self):
        if self.conn:
            self.conn.close()

    def _get_component(self, lib_name, sym_name):
        key = (lib_name, sym_name)
        if key not in self._comp_cache:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, total_pins, total_units FROM components WHERE library=? AND symbol=?", (lib_name, sym_name))
            row = cursor.fetchone()
            self._comp_cache[key] = dict(row) if row else None
        return self._comp_cache[key]

    def _get_pins(self, comp_id):
        if comp_id not in self._pins_cache:
            cursor = self.conn.cursor()
            cursor.execute("SELECT pin_number, pin_name FROM pins WHERE component_id=?", (comp_id,))
            rows = cursor.fetchall()
            self._pins_cache[comp_id] = {
                "numbers": [r["pin_number"] for r in rows],
                "names": [r["pin_name"] for r in rows],
                "all": [r["pin_number"] for r in rows] + [r["pin_name"] for r in rows]
            }
        return self._pins_cache[comp_id]

    def validate_json(self, json_data):
        """Valida la sintaxis del JSON y la coherencia semántica contra la DB de KiCad."""
        self.connect()
        errors = []
        
        # 1. Validación de Esquema (Sintáctica optimizada)
        schema_errors = list(_SCHEMA_VALIDATOR.iter_errors(json_data))
        if schema_errors:
            for e in schema_errors:
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
            
        # 2. Validación Semántica contra SQLite (con caché LRU)
        unresolved_refs = json_data.get("unresolved_parts", [])

        for ref, comp in components_map.items():
            part_def = comp["part_def"]
            
            # Saltamos la validación en DB si el componente fue declarado como unresolved
            if ref in unresolved_refs:
                continue
                
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
            
            # Consultar si el componente existe en la cache / DB
            db_comp = self._get_component(lib_name, sym_name)
            
            if not db_comp:
                errors.append({
                    "code": "LIBRARY_NOT_FOUND",
                    "severity": "error",
                    "description": f"Componente {part_def} no encontrado en la base de datos local de KiCad.",
                    "affected_refs": [ref],
                    "instruction": "Verifica el nombre en KiCad 8 o muévelo a unresolved_parts."
                })
                continue
            
            # Validar footprint en DB si aplica
            fp_def = comp.get("footprint", "")
            if ":" in fp_def:
                fp_lib, fp_name = fp_def.split(":", 1)
                fp_key = (fp_lib, fp_name)
                if fp_key not in self._fp_cache:
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT id FROM footprints WHERE library=? AND footprint=?", (fp_lib, fp_name))
                    self._fp_cache[fp_key] = cursor.fetchone() is not None

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

                # Verificar contra la DB usando la caché
                part_def = comp_def["part_def"]
                if ":" in part_def:
                    lib_name, sym_name = part_def.split(":", 1)
                    db_comp = self._get_component(lib_name, sym_name)
                    
                    if db_comp:
                        if db_comp["total_pins"] == -1:
                            # Saltamos la validación estricta de pines físicos para los componentes derivados (extends)
                            pass
                        else:
                            pin_info = self._get_pins(db_comp["id"])
                            all_valid = pin_info["all"]
                            valid_pins = pin_info["numbers"]
                            
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
