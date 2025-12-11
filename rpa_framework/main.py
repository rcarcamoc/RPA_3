#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RPA Framework v2 - CLI Principal."""

import sys
import argparse
from pathlib import Path

from core.recorder import RecorderGUI
from core.player import RecordingPlayer
from generators.script_generator import QuickScriptGenerator
from generators.module_generator import ModuleGenerator
from utils.config_loader import load_config
from utils.logging_setup import setup_logging

def cmd_record(args):
    setup_logging(level=args.log_level)
    config = load_config(args.config)
    gui = RecorderGUI(config=config)
    gui.run()

def cmd_replay(args):
    setup_logging(level=args.log_level)
    config = load_config(args.config)
    player = RecordingPlayer(args.recording, config)
    results = player.run()
    
    import json
    with open(f"replay_report_{results['session_id']}.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return 0 if results["status"] == "SUCCESS" else 1

def cmd_generate_script(args):
    setup_logging(level=args.log_level)
    gen = QuickScriptGenerator(args.recording)
    output = gen.generate(args.output)
    print(f"Script generado: {output}")

def cmd_generate_module(args):
    setup_logging(level=args.log_level)
    config = load_config(args.config)
    gen = ModuleGenerator(args.recording, args.module_name, config)
    module_dir = gen.generate()
    print(f"Módulo generado: {module_dir}")

def main():
    parser = argparse.ArgumentParser(
        description="RPA Framework v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--config", default="config/ris_config.yaml")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    subparsers = parser.add_subparsers(dest="command")
    
    sp_record = subparsers.add_parser("record", help="Grabar")
    sp_replay = subparsers.add_parser("replay", help="Reproducir")
    sp_replay.add_argument("recording")
    sp_gen_script = subparsers.add_parser("generate-script", help="Generar script")
    sp_gen_script.add_argument("recording")
    sp_gen_script.add_argument("-o", "--output")
    sp_gen_module = subparsers.add_parser("generate-module", help="Generar módulo")
    sp_gen_module.add_argument("recording")
    sp_gen_module.add_argument("-m", "--module-name", required=True)
    
    args = parser.parse_args()
    
    if args.command == "record":
        return cmd_record(args) or 0
    elif args.command == "replay":
        return cmd_replay(args)
    elif args.command == "generate-script":
        return cmd_generate_script(args) or 0
    elif args.command == "generate-module":
        return cmd_generate_module(args) or 0
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
