import sys
import json
import math
import pcbnew

def draw_board_outline(board, width_mm, height_mm, origin_x_mm=100.0, origin_y_mm=100.0):
    """
    Genera el contorno de la placa en la capa Edge.Cuts.
    """
    print(f"  -> Trazando Edge.Cuts: {width_mm}mm x {height_mm}mm")
    edges = [
        (0, 0, width_mm, 0),
        (width_mm, 0, width_mm, height_mm),
        (width_mm, height_mm, 0, height_mm),
        (0, height_mm, 0, 0)
    ]
    
    for x1, y1, x2, y2 in edges:
        segment = pcbnew.PCB_SHAPE(board)
        segment.SetShape(pcbnew.SHAPE_T_SEGMENT)
        segment.SetLayer(pcbnew.Edge_Cuts)
        segment.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(origin_x_mm + x1), pcbnew.FromMM(origin_y_mm + y1)))
        segment.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(origin_x_mm + x2), pcbnew.FromMM(origin_y_mm + y2)))
        segment.SetWidth(pcbnew.FromMM(0.1))
        board.Add(segment)

def resolve_collision_spiral(board, module, anchor_x_mm, anchor_y_mm, step_mm=1.27, max_attempts=100):
    """
    Algoritmo de Espiral Cuadrada determinista usando Bounding Boxes.
    Evita que las huellas colisionen buscando el espacio libre más cercano al ancla.
    """
    step_iu = pcbnew.FromMM(step_mm)
    anchor_pos = pcbnew.VECTOR2I(pcbnew.FromMM(anchor_x_mm), pcbnew.FromMM(anchor_y_mm))
    
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    dir_idx = 0
    segment_length = 1
    segment_passed = 0
    
    current_pos = pcbnew.VECTOR2I(anchor_pos.x, anchor_pos.y)
    module.SetPosition(current_pos)
    
    for attempt in range(max_attempts):
        collision = False
        module_box = module.GetBoundingBox()
        
        for other_module in board.GetFootprints():
            if other_module.GetReference() == module.GetReference():
                continue
            if other_module.GetBoundingBox().Intersects(module_box):
                collision = True
                break
                
        if not collision:
            return True 
            
        dx, dy = directions[dir_idx]
        current_pos = pcbnew.VECTOR2I(current_pos.x + (dx * step_iu), current_pos.y + (dy * step_iu))
        module.SetPosition(current_pos)
        
        segment_passed += 1
        if segment_passed == segment_length:
            segment_passed = 0
            dir_idx = (dir_idx + 1) % 4
            if dir_idx % 2 == 0:
                segment_length += 1
                
    return False

def apply_layout_strategies(board, strategies, default_origin_x=100.0, default_origin_y=100.0):
    """
    Interpreta las directivas del LLM (grid, radial, absolute_cluster) y asigna coordenadas físicas.
    """
    for strategy in strategies:
        strat_type = strategy.get("strategy_type")
        targets = strategy.get("target_refs", [])
        params = strategy.get("parameters", {})
        
        print(f"  -> Aplicando estrategia '{strat_type}' a {len(targets)} componentes.")
        
        for idx, ref in enumerate(targets):
            module = board.FindFootprintByReference(ref)
            if not module:
                print(f"     [!] Advertencia: Huella {ref} no encontrada en la placa.")
                continue
                
            target_x_mm = default_origin_x
            target_y_mm = default_origin_y
            rotation_deg = 0.0

            if strat_type == "grid":
                cols = params.get("cols", 1)
                spacing_x = params.get("spacing_x", 0.0)
                spacing_y = params.get("spacing_y", 0.0)
                rotation_deg = params.get("rotation_deg", 0.0)
                
                row = idx // cols
                col = idx % cols
                target_x_mm += (col * spacing_x)
                target_y_mm += (row * spacing_y)
                
            elif strat_type == "radial":
                radius = params.get("radius", 10.0)
                start_angle = params.get("start_angle", 0.0)
                sweep_angle = params.get("sweep_angle", 360.0)
                
                delta = sweep_angle / len(targets) if len(targets) > 1 else 0
                angle_deg = start_angle + (idx * delta)
                angle_rad = math.radians(angle_deg)
                
                target_x_mm += (radius * math.cos(angle_rad))
                target_y_mm += (radius * math.sin(angle_rad))
                rotation_deg = angle_deg + 90.0 # Orientación hacia el exterior
                
            elif strat_type == "absolute_cluster":
                positions = params.get("positions", [])
                if idx < len(positions):
                    pos = positions[idx]
                    target_x_mm += pos.get("dx", 0.0)
                    target_y_mm += pos.get("dy", 0.0)
                    rotation_deg = pos.get("rotation", 0.0)

            # Establecer rotación antes del motor de colisión para que el Bounding Box sea preciso
            module.SetOrientation(pcbnew.EDA_ANGLE(rotation_deg, pcbnew.DEGREES_T))
            
            # Ejecutar posicionamiento con evasión de colisiones
            success = resolve_collision_spiral(board, module, target_x_mm, target_y_mm)
            if not success:
                print(f"     [!] Colisión irresoluble para {ref} tras agotar la espiral.")

def route_basic_differential_pairs(board, diff_pairs):
    """
    Ruteo punto a punto básico simétrico (línea recta) para Pares Diferenciales.
    Esta función fija la impedancia base bloqueando las trazas antes de Freerouting.
    """
    for dp in diff_pairs:
        net_p_name = dp.get("net_p")
        net_n_name = dp.get("net_n")
        
        net_p = board.FindNet(net_p_name)
        net_n = board.FindNet(net_n_name)
        
        if not net_p or not net_n:
            continue
            
        print(f"  -> Ruteando Par Diferencial: {net_p_name} / {net_n_name}")
        
        # Lógica de ruteo simplificada: Obtener los pads asociados y trazar pista directa.
        # Para hardware de producción real, este bloque evolucionará para calcular vías y obstáculos.
        pads_p = board.GetConnectivity().GetConnectedPads(net_p)
        pads_n = board.GetConnectivity().GetConnectedPads(net_n)
        
        if len(pads_p) >= 2 and len(pads_n) >= 2:
            track_p = pcbnew.PCB_TRACK(board)
            track_p.SetStart(pads_p[0].GetPosition())
            track_p.SetEnd(pads_p[1].GetPosition())
            track_p.SetWidth(pcbnew.FromMM(0.2))
            track_p.SetLayer(pcbnew.F_Cu)
            track_p.SetNetCode(net_p.GetNetCode())
            track_p.SetLocked(True) # Bloquear para proteger de Freerouting
            board.Add(track_p)
            
            track_n = pcbnew.PCB_TRACK(board)
            track_n.SetStart(pads_n[0].GetPosition())
            track_n.SetEnd(pads_n[1].GetPosition())
            track_n.SetWidth(pcbnew.FromMM(0.2))
            track_n.SetLayer(pcbnew.F_Cu)
            track_n.SetNetCode(net_n.GetNetCode())
            track_n.SetLocked(True)
            board.Add(track_n)

def main():
    if len(sys.argv) < 2:
        print("Uso: python aero_pcb_macro.py <layout_config.json>")
        sys.exit(1)
        
    config_path = sys.argv[1]
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    board_path = config.get("pcb_file")
    if not board_path:
        print("Error: pcb_file no especificado en la configuración.")
        sys.exit(1)
        
    print(f"[*] Cargando placa: {board_path}")
    board = pcbnew.LoadBoard(board_path)
    
    outline = config.get("board_outline", {})
    draw_board_outline(board, outline.get("width", 50.0), outline.get("height", 50.0))
    
    apply_layout_strategies(board, config.get("layout_strategies", []))
    route_basic_differential_pairs(board, config.get("differential_pairs", []))
    
    pcbnew.SaveBoard(board_path, board)
    print(f"[+] Placa guardada exitosamente. Lista para Freerouting.")

if __name__ == "__main__":
    main()
