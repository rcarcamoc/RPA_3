import sys
import os
import re
import unicodedata
from rapidfuzz import fuzz, process

patologias = ['Absceso cerebral', 'Absceso psoas', 'Apendicitis aguda', 'Ascitis', 'AVE agudo o en evolucion', 'Coleccion subfrenica', 'Colecistitis aguda', 'Coledocolitiasis c/fiebre', 'Compresion medular', 'Derrame pleural', 'Diseccion carotidea aortica o aneurisma complicado', 'Diseccion carotidea y/o vertebral', 'Diverticulitis', 'Embarazo feto sin latido', 'Embarazo tubario/ovarico', 'Embolia Arterial', 'Empiema dural', 'Encefalitis', 'Fractura de columna como primer hallazgo (trauma agudo)', 'Fractura de craneo como primer hallazgo (trauma agudo)', 'Fractura de pelvis como primer hallazgo (trauma agudo)', 'Hematoma subdural, lobar hemorragia subaracnoidea', 'Hemotorax', 'Hernia estrangulada', 'Hidrocefalia', 'Hipertension Endocraneana HTE', 'Imagenes sospechosas de lesion maligna Birads 4-5', 'Invaginacion intestinal', 'Isquemia mesenterica', 'Meningitis', 'Neumatosis portal', 'Neumo o hemoperitoneo', 'Neumonia', 'Neumotorax a tension', 'Obstruccion intestinal', 'Pancreatitis aguda', 'Patologia neoplasica', 'TEP tromboembolismo pulmonar', 'Torsion ovarica o testicular', 'Tromboflebitis', 'Trombosis venosa cerebral', 'Trombosis venosa profunda y superficial', 'Tumor cerebral s/edema HTE']

texto1 = """
TOMOGRAFÍA COMPUTADA DE ABDOMEN y PELVIS
Antecedentes: Diverticulitis aguda
Técnica: Se realizó tomografía computada de abdomen y pelvis ...
Hallazgos:
Fondos de saco pleurales libres...
Formaciones diverticulares en colon, a predominio sigmoide, en este último se asocia
engrosamiento mucoso - parietal de carácter no estenosante, asociado a densificación del
plano graso omental adyacente.
Impresión:
Diverticulitis aguda no complicada.
Hallazgos son compatibles con múltiples quistes...
"""

texto2 = """
TOMOGRAFÍA COMPUTADA DE ABDOMEN y PELVIS
Hallazgos:
Hígado normal ...
La aorta abdominal infrarrenal presenta dilatación fusiforme, alcanzando un diámetro
máximo de 36 mm, con paredes irregulares en relación a cambios ateromatosos, sin
evidencias de flap de disección, el compromiso se extiende a nivel de la bifurcación aortica
con afectación predominante de la arteria ilíaca común izquierda...
Impresión:
No hay signos de diverticulitis, hay presencia de divertículos sin signos inflamatorios infecciosos.
Aneurisma de aorta abdominal infrarrenal con extensión a arteria ilíaca común izquierda sin signos de disección.
"""

def normalizar_texto(texto: str, mantener_puntuacion: bool = False) -> str:
    texto_nfd = unicodedata.normalize('NFD', texto)
    texto_sin_tildes = ''.join(c for c in texto_nfd if unicodedata.category(c) != 'Mn')
    texto_limpio = re.sub(r'\s+', ' ', texto_sin_tildes.lower().strip())
    if not mantener_puntuacion:
        texto_limpio = re.sub(r'[.,;:]+', '', texto_limpio)
    return texto_limpio

def tiene_negacion(frase: str, match_str: str) -> bool:
    negaciones = [
        r'no hay signos de', r'sin signos de', r'no se observan signos de',
        r'sin evidencia[s]? de', r'no se evidencia', r'ausencia de',
        r'no hay', r'no presenta', r'descartar', r'sin'
    ]
    for neg in negaciones:
        if re.search(neg + r'.{0,40}' + re.escape(match_str), frase):
            return True
    return False

def detectar_patologia(diagnostico: str, patologias: list) -> str:
    diagnostico_puntuacion = normalizar_texto(diagnostico, mantener_puntuacion=True)
    
    match_impresion = re.search(r'(impresion|conclusion|impresion:)[;:\s]+(.*)', diagnostico_puntuacion)
    if match_impresion:
        seccion_analisis = match_impresion.group(2)
    else:
        match_hallazgos = re.search(r'(hallazgos)[;:\s]+(.*)', diagnostico_puntuacion)
        if match_hallazgos:
            seccion_analisis = match_hallazgos.group(2)
        else:
            seccion_analisis = diagnostico_puntuacion
            
    print("SECCION ANALISIS:", seccion_analisis)

    seccion_norm = seccion_analisis.replace('.', '').replace(',', '')
    frases_seccion = re.split(r'[.,;]', seccion_analisis)

    # EXACT MATCH
    patologias_norm = [normalizar_texto(p) for p in patologias]
    
    # First priority: custom logic (e.g. Diverticulitis)
    if "Diverticulitis" in patologias:
        diverticulitis_negada = False
        for f in frases_seccion:
            f_norm = normalizar_texto(f, mantener_puntuacion=True)
            if "diverticulitis" in f_norm and tiene_negacion(f_norm, "diverticulitis"):
                diverticulitis_negada = True

        if not diverticulitis_negada:
            # Check exact match for diverticulitis in conclusion/findings
            if "diverticulitis" in seccion_norm:
                 return "Diverticulitis"
            
            # Check for hallazgos (these might be in the whole text if impression doesnt have it)
            diag_full_norm = normalizar_texto(diagnostico)
            if (
                "diverticular" in diag_full_norm and 
                "engrosamiento" in diag_full_norm and
                ("parietal" in diag_full_norm or "mucoso" in diag_full_norm) and
                ("densificacion" in diag_full_norm or "graso" in diag_full_norm)
            ):
                return "Diverticulitis"

    for patologia_norm, patologia_orig in zip(patologias_norm, patologias):
        if patologia_orig == "Diverticulitis":
             continue
        for frase in frases_seccion:
            f_norm = normalizar_texto(frase, mantener_puntuacion=False)
            if re.search(rf"\b{re.escape(patologia_norm)}\b", f_norm):
                if tiene_negacion(normalizar_texto(frase, True), patologia_norm):
                    print(f"Ignorando {patologia_orig} por negacion")
                else:
                    return patologia_orig

    return "-> LLM"

print("--- Texto 1 ---")
print("RESULT:", detectar_patologia(texto1, patologias))
print("--- Texto 2 ---")
print("RESULT:", detectar_patologia(texto2, patologias))
