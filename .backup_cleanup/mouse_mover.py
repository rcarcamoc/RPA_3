import pyautogui
import random
import time
import sys
from datetime import datetime

# ==========================================================
# CONFIGURACIÓN
# ==========================================================
INTERVALO_SEGUNDOS = 60  # Cambia este valor para personalizar el tiempo
# ==========================================================

def mover_mouse_aleatoriamente():
    """Mueve el mouse a una posición aleatoria dentro de los límites de la pantalla."""
    # Obtener el tamaño de la pantalla
    ancho, alto = pyautogui.size()
    pos_actual = pyautogui.position()
    
    # Generar coordenadas aleatorias
    margen = 100
    target_x = random.randint(margen, ancho - margen)
    target_y = random.randint(margen, alto - margen)
    
    print(f"\n[INFO] Posición actual: {pos_actual}")
    print(f"[INFO] Moviendo a: ({target_x}, {target_y})...")
    
    # Movimiento más lento y visible (1 segundo de duración)
    pyautogui.moveTo(target_x, target_y, duration=1.0)
    
    # Verificar si se movió
    pos_final = pyautogui.position()
    ahora = datetime.now().strftime("%H:%M:%S")
    
    if pos_final != pos_actual:
        print(f"[{ahora}] ✅ Mouse movido exitosamente.")
    else:
        print(f"[{ahora}] ❌ El mouse no cambió de posición. ¿Quizás algo está bloqueando el movimiento?")

def mostrar_cuenta_atras(segundos):
    """Muestra un temporizador regresivo en la consola."""
    for i in range(segundos, 0, -1):
        sys.stdout.write(f"\r⏳ Próximo movimiento en: {i:2d} segundos...   ")
        sys.stdout.flush()
        time.sleep(1)

def iniciar_simulacion():
    """Bucle principal de la simulación."""
    print("╔══════════════════════════════════════════════════════╗")
    print("║          SIMULADOR DE MOVIMIENTO DE MOUSE            ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Intervalo: {INTERVALO_SEGUNDOS} segundos                           ║")
    print("║  Instrucciones:                                      ║")
    print("║  - Presiona Ctrl+C para detener.                     ║")
    print("║  - Failsafe: Mueve el mouse a una esquina para salir.║")
    print("╚══════════════════════════════════════════════════════╝")
    
    print("\n🚀 Iniciando en 3 segundos... Suelta el mouse.")
    time.sleep(3)

    try:
        while True:
            mover_mouse_aleatoriamente()
            mostrar_cuenta_atras(INTERVALO_SEGUNDOS)
    except KeyboardInterrupt:
        print("\n\n🛑 Simulación detenida por el usuario.")
    except pyautogui.FailSafeException:
        print("\n\n⚠️ Failsafe detectado (mouse en esquina).")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")

if __name__ == "__main__":
    # Configurar failsafe de pyautogui (se activa si el usuario mueve el mouse a una esquina)
    pyautogui.FAILSAFE = True
    
    iniciar_simulacion()
