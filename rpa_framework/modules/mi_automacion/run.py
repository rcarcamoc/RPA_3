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
    "created_at": "2025-12-21T18:04:37.716586",
    "screen_resolution": {
      "width": 1920,
      "height": 1080
    },
    "total_actions": 9,
    "total_actions_optimized": 9,
    "duration_seconds": 25.565946,
    "optimization_stats": {
      "removed_count": 0,
      "consolidated_count": 0
    }
  },
  "actions": [
    {
      "type": "click",
      "timestamp": "2025-12-21T18:04:06.768081",
      "position": {
        "x": 1916,
        "y": 1053
      },
      "selector": {
        "automation_id": "SystemTrayIcon"
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
        "name": "Mostrar escritorio",
        "automation_id": "SystemTrayIcon",
        "class_name": "SystemTray.ShowDesktopButton",
        "control_type": "Button"
      }
    },
    {
      "type": "click",
      "timestamp": "2025-12-21T18:04:11.845930",
      "position": {
        "x": 52,
        "y": 791
      },
      "selector": {
        "name": "PACS INTEGRA VPN",
        "control_type": "ListItem"
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
        "name": "PACS INTEGRA VPN",
        "automation_id": "",
        "class_name": "",
        "control_type": "ListItem"
      }
    },
    {
      "type": "click",
      "timestamp": "2025-12-21T18:04:12.060184",
      "position": {
        "x": 52,
        "y": 791
      },
      "selector": {
        "name": "PACS INTEGRA VPN",
        "control_type": "ListItem"
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
        "name": "PACS INTEGRA VPN",
        "automation_id": "",
        "class_name": "",
        "control_type": "ListItem"
      }
    },
    {
      "type": "click",
      "timestamp": "2025-12-21T18:04:22.951877",
      "position": {
        "x": 1094,
        "y": 430
      },
      "selector": {
        "automation_id": "txtUsername"
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
        "automation_id": "txtUsername",
        "class_name": "WindowsForms10.EDIT.app.0.297b065_r29_ad1",
        "control_type": "Edit"
      }
    },
    {
      "type": "type_text",
      "timestamp": "2025-12-21T18:04:25.678048",
      "text": "hadhasjda",
      "selector": {
        "automation_id": "txtUsername"
      },
      "position": null
    },
    {
      "type": "click",
      "timestamp": "2025-12-21T18:04:25.719774",
      "position": {
        "x": 1082,
        "y": 470
      },
      "selector": {
        "automation_id": "txtPassword"
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
        "automation_id": "txtPassword",
        "class_name": "WindowsForms10.EDIT.app.0.297b065_r29_ad1",
        "control_type": "Edit"
      }
    },
    {
      "type": "type_text",
      "timestamp": "2025-12-21T18:04:28.939871",
      "text": "asdhsadjsao",
      "selector": {
        "automation_id": "txtPassword"
      },
      "position": null
    },
    {
      "type": "click",
      "timestamp": "2025-12-21T18:04:30.351224",
      "position": {
        "x": 816,
        "y": 959
      },
      "selector": {
        "name": "🎬 RPA Recorder v2: 2 ventanas en ejecución",
        "control_type": "Group"
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
        "name": "🎬 RPA Recorder v2: 2 ventanas en ejecución",
        "automation_id": "",
        "class_name": "NamedContainerAutomationPeer",
        "control_type": "Group"
      }
    },
    {
      "type": "click",
      "timestamp": "2025-12-21T18:04:32.334027",
      "position": {
        "x": 310,
        "y": 210
      },
      "selector": {
        "position": {
          "x": 310,
          "y": 210
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
        
    print("🚀 Ejecutando módulo independiente: mi_automacion")
    
    # Parsear datos incrustados
    recording_data = json.loads(RECORDING_JSON)
    
    # Instanciar player con diccionario de datos
    player = RecordingPlayer(recording_data, config)
    
    results = player.run()
    print(results)
