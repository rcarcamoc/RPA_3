"""
Generador de reporte de tiempos y desviaciones por fase para workflows RPA (Sub_work / RIS / pacs).

Uso:
    python rpa_framework/scripts/reporte_tiempos.py
    python rpa_framework/scripts/reporte_tiempos.py --output rpa_framework/logs/reporte_tiempos.md
"""

import argparse
import glob
import os
import re
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Tuple


TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
NODE_RE = re.compile(r"Nodo actual: (.+?) \((action|workflow|start|end)\)")


def format_duration(seconds: float) -> str:
    """Formatea segundos a una cadena legible (Xm Ys o Zs)."""
    secs = int(round(seconds))
    if secs >= 60:
        mins, rem = divmod(secs, 60)
        return f"{mins}m {rem:02d}s ({seconds:.0f}s)"
    return f"{seconds:.1f}s" if seconds % 1 else f"{secs}s"


def parse_log_file(fpath: str) -> dict:
    """Extrae ejecuciones de Sub_work, RIS, pacs y duraciones por nodo de un archivo de log."""
    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    subwork_runs: List[Tuple[datetime, float]] = []
    ris_runs: List[Tuple[datetime, float]] = []
    pacs_runs: List[Tuple[datetime, float]] = []
    node_runs: Dict[Tuple[str, str], List[Tuple[datetime, float]]] = {}

    last_ts: Optional[datetime] = None
    subwork_start: Optional[datetime] = None
    ris_start: Optional[datetime] = None
    pacs_start: Optional[datetime] = None
    current_wf: Optional[str] = None
    current_node: Optional[str] = None
    node_start: Optional[datetime] = None

    def close_node(ts: datetime) -> None:
        nonlocal current_node, node_start
        if current_node and node_start and current_wf in ("RIS", "pacs"):
            dur = (ts - node_start).total_seconds()
            if 0 <= dur < 3600:
                node_runs.setdefault((current_wf, current_node), []).append((node_start, dur))
        current_node = None
        node_start = None

    for line in lines:
        m = TS_RE.match(line)
        if m:
            last_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        if not last_ts:
            continue

        if "Iniciando ejecución: Sub_work" in line:
            subwork_start = last_ts
            current_wf = "Sub_work"
        elif "Iniciando ejecución: RIS" in line:
            ris_start = last_ts
            current_wf = "RIS"
            current_node = None
            node_start = None
        elif "Iniciando ejecución: pacs" in line:
            pacs_start = last_ts
            current_wf = "pacs"
            current_node = None
            node_start = None
        elif "Nodo actual:" in line:
            nm = NODE_RE.search(line)
            if nm:
                node_name, node_type = nm.group(1).strip(), nm.group(2)
                if node_type == "action":
                    close_node(last_ts)
                    current_node = node_name
                    node_start = last_ts
                elif node_type == "end":
                    close_node(last_ts)
        elif "Ejecución completada:" in line:
            status = line.split("Ejecución completada:")[-1].strip()
            if "[WF:RIS]" in line and ris_start:
                close_node(last_ts)
                dur = (last_ts - ris_start).total_seconds()
                if status == "success" and 0 <= dur < 3600:
                    ris_runs.append((ris_start, dur))
                ris_start = None
                current_wf = "Sub_work"
            elif "[WF:pacs]" in line and pacs_start:
                close_node(last_ts)
                dur = (last_ts - pacs_start).total_seconds()
                if status == "success" and 0 <= dur < 3600:
                    pacs_runs.append((pacs_start, dur))
                pacs_start = None
                current_wf = "Sub_work"
            elif "[WF:" not in line and subwork_start:
                dur = (last_ts - subwork_start).total_seconds()
                if status == "success" and 0 <= dur < 3600:
                    subwork_runs.append((subwork_start, dur))
                subwork_start = None
                current_wf = None

    return {
        "file": fpath,
        "subwork": subwork_runs,
        "ris": ris_runs,
        "pacs": pacs_runs,
        "nodes": node_runs,
    }


def classify_deviation(last_val: float, mean_val: float, stdev_val: float) -> Tuple[str, float]:
    """Clasifica la desviación respecto al promedio histórico usando Z-score."""
    if stdev_val <= 0:
        return "NORMAL", 0.0
    z = (last_val - mean_val) / stdev_val
    abs_z = abs(z)
    if abs_z >= 2.0:
        label = "⚠️ ALTA (más lento)" if z > 0 else "⚡ ALTA (más rápido)"
    elif abs_z >= 1.0:
        label = "🔸 MODERADA (más lento)" if z > 0 else "🔹 MODERADA (más rápido)"
    else:
        label = "✅ NORMAL"
    return label, z


def build_stats_row(name: str, last_val: Optional[float], hist_vals: List[float]) -> str:
    """Construye una fila Markdown con estadísticas y desviación."""
    if last_val is None or not hist_vals:
        return f"| `{name}` | — | 0 | — | — | — | — | — | — |"
    n = len(hist_vals)
    mean_v = statistics.mean(hist_vals)
    med_v = statistics.median(hist_vals)
    min_v = min(hist_vals)
    max_v = max(hist_vals)
    stdev_v = statistics.stdev(hist_vals) if n > 1 else 0.0
    delta = last_val - mean_v
    pct = (delta / mean_v * 100.0) if mean_v > 0 else 0.0
    status, z = classify_deviation(last_val, mean_v, stdev_v)
    sign = "+" if delta >= 0 else ""
    return (
        f"| `{name}` | **{format_duration(last_val)}** | {n} | "
        f"{format_duration(mean_v)} | {format_duration(med_v)} | "
        f"{format_duration(min_v)} / {format_duration(max_v)} | "
        f"{stdev_v:.1f}s | {sign}{delta:.1f}s ({sign}{pct:.1f}%, z={z:+.2f}) | {status} |"
    )


def generate_report(logs_dir: str) -> str:
    """Genera el reporte completo en Markdown comparando la última ejecución con el histórico."""
    pattern_sub = os.path.join(logs_dir, "wf_Sub_work_*.log")
    pattern_loop = os.path.join(logs_dir, "wf_loop_*.log")
    files = sorted(glob.glob(pattern_sub) + glob.glob(pattern_loop))

    all_subwork: List[Tuple[str, datetime, float]] = []
    all_ris: List[Tuple[str, datetime, float]] = []
    all_pacs: List[Tuple[str, datetime, float]] = []
    all_nodes: Dict[Tuple[str, str], List[Tuple[str, datetime, float]]] = {}

    for fpath in files:
        if os.path.getsize(fpath) < 500:
            continue
        parsed = parse_log_file(fpath)
        for ts, dur in parsed["subwork"]:
            all_subwork.append((fpath, ts, dur))
        for ts, dur in parsed["ris"]:
            all_ris.append((fpath, ts, dur))
        for ts, dur in parsed["pacs"]:
            all_pacs.append((fpath, ts, dur))
        for key, items in parsed["nodes"].items():
            for ts, dur in items:
                all_nodes.setdefault(key, []).append((fpath, ts, dur))

    if not all_subwork:
        return "# Reporte de Tiempos RPA\n\nNo se encontraron ejecuciones exitosas de `Sub_work`."

    all_subwork.sort(key=lambda x: x[1])
    all_ris.sort(key=lambda x: x[1])
    all_pacs.sort(key=lambda x: x[1])

    last_file, last_ts, last_sub_dur = all_subwork[-1]
    last_ris_dur = all_ris[-1][2] if all_ris else None
    last_pacs_dur = all_pacs[-1][2] if all_pacs else None

    # Orden canónico de nodos según la última ejecución en last_file
    last_parsed = parse_log_file(last_file)
    ordered_nodes: List[Tuple[str, str]] = list(last_parsed["nodes"].keys())

    lines = [
        "# Reporte de Tiempos y Desviaciones — Workflow `Sub_work`",
        "",
        f"- **Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Última ejecución analizada:** `{os.path.basename(last_file)}` (inicio `{last_ts.strftime('%Y-%m-%d %H:%M:%S')}`)",
        f"- **Base histórica:** {len(all_subwork)} ejecuciones exitosas de `Sub_work`, {len(all_ris)} de `RIS`, {len(all_pacs)} de `pacs`",
        "",
        "## 1. Resumen por Macro-Fase",
        "",
        "| Fase | Última | N | Promedio | Mediana | Mín / Máx | Desv. Est. | Delta vs Promedio | Estado |",
        "| :--- | :--- | ---: | :--- | :--- | :--- | ---: | :--- | :--- |",
        build_stats_row("Sub_work (Total)", last_sub_dur, [x[2] for x in all_subwork]),
        build_stats_row("RIS", last_ris_dur, [x[2] for x in all_ris]),
        build_stats_row("pacs", last_pacs_dur, [x[2] for x in all_pacs]),
        "",
    ]

    for wf_name in ("RIS", "pacs"):
        wf_nodes = [k for k in ordered_nodes if k[0] == wf_name]
        lines.extend([
            f"## 2.{'1' if wf_name == 'RIS' else '2'}. Detalle por Nodo — `{wf_name}`",
            "",
            "| Nodo | Última | N | Promedio | Mediana | Mín / Máx | Desv. Est. | Delta vs Promedio | Estado |",
            "| :--- | :--- | ---: | :--- | :--- | :--- | ---: | :--- | :--- |",
        ])
        for key in wf_nodes:
            _, node_name = key
            hist = [x[2] for x in all_nodes.get(key, [])]
            last_node_runs = last_parsed["nodes"].get(key, [])
            last_val = last_node_runs[-1][1] if last_node_runs else None
            lines.append(build_stats_row(node_name, last_val, hist))
        lines.append("")

    lines.extend([
        "## 3. Criterio de Desviación",
        "",
        "- **NORMAL:** $|z| < 1.0$ respecto al promedio histórico.",
        "- **MODERADA:** $1.0 \\le |z| < 2.0$ respecto al promedio histórico.",
        "- **ALTA:** $|z| \\ge 2.0$ respecto al promedio histórico (posible anomalía o cuello de botella).",
        "",
    ])

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera reporte de tiempos y desviaciones RPA.")
    parser.add_argument(
        "--logs-dir",
        default=r"C:\Desarrollo\RPA_3\rpa_framework\logs",
        help="Directorio donde se encuentran los archivos wf_*.log",
    )
    parser.add_argument(
        "--output",
        default=r"C:\Desarrollo\RPA_3\rpa_framework\logs\reporte_tiempos_ultima_ejecucion.md",
        help="Ruta de salida del reporte Markdown",
    )
    args = parser.parse_args()

    report = generate_report(args.logs_dir)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Reporte generado en: {args.output}")


if __name__ == "__main__":
    main()
