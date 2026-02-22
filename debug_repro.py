import sys
import os
import ast
import re
import tempfile

def extract_steps_from_script(script_path):
    try:
        try:
            with open(script_path, "r", encoding="utf-8-sig") as f:
                source = f.read()
        except UnicodeDecodeError:
            with open(script_path, "r", encoding="latin-1") as f:
                source = f.read()
        lines = source.splitlines()
    except Exception:
        return []

    steps = []
    action_pattern = re.compile(r"#\s*Acci[oó]n\s+(\d+)", re.IGNORECASE)
    action_lines = []
    for i, line in enumerate(lines):
        if action_pattern.search(line):
            action_lines.append(i)

    if len(action_lines) >= 2:
        for idx, start in enumerate(action_lines):
            end = action_lines[idx + 1] - 1 if idx + 1 < len(action_lines) else len(lines) - 1
            desc = lines[start].strip().lstrip("#").strip()
            steps.append((start + 1, end + 1, desc))
        return steps
    return []

def build_instrumented_script(script_path, steps, start_step=1):
    try:
        with open(script_path, "r", encoding="utf-8-sig") as f:
            original = f.read()
    except UnicodeDecodeError:
        with open(script_path, "r", encoding="latin-1") as f:
            original = f.read()

    lines = original.splitlines(keepends=True)
    # Ensure lines end with newline
    lines = [l if l.endswith("\n") else l + "\n" for l in lines]

    hook_block = "# HOOK BLOCK MOCK\n"

    for i, (start_1, end_1, desc) in reversed(list(enumerate(steps))):
        step_n = i + 1
        if step_n < start_step:
            continue

        target_idx = start_1 - 1
        if target_idx < 0 or target_idx >= len(lines):
            continue

        indent_str = ""
        found_indent = False
        
        end_search_idx = min(end_1, len(lines))
        
        for k in range(target_idx, end_search_idx):
            line_k = lines[k]
            stripped_k = line_k.lstrip()
            if stripped_k and not stripped_k.startswith("#"):
                indent = len(line_k) - len(stripped_k)
                indent_str = " " * indent
                found_indent = True
                print(f"Step {step_n}: Found indent {indent} at line {k+1}: {repr(line_k)}")
                break
        
        if not found_indent:
            target_line = lines[target_idx]
            stripped = target_line.lstrip()
            indent = len(target_line) - len(stripped)
            indent_str = " " * indent
            print(f"Step {step_n}: Fallback indent {indent} at line {target_idx+1}")

        hook_call = (
            f"{indent_str}_rpa_step_hook({step_n})\n"
        )
        lines.insert(target_idx, hook_call)

    return hook_block + "".join(lines)

path = r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ui\patologia_critica,_con_cierre_ok.py"
steps = extract_steps_from_script(path)
print(f"Steps found: {len(steps)}")
code = build_instrumented_script(path, steps)

# Write output to investigate
with open("debug_output.py", "w", encoding="utf-8") as f:
    f.write(code)

# Check indentation of inserted lines
out_lines = code.splitlines()
for i, line in enumerate(out_lines):
    if "_rpa_step_hook(2)" in line:
        print(f"Line {i+1}: {repr(line)}")
        # Check surrounding lines
        print(f"Prev: {repr(out_lines[i-1])}")
        print(f"Next: {repr(out_lines[i+1])}")
        print(f"Next+1: {repr(out_lines[i+2])}")

print("\nValidating syntax...")
try:
    ast.parse(code)
    print("✅ Syntax OK")
except IndentationError as e:
    print(f"❌ IndentationError: {e}")
    print(f"Line {e.lineno}: {out_lines[e.lineno-1]}")
except SyntaxError as e:
    print(f"❌ SyntaxError: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
