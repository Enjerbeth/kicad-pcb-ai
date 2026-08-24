import os
import sqlite3
import re
import glob
from pathlib import Path

# Configuración y Rutas (Ajustables mediante variables de entorno)
KICAD_SHARE_DIR = os.environ.get('KICAD_SYMBOL_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), "aero_custom_libs"))
SYMBOL_DIR = KICAD_SHARE_DIR
FOOTPRINT_DIR = KICAD_SHARE_DIR

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kicad_cache.db")

def configure_sqlite_pragmas(conn):
    """Configura PRAGMAs de alto rendimiento para acelerar lectura y escritura masiva."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA cache_size = -64000;")
    cursor.execute("PRAGMA mmap_size = 268435456;")
    cursor.execute("PRAGMA synchronous = NORMAL;")

def setup_database(conn):
    """Inicializa el esquema de la base de datos SQLite (Zero-RAM footprint para el Middleware)."""
    configure_sqlite_pragmas(conn)
    cursor = conn.cursor()
    cursor.executescript('''
        DROP TABLE IF EXISTS pins;
        DROP TABLE IF EXISTS components;
        DROP TABLE IF EXISTS footprints;

        CREATE TABLE components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library TEXT NOT NULL,
            symbol TEXT NOT NULL,
            total_pins INTEGER DEFAULT 0,
            total_units INTEGER DEFAULT 1,
            UNIQUE(library, symbol)
        );

        CREATE TABLE pins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_id INTEGER NOT NULL,
            pin_number TEXT NOT NULL,
            pin_name TEXT NOT NULL,
            electrical_type TEXT,
            FOREIGN KEY(component_id) REFERENCES components(id)
        );

        CREATE TABLE footprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library TEXT NOT NULL,
            footprint TEXT NOT NULL,
            has_courtyard BOOLEAN DEFAULT 0,
            UNIQUE(library, footprint)
        );
        
        CREATE INDEX idx_comp_lookup ON components(library, symbol);
        CREATE INDEX idx_foot_lookup ON footprints(library, footprint);
        CREATE INDEX IF NOT EXISTS idx_pins_component_id ON pins(component_id);
    ''')
    conn.commit()
    print(f"[+] Base de datos inicializada en: {DB_PATH}")

def parse_kicad_sym(filepath, conn):
    """Parsea superficialmente archivos .kicad_sym usando Regex para extraer componentes y pines."""
    lib_name = Path(filepath).stem
    cursor = conn.cursor()
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"[-] Error leyendo {filepath}: {e}")
        return

    # Extraer bloques de símbolos raíz (ignorando derivados para esta v1)
    # Patrón busca: (symbol "Nombre"
    # KiCad 8 a veces usa (symbol "lib_name:part_name" o (symbol "part_name"
    symbol_blocks = re.split(r'\n\s*\(symbol\s+"([^"]+)"', content)[1:]
    
    if not symbol_blocks:
        return

    components_added = 0
    
    for i in range(0, len(symbol_blocks), 2):
        raw_sym_name = symbol_blocks[i]
        sym_body = symbol_blocks[i+1]
        
        # Limpiar el nombre (quitar el prefijo de librería si lo tiene)
        sym_name = raw_sym_name.split(':')[-1] if ':' in raw_sym_name else raw_sym_name
        
        # Manejo de herencia (extends)
        extends_match = re.search(r'\(extends\s+"([^"]+)"\)', sym_body)
        
        pins = []
        if extends_match:
            # Componente heredado. Para una indexación perfecta, se debe consultar el padre en la DB.
            # En esta v1 asumimos que hereda sus pines del padre, marcamos con total_pins = -1 temporalmente
            # O permitimos que el Interrogador se salte la validación estricta de pines físicos
            # si total_pins == -1 (hasta desarrollar un parser recursivo).
            total_units = 1
            pins_derived = True
        else:
            # Componente base
            pins_derived = False
            for pin_match in re.finditer(r'\(pin\s+([a-zA-Z_]+).*?\(name\s+"([^"]*)".*?\(number\s+"([^"]+)"', sym_body, re.DOTALL):
                elec_type = pin_match.group(1)
                p_name = pin_match.group(2)
                p_num = pin_match.group(3)
                pins.append((p_num, p_name, elec_type))
            
            units_found = set(re.findall(r'\(symbol\s+"[^"]+_(\d+)_\d+"', sym_body))
            total_units = max([int(u) for u in units_found]) if units_found else 1
        
        if pins or pins_derived:
            try:
                # Si deriva, insertamos con -1 pines para indicar al interrogador que asuma flexibilidad
                pin_count = -1 if pins_derived else len(pins)
                cursor.execute("INSERT INTO components (library, symbol, total_pins, total_units) VALUES (?, ?, ?, ?)",
                               (lib_name, sym_name, pin_count, total_units))
                comp_id = cursor.lastrowid
                
                if not pins_derived:
                    pin_data = [(comp_id, p[0], p[1], p[2]) for p in pins]
                    cursor.executemany("INSERT INTO pins (component_id, pin_number, pin_name, electrical_type) VALUES (?, ?, ?, ?)", pin_data)
                
                components_added += 1
            except sqlite3.IntegrityError:
                pass # Símbolo duplicado
                
    conn.commit()
    return components_added

def parse_kicad_footprints(footprint_dir_path, conn):
    """Escanea carpetas .pretty y parsea archivos .kicad_mod para extraer Courtyards."""
    cursor = conn.cursor()
    lib_name = Path(footprint_dir_path).stem
    
    fps_to_insert = []
    for mod_file in glob.glob(os.path.join(footprint_dir_path, "*.kicad_mod")):
        fp_name = Path(mod_file).stem
        
        try:
            with open(mod_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue
            
        # Búsqueda rápida de la capa Courtyard (F.CrtYd o B.CrtYd)
        has_courtyard = 'F.CrtYd' in content or 'B.CrtYd' in content
        fps_to_insert.append((lib_name, fp_name, has_courtyard))
        
    if fps_to_insert:
        cursor.executemany("INSERT OR IGNORE INTO footprints (library, footprint, has_courtyard) VALUES (?, ?, ?)", fps_to_insert)
        conn.commit()
    return len(fps_to_insert)

def run_sync():
    print(f"[*] Iniciando sincronización de librerías KiCad 8 (Cold Indexing)")
    print(f"[*] Directorio de KiCad detectado: {KICAD_SHARE_DIR}")
    
    if not os.path.exists(SYMBOL_DIR) or not os.path.exists(FOOTPRINT_DIR):
        print("[-] ADVERTENCIA: No se encontraron los directorios de símbolos o huellas. Ajusta las variables de entorno.")
        return

    conn = sqlite3.connect(DB_PATH)
    setup_database(conn)
    
    # 1. Sincronizar Símbolos
    print("\n[+] Sincronizando Símbolos (.kicad_sym)...")
    sym_files = glob.glob(os.path.join(SYMBOL_DIR, "*.kicad_sym"))
    total_syms = 0
    for f in sym_files:
        added = parse_kicad_sym(f, conn)
        if added:
            total_syms += added
            print(f"  -> {Path(f).stem}: {added} componentes indexados.")
    print(f"[!] Total componentes indexados: {total_syms}")
    
    # 2. Sincronizar Huellas (Footprints)
    print("\n[+] Sincronizando Huellas (.pretty)...")
    pretty_dirs = glob.glob(os.path.join(FOOTPRINT_DIR, "*.pretty"))
    total_fps = 0
    for d in pretty_dirs:
        added = parse_kicad_footprints(d, conn)
        if added:
            total_fps += added
    print(f"[!] Total huellas indexadas: {total_fps}")
    
    conn.close()
    print(f"\n[+] Indexación completada. Base de datos lista para el Shadow Interrogator: {DB_PATH}")

if __name__ == "__main__":
    run_sync()
