import os
import re

files_to_fix = [
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\sistema\verifica_openrouter.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\sistema\check_db_connection.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\web\Inicio_ris.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\web\seleccion int 2.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\web\busca_doctor.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\web\procesar_pdf_doctor.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\web\detecta_patologia_ia_v2.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ui\Abre_pacs.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ui\ingresa_user_pacs.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ocr\busca_busqueda de pacientes.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ui\busqueda_paciente.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ocr\busqueda_triple_text_only.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ui\pega en word.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ui\actualiza_estado.py",
    r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ui\verifica_inicio_v4_similitud.py"
]

def process_file(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Regex to find the exception block
    # We want to match: except Exception as e:\n ... up to sys.exit(1)
    
    # Simple regex approach:
    # Look for 'except Exception as e:' and then capture everything until 'sys.exit(1)'
    pattern = re.compile(r'(^[ \t]+)(except Exception as [a-zA-Z_0-9]+:.*?sys\.exit\(\d+\))', re.DOTALL | re.MULTILINE)
    
    script_name = os.path.basename(filepath)
    
    def replacer(match):
        indent = match.group(1)
        original_block = match.group(2)
        
        # We replace the whole block with handle_error_and_exit
        new_block = f"""except Exception as e:
{indent}    import sys
{indent}    sys.path.append(r'c:\\Desarrollo\\RPA_3')
{indent}    try:
{indent}        from rpa_framework.utils.error_handler import handle_error_and_exit
{indent}        handle_error_and_exit("{script_name}", str(e))
{indent}    except ImportError:
{indent}        print(f"ERROR_HANDLER NO ENCONTRADO: {{str(e)}}")
{indent}        sys.exit(1)"""
        return indent + new_block

    new_content = pattern.sub(replacer, content)

    if new_content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed: {script_name}")
    else:
        print(f"No changes made to: {script_name}")

for fp in files_to_fix:
    process_file(fp)
