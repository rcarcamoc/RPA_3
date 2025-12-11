# RPA Framework v2

Production-ready RPA framework with GUI recorder, player, and generators.

## Features

- 🎬 GUI Recording (mouse clicks, keyboard input)
- ▶️ Playback with retry logic
- 📄 Script generation
- 📦 Module generation
- 🔧 YAML configuration
- 🏗️ Modular architecture

## Quick Start

```bash
python main.py record --config config/ris_config.yaml
python main.py replay recordings/recording_*.json --config config/ris_config.yaml
python main.py generate-module recordings/recording_*.json --module-name "mi_modulo"
```

## Architecture

- `core/` - Action, Selector, Executor, Player, Recorder
- `utils/` - Logging, Config, Health Check
- `generators/` - Script and Module generators

## See also

- QUICK_START.md - Step by step guide
- RESUMEN_EJECUTIVO.md - Executive summary
- COMANDOS_COPYPASTE.md - Copy/paste commands
