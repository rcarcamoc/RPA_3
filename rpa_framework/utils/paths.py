"""
Path management utilities for RPA Framework.

This module centralizes all output paths to ensure consistency
across the application.
"""

from pathlib import Path
from typing import Optional


# Base directories - anchored to package location
BASE_DIR = Path(__file__).resolve().parent.parent
RECORDINGS_DIR = BASE_DIR / "recordings"

# Legacy directories (root of project)
LEGACY_ROOT = Path.cwd()
LEGACY_RECORDINGS_DIR = LEGACY_ROOT / "recordings"
LEGACY_MODULES_DIR = LEGACY_ROOT / "modules"

# Recording subdirectories
UI_RECORDINGS_DIR = RECORDINGS_DIR / "ui"
WEB_RECORDINGS_DIR = RECORDINGS_DIR / "web"
OCR_RECORDINGS_DIR = RECORDINGS_DIR / "ocr"
WORKFLOWS_DIR = BASE_DIR / "workflows"

# Other directories
SCRIPTS_DIR = BASE_DIR / "scripts"
QUICK_SCRIPTS_DIR = BASE_DIR / "quick_scripts"
MODULES_DIR = BASE_DIR / "modules"
LOGS_DIR = BASE_DIR / "logs"


def ensure_directories():
    """Create all required directories if they don't exist."""
    directories = [
        RECORDINGS_DIR,
        UI_RECORDINGS_DIR,
        WEB_RECORDINGS_DIR,
        OCR_RECORDINGS_DIR,
        WORKFLOWS_DIR,
        SCRIPTS_DIR,
        QUICK_SCRIPTS_DIR,
        MODULES_DIR,
        LOGS_DIR
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def get_ui_recording_path(filename: str) -> Path:
    """Get full path for a UI recording file."""
    UI_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return UI_RECORDINGS_DIR / filename


def get_web_recording_path(filename: str) -> Path:
    """Get full path for a web recording file."""
    WEB_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return WEB_RECORDINGS_DIR / filename


def get_ocr_module_path(filename: str) -> Path:
    """Get full path for an OCR module file."""
    OCR_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return OCR_RECORDINGS_DIR / filename


def get_workflow_path(filename: str) -> Path:
    """Get full path for a workflow file."""
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    return WORKFLOWS_DIR / filename


def get_all_scripts(include_subdirs: bool = True) -> list[Path]:
    """
    Get all Python scripts from recordings and scripts directories,
    including legacy locations.
    """
    scripts = []
    
    # 1. Scripts directory (standard)
    if SCRIPTS_DIR.exists():
        scripts.extend(SCRIPTS_DIR.glob("*.py"))
        
    # 2. Quick Scripts
    if QUICK_SCRIPTS_DIR.exists():
        scripts.extend(QUICK_SCRIPTS_DIR.glob("*.py"))
    
    if include_subdirs:
        # Search in all recordings subdirectories (New Structure)
        for subdir in [UI_RECORDINGS_DIR, WEB_RECORDINGS_DIR, OCR_RECORDINGS_DIR]:
            if subdir.exists():
                scripts.extend(subdir.glob("**/*.py"))
        
        # Modules directory (Standard)
        if MODULES_DIR.exists():
            scripts.extend(MODULES_DIR.glob("**/*.py"))
            
        # Legacy Modules (Root)
        if LEGACY_MODULES_DIR.exists() and LEGACY_MODULES_DIR != MODULES_DIR:
             scripts.extend(LEGACY_MODULES_DIR.glob("**/*.py"))
             
    else:
        # Legacy: only top-level recordings (Standard)
        if RECORDINGS_DIR.exists():
            scripts.extend(RECORDINGS_DIR.glob("*.py"))
            
        # Legacy Recordings (Root)
        if LEGACY_RECORDINGS_DIR.exists() and LEGACY_RECORDINGS_DIR != RECORDINGS_DIR:
             scripts.extend(LEGACY_RECORDINGS_DIR.glob("*.py"))
    
    # Deduplicate by path
    unique_scripts = {str(p.resolve()): p for p in scripts}
    
    return sorted(unique_scripts.values(), key=lambda p: p.stat().st_mtime, reverse=True)


def get_all_recordings(recording_type: Optional[str] = None) -> list[Path]:
    """Get all JSON and Python recording files, recursively."""
    recordings = []
    
    # helper to scan a dir recursively for both formats
    def scan_dir_recursive(d):
        if d.exists():
            # Buscamos JSON (datos) y PY (scripts autogenerados)
            recordings.extend(d.rglob("*.json"))
            recordings.extend(d.rglob("*.py"))

    if recording_type == 'ui':
        scan_dir_recursive(UI_RECORDINGS_DIR)
    elif recording_type == 'web':
        scan_dir_recursive(WEB_RECORDINGS_DIR)
    else:
        # Search everything in the main recordings folder
        scan_dir_recursive(RECORDINGS_DIR)
            
    # Legacy Support
    if LEGACY_RECORDINGS_DIR.exists() and LEGACY_RECORDINGS_DIR.resolve() != RECORDINGS_DIR.resolve():
         scan_dir_recursive(LEGACY_RECORDINGS_DIR)
    
    # Deduplicate and sort by modification time
    unique_recs = {str(p.resolve()): p for p in recordings}
    
    return sorted(unique_recs.values(), key=lambda p: p.stat().st_mtime, reverse=True)


def get_all_json_recordings(recording_type: Optional[str] = None) -> list[Path]:
    """Get only JSON recording files (backward compatibility)."""
    all_recs = get_all_recordings(recording_type)
    return [p for p in all_recs if p.suffix.lower() == ".json"]


# Initialize directories on import
ensure_directories()
