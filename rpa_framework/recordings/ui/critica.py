#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application
from core.executor import ActionExecutor
from core.action import Action, ActionType
from utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)

class CriticaAutomation:
    """Automatización simplificada: critica"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        
    def setup(self) -> bool:
        """Conecta a la aplicación de forma robusta."""
        try:
            # Título constante identificado por el usuario
            target_title = ".*Carestream RIS V11.*"
            try:
                logger.info(f"Conectando a {target_title}...")
                self.app = Application(backend='uia').connect(title_re=target_title, timeout=5)
            except:
                try:
                    # Fallback a búsqueda por ID de proceso o clase si el título falla temporalmente
                    self.app = Application(backend='uia').connect(path="Carestream RIS.exe")
                except:
                    logger.warning("No se pudo conectar, usando Desktop como root")
                    self.app = Application(backend='uia')
            
            self.executor = ActionExecutor(self.app, {})
            return True
        except Exception as e:
            logger.error(f"Error en setup: {e}")
            return False

    def _robust_execute(self, action: Action):
        """Asegura el foco del elemento antes de ejecutar la acción."""
        if action.selector and action.type in [ActionType.CLICK, ActionType.DOUBLE_CLICK]:
            try:
                element = self.executor.selector_helper.find_element(
                    action.selector, 
                    timeout=3
                )
                logger.debug(f"Forzando foco en elemento: {action.selector}")
                element.set_focus()
                time.sleep(0.3)
            except Exception as e:
                logger.debug(f"No se pudo dar foco previo: {e}")
        
        return self.executor.execute(action)

    def run(self):
        """Ejecuta los movimientos automatizados de forma robusta."""
        if not self.setup():
            return
            
        # Acción 1: CLICK en Carestream RIS (Asegurar foco y activación)
        self._robust_execute(Action(
            type=ActionType.CLICK,
            timestamp=datetime.now(),
            selector={
                'automation_id': 'RISShellView', 
                'title_re': '.*Carestream RIS V11.*'
            },
            position={'x': 824, 'y': 1066}
        ))
        time.sleep(1)

        # Acción 2: DOUBLE_CLICK en resultado critico (tabControl1)
        # Mover y esperar un instante para asegurar que el control está listo bajo el mouse
        self.executor.execute(Action(
            type=ActionType.MOVE,
            position={'x': 692, 'y': 84},
            timestamp=datetime.now()
        ))
        time.sleep(0.5)
        
        # Doble clic robusto. Si falla por selector, el nuevo fallback hará clic-pausa-clic.
        self._robust_execute(Action(
            type=ActionType.DOUBLE_CLICK,
            selector={'automation_id': 'tabControl1'},
            position={'x': 692, 'y': 84},
            timestamp=datetime.now()
        ))
        time.sleep(1)

        # Acción 3: CLICK en Abrir
        self._robust_execute(Action(
            type=ActionType.CLICK,
            timestamp=datetime.now(),
            selector={'name': 'Abrir', 'control_type': 'Button'},
            position={'x': 289, 'y': 130}
        ))
        time.sleep(1)

        # Acción 4, 5, 6: DOWN
        for _ in range(3):
            self.executor.execute(Action(
                type=ActionType.KEY_PRESS, 
                timestamp=datetime.now(),
                key_code="DOWN"
            ))
            time.sleep(0.5)


if __name__ == "__main__":
    setup_logging()
    CriticaAutomation().run()
