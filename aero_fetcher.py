import os
import sys
import urllib.request
import zipfile
import shutil

# Rutas estándar
CUSTOM_LIBS_DIR = "aero_custom_libs"
SYMBOLS_DIR = os.path.join(CUSTOM_LIBS_DIR, "symbols")
FOOTPRINTS_DIR = os.path.join(CUSTOM_LIBS_DIR, "footprints.pretty")

def setup_directories():
    """Crea los directorios necesarios para las librerías custom de KiCad."""
    os.makedirs(SYMBOLS_DIR, exist_ok=True)
    os.makedirs(FOOTPRINTS_DIR, exist_ok=True)

def download_file(url, destination):
    """Descarga un archivo genérico desde una URL."""
    try:
        print(f"[*] Descargando desde: {url}")
        urllib.request.urlretrieve(url, destination)
        print(f"[+] Archivo guardado en: {destination}")
        return True
    except Exception as e:
        print(f"[-] Error descargando el archivo: {e}")
        return False

def extract_and_organize(zip_path):
    """Extrae un ZIP y mueve archivos .kicad_sym y .kicad_mod a sus directorios correspondientes."""
    extract_dir = os.path.join(CUSTOM_LIBS_DIR, "temp_extract")
    os.makedirs(extract_dir, exist_ok=True)
    
    print("[*] Extrayendo archivos...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        
    for root, _, files in os.walk(extract_dir):
        for file in files:
            source_path = os.path.join(root, file)
            if file.endswith(".kicad_sym"):
                shutil.move(source_path, os.path.join(SYMBOLS_DIR, file))
                print(f"  -> Símbolo importado: {file}")
            elif file.endswith(".kicad_mod"):
                shutil.move(source_path, os.path.join(FOOTPRINTS_DIR, file))
                print(f"  -> Huella importada: {file}")

    shutil.rmtree(extract_dir)
    os.remove(zip_path)
    print("[+] Limpieza de archivos temporales completada.")

def print_help():
    print("AERO Fetcher - Herramienta de inyección dinámica de librerías para KiCad 8")
    print("Uso:")
    print("  python aero_fetcher.py [URL_DEL_ZIP_O_RAW_FILE]")
    print("El archivo se descargará, extraerá (si es ZIP) e inyectará en aero_custom_libs.")
    print("Posteriormente debes ejecutar: python sync_kicad_libs.py")

if __name__ == "__main__":
    setup_directories()
    
    if len(sys.sys.argv) < 2:
        print_help()
        sys.exit(1)
        
    url = sys.argv[1]
    
    # Determinar nombre del archivo
    filename = url.split("/")[-1]
    if not filename:
        filename = "downloaded_lib.zip"
        
    dest_path = os.path.join(CUSTOM_LIBS_DIR, filename)
    
    if download_file(url, dest_path):
        if dest_path.endswith(".zip"):
            extract_and_organize(dest_path)
        elif dest_path.endswith(".kicad_sym"):
            shutil.move(dest_path, os.path.join(SYMBOLS_DIR, filename))
        elif dest_path.endswith(".kicad_mod"):
            shutil.move(dest_path, os.path.join(FOOTPRINTS_DIR, filename))
            
        print("\n[!] Proceso finalizado. RECUERDA: Ejecuta 'python sync_kicad_libs.py' para actualizar la base de datos.")
