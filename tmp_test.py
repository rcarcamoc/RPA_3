import sys
import os
sys.path.append(r"c:\Desarrollo\RPA_3\rpa_framework")
from recordings.web.detecta_patologia_ia_v2 import conectar_bd, DB_CONFIG, cargar_datos, detectar_patologia

texto1 = """
TOMOGRAFÍA COMPUTADA DE ABDOMEN y PELVIS
Antecedentes: Diverticulitis aguda
Técnica: Se realizó tomografía computada de abdomen y pelvis en series previas y
posteriores a la inyección de contraste yodado endovenoso no iónico, de baja osmolaridad.
No se administró contraste oral.
Hallazgos:
Fondos de saco pleurales libres.
Se identifican múltiples imágenes hipovasculares distribuidas en forma difusa en el
parénquima hepático, de probable naturaleza quística. A nivel del segmento II se observa
una lesión de aproximadamente 23 mm, con características sugestivas de hemangioma.
Vía biliar intra y extrahepática no dilatadas.
Vesícula distendida, de paredes finas, sin cálculos en su interior.
Páncreas de forma, tamaño y densidad normal, sin evidencia de masas. No se observa
dilatación del conducto principal.
Glándulas suprarrenales de configuración habitual.
Ambos riñones se encuentran bien situados, son de tamaño, forma y densidad normal, sin
evidencia de masas, hidronefrosis ni litiasis, con correcta concentración y uroexcreción del
medio de contraste. Espesor parenquimatoso conservado.
El retroperitoneo libre de adenomegalias.
Apéndice cecal, sin signos inflamatorios.
Formaciones diverticulares en colon, a predominio sigmoide, en este último se asocia
engrosamiento mucoso - parietal de carácter no estenosante, asociado a densificación del
plano graso omental adyacente. No se observan signos de obstrucción de asas intestinales
Grandes vasos de trayecto y calibre normal.
Vejiga distendida de paredes finas sin imágenes patológicas en su interior.
Glándula prostática de tamaño normal.
Fosas isquiorrectales libres.

Fermin Rigoli Gonzalez
 Atrys
14.598.394-0

Impresión:
Diverticulitis aguda no complicada.
Hallazgos son compatibles con múltiples quistes hepáticos, asociados a una lesión focal en
segmento II de probable etiología benigna tipo hemangioma.
"""

texto2 = """
Nombre del paciente RODRIGO  MARTINEZ LABORDE
Número de documento 0010244576-
Edad 56 años
Procedencia
Número de ficha

TOMOGRAFÍA COMPUTADA DE ABDOMEN y PELVIS
Técnica: Se realizó tomografía computada de abdomen y pelvis en series previas y
posteriores a la inyección de contraste yodado endovenoso no iónico, de baja osmolaridad.
No se administró contraste oral.
Hallazgos:
Hígado de forma, tamaño y densidad normal, se identifican múltiples imágenes hipodensas
de distribución difusa en parénquima hepático las cuales no presentan captación de
contraste endovenoso, a predominio del lóbulo izquierdo, hallazgos en relación a quistes.
Vía biliar intra y extrahepática no dilatadas.
Vesícula distendida, de paredes finas, sin cálculos en su interior.
Páncreas de forma, tamaño y densidad normal, sin evidencia de masas. No se observa
dilatación del conducto principal.
Glándulas suprarrenales de configuración habitual.
Ambos riñones se encuentran bien situados, son de tamaño, forma y densidad normal, sin
evidencia de masas, hidronefrosis ni litiasis, con correcta concentración y uroexcreción del
medio de contraste. Espesor parenquimatoso conservado.
El retroperitoneo libre de adenomegalias.
La aorta abdominal infrarrenal presenta dilatación fusiforme, alcanzando un diámetro
máximo de 36 mm, con paredes irregulares en relación a cambios ateromatosos, sin
evidencias de flap de disección, el compromiso se extiende a nivel de la bifurcación aortica
con afectación predominante de la arteria ilíaca común izquierda, la cual se encuentra
dilatada, de aspecto aneurismático, con diámetro aproximado de 27 mm y discreta
tortuosidad de su trayecto hasta su bifurcación, se identifica ateromatosis mixta en todo el
trayecto vascular aortoilíaco.
No se evidencian signos de obstrucción de asas intestinales ni líquido libre en cavidad
abdominal. Diverticulosis colónica a predominio de colon sigmoides.
Vejiga distendida de paredes finas sin imágenes patológicas en su interior.
Fosas isquiorrectales libres.

Impresión:
No hay signos de diverticulitis, hay presencia de divertículos sin signos inflamatorios
infecciosos.
Quistes hepáticos.
Aneurisma de aorta abdominal infrarrenal con extensión a arteria ilíaca común izquierda
sin signos de disección.
"""

try:
    engine = conectar_bd(DB_CONFIG)
    df_acciones, patologias = cargar_datos(engine)
    engine.dispose()
    
    print("Número de patologías:", len(patologias))
    
    print("\n--- TEXTO 1 ---")
    res1 = detectar_patologia(texto1, patologias)
    print("Resultado Texto 1:", res1)
    
    print("\n--- TEXTO 2 ---")
    res2 = detectar_patologia(texto2, patologias)
    print("Resultado Texto 2:", res2)
    
except Exception as e:
    import traceback
    traceback.print_exc()
