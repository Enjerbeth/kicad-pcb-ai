import sys
import json
import math
import numpy as np
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

class SpatialPlacementEngine:
    """
    Motor de posicionamiento espacial y colisiones AABB vectorizado con NumPy.
    Evita llamadas repetitivas y bloqueos por la interfaz C++/SWIG de KiCad.
    """
    def __init__(self, board):
        self.board = board
        self.boxes = []
        self._sync_boxes()

    def _sync_boxes(self):
        self.boxes = []
        for fp in self.board.GetFootprints():
            ref = fp.GetReference()
            bbox = fp.GetBoundingBox()
            self.boxes.append((
                ref,
                bbox.GetX(),
                bbox.GetY(),
                bbox.GetX() + bbox.GetWidth(),
                bbox.GetY() + bbox.GetHeight()
            ))

    def update_box(self, ref, x_min, y_min, x_max, y_max):
        for i, b in enumerate(self.boxes):
            if b[0] == ref:
                self.boxes[i] = (ref, x_min, y_min, x_max, y_max)
                return
        self.boxes.append((ref, x_min, y_min, x_max, y_max))

    def check_collision_vectorized(self, target_ref, t_xmin, t_ymin, t_xmax, t_ymax):
        if not self.boxes:
            return False
        other_boxes = [b[1:] for b in self.boxes if b[0] != target_ref]
        if not other_boxes:
            return False
        arr = np.array(other_boxes, dtype=np.int64)
        
        # Solapamiento de rectángulos AABB en 2D
        overlap_x = (t_xmin < arr[:, 2]) & (t_xmax > arr[:, 0])
        overlap_y = (t_ymin < arr[:, 3]) & (t_ymax > arr[:, 1])
        return bool(np.any(overlap_x & overlap_y))

    def resolve_spiral(self, module, anchor_x_mm, anchor_y_mm, step_mm=1.27, max_attempts=150):
        ref = module.GetReference()
        step_iu = pcbnew.FromMM(step_mm)
        anchor_x_iu = pcbnew.FromMM(anchor_x_mm)
        anchor_y_iu = pcbnew.FromMM(anchor_y_mm)
        
        bbox = module.GetBoundingBox()
        w = bbox.GetWidth()
        h = bbox.GetHeight()
        
        # Paso dinámico adaptable al tamaño del footprint
        dyn_step = max(step_iu, min(w, h) // 4)
        
        pos = module.GetPosition()
        offset_x = bbox.GetX() - pos.x
        offset_y = bbox.GetY() - pos.y
        
        cur_x = anchor_x_iu
        cur_y = anchor_y_iu
        
        directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        dir_idx = 0
        segment_length = 1
        segment_passed = 0
        
        for _ in range(max_attempts):
            t_xmin = cur_x + offset_x
            t_ymin = cur_y + offset_y
            t_xmax = t_xmin + w
            t_ymax = t_ymin + h
            
            if not self.check_collision_vectorized(ref, t_xmin, t_ymin, t_xmax, t_ymax):
                final_pos = pcbnew.VECTOR2I(int(cur_x), int(cur_y))
                module.SetPosition(final_pos)
                self.update_box(ref, t_xmin, t_ymin, t_xmax, t_ymax)
                return True
                
            dx, dy = directions[dir_idx]
            cur_x += dx * dyn_step
            cur_y += dy * dyn_step
            
            segment_passed += 1
            if segment_passed == segment_length:
                segment_passed = 0
                dir_idx = (dir_idx + 1) % 4
                if dir_idx % 2 == 0:
                    segment_length += 1
                    
        module.SetPosition(pcbnew.VECTOR2I(int(cur_x), int(cur_y)))
        return False

def apply_layout_strategies(board, strategies, default_origin_x=100.0, default_origin_y=100.0):
    """
    Interpreta las directivas del LLM (grid, radial, absolute_cluster) y asigna coordenadas físicas.
    """
    engine = SpatialPlacementEngine(board)

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
            
            # Ejecutar posicionamiento con evasión de colisiones vectorizada
            success = engine.resolve_spiral(module, target_x_mm, target_y_mm)
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
