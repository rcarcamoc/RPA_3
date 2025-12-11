"""WindowsSelector - Búsqueda con fallback chain."""
import logging
from typing import Dict, Optional, Tuple
from pywinauto import Desktop
from pywinauto.findwindows import ElementNotFoundError

logger = logging.getLogger(__name__)

class SelectorStrategy:
    """Strategy pattern para selectores."""
    
    @staticmethod
    def by_automation_id(automation_id: str) -> Dict:
        return {"automation_id": automation_id}
    
    @staticmethod
    def by_name_and_controltype(name: str, control_type: str) -> Dict:
        return {"name": name, "control_type": control_type}
    
    @staticmethod
    def by_classname_and_title(classname: str, title_regex: str) -> Dict:
        return {"classname": classname, "title_regex": title_regex}
    
    @staticmethod
    def by_position(x: int, y: int) -> Dict:
        return {"position": (x, y)}

class WindowsSelector:
    """Encuentra elementos con fallback chain y retry."""
    
    FALLBACK_CHAIN = [
        "automation_id",
        "name_and_controltype",
        "classname_and_title",
        "position"
    ]
    
    def __init__(self, app_context: str = "unknown", max_retries: int = 2, app=None):
        self.app_context = app_context
        self.max_retries = max_retries
        self.root = app if app else Desktop(backend='uia')
    
    @staticmethod
    def extract_from_point(x: int, y: int) -> Dict:
        """Extrae propiedades de elemento en (x, y) buscando el mejor candidato y su contexto de app."""
        try:
            desktop = Desktop(backend='uia')
            element = desktop.from_point(x, y)
            
            # 1. Identificar Ventana Principal (App Context)
            try:
                top_level = element.top_level_parent()
                window_title = top_level.element_info.name or ""
                window_class = top_level.element_info.class_name or ""
            except:
                window_title = "Desktop"
                window_class = "#32769" # Standard desktop class

            # 2. Heurística: Si el elemento es muy genérico (ej. Text sin ID), buscar padre interactivo
            original_element = element
            candidate = element
            
            for _ in range(3): # Subir max 3 niveles
                info = candidate.element_info
                
                # Criterios de "Buen Candidato"
                has_id = bool(info.automation_id)
                is_interactive = info.control_type in ["Button", "ListItem", "MenuItem", "CheckBox", "RadioButton", "Hyperlink", "Edit", "Pane"]
                has_name = bool(info.name)
                
                if has_id or (is_interactive and has_name):
                    element = candidate
                    break
                    
                # Si no es bueno, intentar padre
                try:
                    parent = candidate.parent()
                    if not parent: break
                    candidate = parent
                except:
                    break
            
            # Extraer info del ganador
            info = element.element_info
            
            return {
                "name": info.name or "",
                "automation_id": info.automation_id or "",
                "class_name": info.class_name or "",
                "control_type": info.control_type or "",
                "found_index": 0,
                "parent_control": candidate.parent().element_info.control_type if candidate.parent() else "",
                # Contexto de App
                "window_title": window_title,
                "window_class": window_class
            }
            
        except Exception as e:
            logger.warning(f"No se pudo extraer elemento en ({x}, {y}): {e}")
            return {}
    
    def build_selector(self, element_info: Dict, position: Tuple[int, int]) -> Dict:
        """Construye selector priorizado con validación de calidad."""
        selector = {}
        
        # Helper para detectar IDs generados (números puros)
        def is_generated_id(aid):
            return aid.isdigit() or (len(aid) < 3)

        auto_id = element_info.get("automation_id", "")
        name = element_info.get("name", "")
        control_type = element_info.get("control_type", "")
        class_name = element_info.get("class_name", "")

        # 1. Name + ControlType (Prioridad si ID es malo o no existe)
        # Preferir nombre si el ID parece autogenerado ("100") y el nombre es legible ("Guardar")
        if name and control_type:
            if not auto_id or (is_generated_id(auto_id) and len(name) > 1):
                selector["name"] = name
                selector["control_type"] = control_type
                logger.debug(f"Selector: name + control_type (ID débil o ausente)")
                return selector

        # 2. Automation ID (Prioridad estándar)
        if auto_id:
            selector["automation_id"] = auto_id
            logger.debug(f"Selector: automation_id")
            return selector
        
        # 3. Class Name (Solo si es específica)
        GENERIC_CLASSES = ["Button", "Pane", "Window", "Group", "Text", "Image", "Static", "Edit"]
        if class_name and class_name not in GENERIC_CLASSES:
            selector["class_name"] = class_name
            logger.debug(f"Selector: class_name (Específico: {class_name})")
            return selector
        
        # 4. Fallback Position
        selector["position"] = position
        logger.debug(f"Selector: position (fallback)")
        return selector
    
    def find_element(self, selector: Dict, timeout: float = 5.0, app_context: Optional[Dict] = None):
        """Busca elemento con retry, usando contexto de app si existe."""
        for attempt in range(1, self.max_retries + 1):
            try:
                # 1. Resolver Parent (Ventana)
                parent = self.root
                if app_context and (app_context.get("title") or app_context.get("class_name")):
                    # Intentar encontrar la ventana padre específica
                    try:
                        kwargs = {}
                        if app_context.get("title") and app_context["title"] != "Desktop":
                            kwargs["title"] = app_context["title"]
                        if app_context.get("class_name"):
                             kwargs["class_name"] = app_context["class_name"]
                        
                        if kwargs:
                            logger.debug(f"Buscando ventana padre: {kwargs}")
                            parent = self.root.window(**kwargs)
                            # Verificar que existe (rápido)
                            parent.wait("exists", timeout=1)
                    except:
                        # Si falla, usar root (Desktop/App global)
                        parent = self.root

                # 2. Convertir selector a kwargs de pywinauto
                kwargs = {}
                if "automation_id" in selector:
                    kwargs["auto_id"] = selector["automation_id"]
                elif "name" in selector and "control_type" in selector:
                    kwargs["title"] = selector["name"]
                    kwargs["control_type"] = selector["control_type"]
                elif "class_name" in selector:
                    kwargs["class_name"] = selector["class_name"]
                elif "position" in selector:
                    # Posición es caso especial
                    pos_data = selector["position"]
                    if isinstance(pos_data, dict):
                         x = int(pos_data["x"])
                         y = int(pos_data["y"])
                    else:
                         # Asumir tupla/lista
                         x, y = int(pos_data[0]), int(pos_data[1])
                         
                    from pywinauto import Desktop
                    element = Desktop(backend='uia').from_point(x, y)
                    # wait visible might fail if element is virtual or under mouse
                    # element.wait("visible", timeout=timeout) 
                    # from_point returns element immediately. check if exists?
                    logger.info(f"Elemento encontrado por posición ({x}, {y})")
                    return element
                else:
                    raise ValueError(f"Selector no reconocido: {selector}")
                
                # 3. Buscar elemento (child_window si tenemos parent específico, o window si es root)
                if parent != self.root:
                    element = parent.child_window(**kwargs)
                else:
                    # Si estamos en root, child_window busca en todo? No siempre.
                    # window() busca top-level. 
                    # Si buscamos un control hijo sin padre, necesitamos descendants o child_window sobre el root?
                    # Desktop.child_window no existe.
                    # Pero Application.window(...).child_window(...) sí.
                    # Si falla parent, intentamos buscar como ventana top level
                    element = self.root.window(**kwargs)

                element.wait("visible", timeout=timeout)
                logger.info(f"Elemento encontrado: {selector}")
                return element
                
            except Exception as e:
                logger.warning(f"Intento {attempt}/{self.max_retries} fallido: {e}")
                if attempt == self.max_retries:
                    logger.error(f"No se pudo encontrar elemento: {selector}")
                    raise
                import time
                time.sleep(0.5)
