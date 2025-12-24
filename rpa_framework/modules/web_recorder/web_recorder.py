#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web Recorder Module
Captures web browser actions using Selenium and Javascript injection.
"""

import time
import base64
import threading
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from queue import Queue
from threading import Thread, Event, Lock
import traceback
import io

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service
    from PIL import Image, ImageGrab, ImageDraw
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# ==================== DATA MODELS ====================

@dataclass
class ElementInfo:
    """Captured element information"""
    tag: str = ""
    element_id: str = ""
    class_name: str = ""
    xpath: str = ""
    text: str = ""
    name: str = ""
    placeholder: str = ""
    value: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class WebAction:
    """Structure to store a browser action"""
    action_type: str
    timestamp: float
    element_info: ElementInfo
    url: str = ""
    screenshot_base64: Optional[str] = None
    screenshot_bbox: Optional[Tuple[int, int, int, int]] = None
    value: Optional[str] = None
    x_coord: int = 0
    y_coord: int = 0
    duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_type': self.action_type,
            'timestamp': self.timestamp,
            'element_info': self.element_info.to_dict(),
            'url': self.url,
            'screenshot_bbox': self.screenshot_bbox,
            'value': self.value,
            'x_coord': self.x_coord,
            'y_coord': self.y_coord,
            'duration': self.duration
        }


@dataclass
class RecordingStats:
    """Recording statistics"""
    total_actions: int = 0
    clicks: int = 0
    inputs: int = 0
    selects: int = 0
    navigations: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def elapsed_time(self) -> float:
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time if self.start_time > 0 else 0
    
    @property
    def elapsed_formatted(self) -> str:
        elapsed = int(self.elapsed_time)
        return f"{elapsed // 60:02d}:{elapsed % 60:02d}"


# ==================== WEB RECORDER ====================

class WebRecorder:
    """Captures web actions using Selenium"""
    
    INJECTION_SCRIPT = """
    (function() {
        if (window._rpaRecorder) return;
        
        window._rpaRecorder = {
            actions: [],
            addAction: function(action) {
                this.actions.push(action);
            },
            getActions: function() {
                return this.actions;
            },
            clearActions: function() {
                this.actions = [];
            }
        };
        
        window.getXPath = function(element) {
            if (element.id !== '')
                return "//*[@id='" + element.id + "']";
            if (element === document.body)
                return element.tagName.toLowerCase();
            
            var ix = 0;
            var siblings = element.parentNode.childNodes;
            for (var i = 0; i < siblings.length; i++) {
                var sibling = siblings[i];
                if (sibling === element)
                    return window.getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                if (sibling.nodeType === 1 && sibling.tagName.toLowerCase() === element.tagName.toLowerCase())
                    ix++;
            }
            return '';
        };
        
        document.addEventListener('click', function(e) {
            if (e.target !== document.body && e.target !== document.documentElement) {
                var element = e.target;
                window._rpaRecorder.addAction({
                    type: 'click',
                    tag: element.tagName,
                    id: element.id || '',
                    className: element.className || '',
                    xpath: window.getXPath(element),
                    text: (element.innerText || element.textContent || '').substring(0, 100),
                    timestamp: Date.now(),
                    x: e.clientX,
                    y: e.clientY,
                    url: window.location.href
                });
            }
        }, true);
        
        document.addEventListener('input', function(e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                window._rpaRecorder.addAction({
                    type: 'input',
                    tag: e.target.tagName,
                    id: e.target.id || '',
                    className: e.target.className || '',
                    xpath: window.getXPath(e.target),
                    name: e.target.name || '',
                    placeholder: e.target.placeholder || '',
                    value: e.target.value || '',
                    timestamp: Date.now(),
                    url: window.location.href
                });
            }
        }, true);
        
        document.addEventListener('change', function(e) {
            if (e.target.tagName === 'SELECT') {
                var selected = e.target.options[e.target.selectedIndex];
                window._rpaRecorder.addAction({
                    type: 'select',
                    tag: 'SELECT',
                    id: e.target.id || '',
                    className: e.target.className || '',
                    xpath: window.getXPath(e.target),
                    name: e.target.name || '',
                    value: e.target.value || '',
                    text: selected ? selected.text : '',
                    timestamp: Date.now(),
                    url: window.location.href
                });
            }
        }, true);
        
        console.log('RPA Recorder injected successfully');
    })();
    """
    
    def __init__(self, capture_screenshots: bool = False):
        if not HAS_DEPS:
            raise ImportError("Missing dependencies: selenium, pillow")
            
        self.driver: Optional[webdriver.Chrome] = None
        self.actions: List[WebAction] = []
        self.stats = RecordingStats()
        self.is_recording = False
        self.is_paused = False
        self.capture_screenshots = capture_screenshots
        self.current_url = ""
        self.lock = Lock()
        self.action_queue = Queue()
        self.monitor_thread: Optional[Thread] = None
        self.stop_event = Event()
        
    def start_browser(self, url: str = "about:blank", maximize: bool = True) -> bool:
        """Starts Chrome browser"""
        try:
            print(f"[WebRecorder] Starting browser: {url}")
            
            chrome_options = ChromeOptions()
            
            if maximize:
                chrome_options.add_argument("--start-maximized")
            
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            self.driver.implicitly_wait(10)
            
            self.driver.get(url)
            self.current_url = url
            
            self.driver.execute_script(self.INJECTION_SCRIPT)
            
            print("[WebRecorder] Browser started successfully")
            return True
            
        except Exception as e:
            print(f"[ERROR] Could not start browser: {e}")
            traceback.print_exc()
            return False
    
    def start_recording(self):
        """Starts recording actions"""
        with self.lock:
            self.is_recording = True
            self.is_paused = False
            self.actions = []
            self.stats = RecordingStats()
            self.stats.start_time = time.time()
        
        print("[WebRecorder] Recording started")
        
        # Add initial page load action
        self._add_action(WebAction(
            action_type='page_load',
            timestamp=time.time(),
            element_info=ElementInfo(tag="PAGE"),
            url=self.current_url
        ))
        
        self.stop_event.clear()
        self.monitor_thread = Thread(target=self._monitor_actions, daemon=True)
        self.monitor_thread.start()
    
    def pause_recording(self):
        """Pauses recording"""
        self.is_paused = True
        print("[WebRecorder] Recording paused")
    
    def resume_recording(self):
        """Resumes recording"""
        self.is_paused = False
        print("[WebRecorder] Recording resumed")
    
    def stop_recording(self):
        """Stops recording"""
        self.is_recording = False
        self.stop_event.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        
        self.stats.end_time = time.time()
        print(f"[WebRecorder] Recording stopped - {self.stats.total_actions} actions captured")
    
    def _monitor_actions(self):
        """Monitoring thread to capture actions continuously"""
        # Small delay to ensure browser is fully ready
        time.sleep(1)
        
        while not self.stop_event.is_set():
            try:
                if not self.driver:
                    time.sleep(1)
                    continue

                # Check if browser is still open
                try:
                    # Get current URL - this also serves as a check if window is open
                    current_url = self.driver.current_url
                except Exception:
                    # Window probably closed
                    break
                
                # Check for navigation
                if current_url != self.current_url:
                    print(f"[WebRecorder] Navigation detected: {self.current_url} -> {current_url}")
                    self.current_url = current_url
                    
                    if self.is_recording and not self.is_paused:
                        # Log page load action
                        self._add_action(WebAction(
                            action_type='page_load',
                            timestamp=time.time(),
                            element_info=ElementInfo(tag="PAGE"),
                            url=current_url
                        ))
                    
                    # Force re-injection on new page
                    try:
                        time.sleep(0.5) # Wait for DOM
                        self.driver.execute_script(self.INJECTION_SCRIPT)
                    except Exception as e:
                        print(f"[WARNING] Re-injection failed initially: {e}")
                
                # Check for injection (redundant check but safe)
                try:
                    is_injected = self.driver.execute_script("return !!window._rpaRecorder")
                    if not is_injected:
                        self.driver.execute_script(self.INJECTION_SCRIPT)
                except Exception:
                    # Might happen if page is reloading
                    pass

                if self.is_recording and not self.is_paused:
                    self._capture_actions()
                
                time.sleep(0.2)
                
            except Exception as e:
                # e.g. browser closed
                if "no such window" in str(e) or "target window already closed" in str(e):
                    print("Browser window closed.")
                    break
                print(f"[ERROR] In monitoring loop: {e}")
                time.sleep(1)
    
    def _capture_actions(self):
        """Captures actions from the browser"""
        if not self.driver:
            return
        
        try:
            raw_actions = self.driver.execute_script(
                "return window._rpaRecorder ? window._rpaRecorder.getActions() : []"
            )
            
            if raw_actions:
                self.driver.execute_script(
                    "if (window._rpaRecorder) window._rpaRecorder.clearActions();"
                )
                
                for raw_action in raw_actions:
                    action = self._create_web_action(raw_action)
                    if action:
                        self._add_action(action)
            
        except Exception as e:
            # print(f"[ERROR] Capturing actions: {e}")
            pass
    
    def _create_web_action(self, raw_action: Dict) -> Optional[WebAction]:
        """Creates a WebAction object from captured data"""
        try:
            action_type = raw_action.get('type', 'unknown')
            
            element_info = ElementInfo(
                tag=raw_action.get('tag', ''),
                element_id=raw_action.get('id', ''),
                class_name=raw_action.get('className', ''),
                xpath=raw_action.get('xpath', ''),
                text=raw_action.get('text', ''),
                name=raw_action.get('name', ''),
                placeholder=raw_action.get('placeholder', ''),
                value=raw_action.get('value', '')
            )
            
            screenshot_base64 = None
            screenshot_bbox = None
            
            if self.capture_screenshots and action_type in ['click', 'input', 'select']:
                x = raw_action.get('x', 0)
                y = raw_action.get('y', 0)
                # Sometimes x/y are missing or 0 for non-mouse events, try to get element center?
                # For now use what we have.
                screenshot_base64, screenshot_bbox = self._capture_screenshot_area(x, y)
            
            return WebAction(
                action_type=action_type,
                timestamp=raw_action.get('timestamp', time.time()) / 1000,
                element_info=element_info,
                url=raw_action.get('url', self.current_url),
                screenshot_base64=screenshot_base64,
                screenshot_bbox=screenshot_bbox,
                value=raw_action.get('value'),
                x_coord=int(raw_action.get('x', 0)),
                y_coord=int(raw_action.get('y', 0))
            )
            
        except Exception as e:
            print(f"[ERROR] Creating WebAction: {e}")
            return None
    
    def _capture_screenshot_area(self, x: int, y: int, size: int = 300) -> Tuple[Optional[str], Optional[Tuple]]:
        """Captures a square area around the coordinates"""
        try:
            # Note: ImageGrab functionality depends on OS.
            # On Windows it works out of the box.
            # However, x and y from browser are relative to the viewport.
            # ImageGrab takes screen coordinates.
            # This is a limitation. To do this properly we need to know window position + viewport offset.
            # But the user asked for this specific feature.
            # A better approach (headless compatible) is to take full page screenshot via Selenium and crop.
            
            if not self.driver:
                return None, None
                
            # Take screenshot of the viewport (visible part)
            # This is safer than ImageGrab which requires screen coordinates
            screenshot_png = self.driver.get_screenshot_as_png()
            image = Image.open(io.BytesIO(screenshot_png))
            
            # x, y are viewport relative
            left = max(0, int(x) - size // 2)
            top = max(0, int(y) - size // 2)
            right = min(image.width, left + size)
            bottom = min(image.height, top + size)
            
            cropped = image.crop((left, top, right, bottom))
            
            draw = ImageDraw.Draw(cropped)
            center_x = (right - left) // 2
            center_y = (bottom - top) // 2
            radius = 10
            draw.ellipse(
                [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                outline='red',
                width=2
            )
            
            buffer = io.BytesIO()
            cropped.save(buffer, format='PNG')
            buffer.seek(0)
            screenshot_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return screenshot_base64, (left, top, right, bottom)
            
        except Exception as e:
            print(f"[ERROR] Capturing screenshot: {e}")
            return None, None
    
    def _add_action(self, action: WebAction):
        """Adds an action to the list (thread-safe)"""
        with self.lock:
            self.actions.append(action)
            self.stats.total_actions += 1
            
            if action.action_type == 'click':
                self.stats.clicks += 1
            elif action.action_type == 'input':
                self.stats.inputs += 1
            elif action.action_type == 'select':
                self.stats.selects += 1
            elif action.action_type in ['navigate', 'page_load']:
                self.stats.navigations += 1
    
    def close(self):
        """Closes the browser"""
        if self.driver:
            try:
                self.driver.quit()
                print("[WebRecorder] Browser closed")
            except Exception as e:
                print(f"[ERROR] Closing browser: {e}")
