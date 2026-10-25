# -*- coding: utf-8 -*-
"""
visual_and_click_mixin.py — Ejecución de clic secundario humanizado + Ctrl+D y
generación de imágenes de auditoría visual (_FRANJAS.png y _CLIC.png).
Extraído de busqueda_triple_text_only.py.
"""

import time
import logging
from datetime import datetime
import cv2
import pyautogui

logger = logging.getLogger(__name__)


class TripleSearchVisualClickMixin:
    """Mixin para ejecución de clic y guardado de logs visuales de BusquedaTextOnly."""

    def click_target(self, y_click, img_bgr=None, log_dir=None, base_name=None):
        """
        Hace clic en el centro de la fila candidata detectada.
        y_click = y_center (promedio de centros de palabras OCR de la fila).
        """
        screen_x = int(self.region[0] + (self.region[2] / 2))
        screen_y = int(self.region[1] + y_click)
        
        self.update_db_coordinate(f"{screen_x},{screen_y}")
        
        logger.info(f"--- Iniciando secuencia de clic HUMANIZADA en: {screen_x}, {screen_y} ---")

        if img_bgr is not None and log_dir is not None:
            self.save_click_log_image(
                img_bgr=img_bgr,
                click_x_in_region=int(self.region[2] // 2),
                click_y_in_region=int(y_click),
                screen_x=screen_x,
                screen_y=screen_y,
                log_dir=log_dir,
                base_name=base_name or datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            )

        if self.vf:
            self.vf.highlight_click(screen_x, screen_y)
        
        pyautogui.moveTo(screen_x, screen_y, duration=0.5, tween=pyautogui.easeInOutQuad)
        time.sleep(0.1)
        
        pyautogui.mouseDown(button='right')
        time.sleep(0.15)
        pyautogui.mouseUp(button='right')
        logger.info(f"Click secundario (Derecho) realizado en {screen_x}, {screen_y}")

        time.sleep(1.2)

        pyautogui.hotkey('ctrl', 'd')
        logger.info("Combinación Ctrl+D ejecutada")
        time.sleep(getattr(self, "POST_CLICK_SLEEP", 5.0))

    def save_detection_log_image(self, img_bgr, rows_data, candidates, log_dir, base_name):
        """Guarda imagen con franjas coloreadas mostrando las filas detectadas por OCR."""
        try:
            img_log = img_bgr.copy()
            overlay = img_bgr.copy()
            h, w = img_log.shape[:2]
            half_h = self.CROP_HEIGHT // 2

            cand_y_centers = set(int(c['y_center']) for c in candidates)

            for row in rows_data:
                y_c = int(row['y_center'])
                all_ymins = [i['bounds']['y_min'] for i in row['items'] if 'bounds' in i]
                all_ymaxs = [i['bounds']['y_max'] for i in row['items'] if 'bounds' in i]
                if all_ymins and all_ymaxs:
                    y1 = max(0, int(min(all_ymins)) - 2)
                    y2 = min(h, int(max(all_ymaxs)) + 2)
                else:
                    y1 = max(0, y_c - half_h)
                    y2 = min(h, y_c + half_h)
                row_items = sorted(row['items'], key=lambda x: x['center']['x'])
                row_text = " ".join([i['text'] for i in row_items])[:80]
                row_text_safe = row_text.encode('ascii', 'replace').decode('ascii')

                is_candidate = any(abs(y_c - cy) < self.ROW_TOLERANCE for cy in cand_y_centers)

                if is_candidate:
                    cv2.rectangle(overlay, (0, y1), (w, y2), (0, 200, 50), -1)
                else:
                    cv2.rectangle(overlay, (0, y1), (w, y2), (0, 200, 220), -1)

                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.42
                text_color = (0, 0, 0)
                cv2.putText(img_log, row_text_safe, (4, y2 - 4), font, font_scale, (255, 255, 255), 3, cv2.LINE_AA)
                cv2.putText(img_log, row_text_safe, (4, y2 - 4), font, font_scale, text_color, 1, cv2.LINE_AA)

            alpha = 0.25
            cv2.addWeighted(overlay, alpha, img_log, 1 - alpha, 0, img_log)

            for row in rows_data:
                y_c = int(row['y_center'])
                all_ymaxs2 = [i['bounds']['y_max'] for i in row['items'] if 'bounds' in i]
                y2_text = min(h, int(max(all_ymaxs2)) + 2) if all_ymaxs2 else min(h, y_c + half_h)
                row_items = sorted(row['items'], key=lambda x: x['center']['x'])
                row_text = " ".join([i['text'] for i in row_items])[:80]
                row_text_safe = row_text.encode('ascii', 'replace').decode('ascii')
                is_candidate = any(abs(y_c - cy) < self.ROW_TOLERANCE for cy in cand_y_centers)
                label_color = (0, 80, 0) if is_candidate else (80, 60, 0)
                cv2.putText(img_log, row_text_safe, (4, y2_text - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255,255,255), 3, cv2.LINE_AA)
                cv2.putText(img_log, row_text_safe, (4, y2_text - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.42, label_color, 1, cv2.LINE_AA)

            for cand in candidates:
                y_c = int(cand['y_center'])
                all_cy_mins = [i['bounds']['y_min'] for i in cand['items'] if 'bounds' in i]
                all_cy_maxs = [i['bounds']['y_max'] for i in cand['items'] if 'bounds' in i]
                y1 = max(0, int(min(all_cy_mins)) - 2) if all_cy_mins else max(0, y_c - half_h)
                y2 = min(h, int(max(all_cy_maxs)) + 2) if all_cy_maxs else min(h, y_c + half_h)
                y_click_in_img = int(cand.get('y_click', y_c))
                cv2.rectangle(img_log, (0, y1), (w - 1, y2), (0, 255, 80), 2)
                cv2.line(img_log, (0, y_click_in_img), (w, y_click_in_img), (0, 200, 80), 1)
                click_label = f"CANDIDATO | clic Y={y_click_in_img}"
                cv2.putText(img_log, click_label, (w - 230, y_click_in_img - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 80), 2, cv2.LINE_AA)

            cv2.rectangle(img_log, (0, 0), (w - 1, h - 1), (0, 0, 220), 3)
            cv2.rectangle(img_log, (0, 0), (280, 20), (0, 0, 0), -1)
            cv2.putText(img_log, "AMARILLO=fila OCR  VERDE=candidato",
                        (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

            out_path = log_dir / f"{base_name}_FRANJAS.png"
            cv2.imwrite(str(out_path), img_log)
            logger.info(f"🗺️ Log con franjas OCR guardado: {out_path}")
        except Exception as e:
            logger.warning(f"No se pudo guardar imagen de franjas OCR: {e}")

    def save_click_log_image(self, img_bgr, click_x_in_region, click_y_in_region,
                             screen_x, screen_y, log_dir, base_name):
        """Guarda imagen marcando el punto de clic con cruceta, círculo y coordenadas."""
        try:
            img_click = img_bgr.copy()
            h, w = img_click.shape[:2]
            cx = int(click_x_in_region)
            cy = int(click_y_in_region)

            half_h = self.CROP_HEIGHT // 2
            y1 = max(0, cy - half_h)
            y2 = min(h, cy + half_h)
            overlay = img_click.copy()
            cv2.rectangle(overlay, (0, y1), (w, y2), (0, 50, 255), -1)
            cv2.addWeighted(overlay, 0.3, img_click, 0.7, 0, img_click)

            cross_color = (0, 0, 255)
            cv2.line(img_click, (0, cy), (w, cy), cross_color, 1)
            cv2.line(img_click, (cx, 0), (cx, h), cross_color, 1)

            cv2.circle(img_click, (cx, cy), 14, (0, 0, 255), 2)
            cv2.circle(img_click, (cx, cy), 4,  (0, 0, 255), -1)

            coord_text = f"CLIC ({screen_x}, {screen_y})"
            font = cv2.FONT_HERSHEY_SIMPLEX
            tx = min(cx + 18, w - 180)
            ty = max(cy - 10, 16)
            cv2.putText(img_click, coord_text, (tx, ty), font, 0.55, (255, 255, 255), 4, cv2.LINE_AA)
            cv2.putText(img_click, coord_text, (tx, ty), font, 0.55, (0, 0, 200), 1, cv2.LINE_AA)

            rel_text = f"(region rel: {cx},{cy})"
            cv2.putText(img_click, rel_text, (tx, ty + 18), font, 0.4, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(img_click, rel_text, (tx, ty + 18), font, 0.4, (0, 0, 160), 1, cv2.LINE_AA)

            cv2.rectangle(img_click, (0, 0), (w - 1, h - 1), (0, 0, 200), 3)

            out_path = log_dir / f"{base_name}_CLIC.png"
            cv2.imwrite(str(out_path), img_click)
            logger.info(f"🎯 Log con punto de clic guardado: {out_path}  [screen=({screen_x},{screen_y}) | region=({cx},{cy})]")
        except Exception as e:
            logger.warning(f"No se pudo guardar imagen de clic: {e}")
