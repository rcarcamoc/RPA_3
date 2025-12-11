#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Module runner (Standalone)."""

import sys
import json
from pathlib import Path

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.player import RecordingPlayer
from utils.config_loader import load_config
from utils.logging_setup import setup_logging

# DATOS DE LA GRABACIÓN (INCRUSTADOS)
RECORDING_JSON = r"""
{
  "metadata": {
    "created_at": "2025-12-11T00:55:12.660997",
    "screen_resolution": {
      "width": 1920,
      "height": 1080
    },
    "total_actions": 4,
    "total_actions_optimized": 4,
    "duration_seconds": 14.166707,
    "optimization_stats": {
      "removed_count": 0,
      "consolidated_count": 0
    }
  },
  "actions": [
    {
      "type": "click",
      "timestamp": "2025-12-11T00:54:54.624130",
      "position": {
        "x": -1893,
        "y": 1005
      },
      "selector": {
        "automation_id": "StartButton"
      },
      "app_context": {
        "title": "Desktop",
        "class_name": "#32769"
      },
      "modifiers": {
        "ctrl": false,
        "shift": false,
        "alt": false
      },
      "element_info": {
        "name": "Inicio",
        "automation_id": "StartButton",
        "class_name": "ToggleButton",
        "control_type": "Button"
      }
    },
    {
      "type": "click",
      "timestamp": "2025-12-11T00:54:56.822911",
      "position": {
        "x": -1346,
        "y": 518
      },
      "selector": {
        "automation_id": "tile-W~Microsoft.Windows.Explorer"
      },
      "app_context": {
        "title": "Desktop",
        "class_name": "#32769"
      },
      "modifiers": {
        "ctrl": false,
        "shift": false,
        "alt": false
      },
      "element_info": {
        "name": "Explorador de archivos",
        "automation_id": "tile-W~Microsoft.Windows.Explorer",
        "class_name": "GridViewItem",
        "control_type": "ListItem"
      }
    },
    {
      "type": "click",
      "timestamp": "2025-12-11T00:55:04.488853",
      "position": {
        "x": -1115,
        "y": 506
      },
      "selector": {
        "name": "Panel de navegación",
        "control_type": "Tree"
      },
      "app_context": {
        "title": "Desktop",
        "class_name": "#32769"
      },
      "modifiers": {
        "ctrl": false,
        "shift": false,
        "alt": false
      },
      "element_info": {
        "name": "Panel de navegación",
        "automation_id": "100",
        "class_name": "SysTreeView32",
        "control_type": "Tree"
      }
    },
    {
      "type": "click",
      "timestamp": "2025-12-11T00:55:08.790837",
      "position": {
        "x": 769,
        "y": 334
      },
      "selector": {
        "position": {
          "x": 769,
          "y": 334
        }
      },
      "app_context": {
        "title": "Desktop",
        "class_name": "#32769"
      },
      "modifiers": {
        "ctrl": false,
        "shift": false,
        "alt": false
      },
      "element_info": {
        "name": "",
        "automation_id": "",
        "class_name": "Button",
        "control_type": "Button"
      }
    }
  ]
}
"""

if __name__ == "__main__":
    setup_logging()
    
    # Cargar configuración (puede ser externa o default)
    try:
        config = load_config("../../config/ris_config.yaml")
    except:
        config = {}
        
    print("🚀 Ejecutando módulo independiente: test2")
    
    # Parsear datos incrustados
    recording_data = json.loads(RECORDING_JSON)
    
    # Instanciar player con diccionario de datos
    player = RecordingPlayer(recording_data, config)
    
    results = player.run()
    print(results)
