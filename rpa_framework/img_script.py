#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Auto-generated script."""

import json
from pathlib import Path
from core.player import RecordingPlayer
from utils.config_loader import load_config
from utils.logging_setup import setup_logging

if __name__ == "__main__":
    setup_logging()
    config = load_config("config/ris_config.yaml")
    player = RecordingPlayer("recordings\img.json", config)
    results = player.run()
    print(results)
