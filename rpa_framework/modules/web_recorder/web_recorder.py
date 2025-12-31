#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web Recorder Module
Captures web browser actions using Selenium and Javascript injection.
"""

import time
import base64
import copy
import threading
import socket
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from queue import Queue
from threading import Thread, Event, Lock
import traceback
import io
import logging

# Silence noisy connection pool warnings from urllib3
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("selenium").setLevel(logging.ERROR)

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException
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
    css_selector: str = ""
    text: str = ""
    name: str = ""
    placeholder: str = ""
    value: str = ""
    attributes: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
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
    
    INJECTION_SCRIPT = r"""
    (function() {
        if (window._rpaRecorder) return;
        
        // --- STYLES FOR HIGHLIGHTER ---
        const style = document.createElement('style');
        style.textContent = `
            .__rpa-highlight {
                outline: 2px solid #ff0000 !important;
                outline-offset: -2px !important;
                background-color: rgba(255, 0, 0, 0.2) !important;
                box-shadow: 0 0 5px rgba(255,0,0,0.8) !important;
                transition: all 0.1s ease;
                z-index: 2147483647 !important;
                cursor: crosshair !important;
            }
        `;
        document.head.appendChild(style);

        // --- UTILITIES ---
        function getCssSelector(el) {
            if (!(el instanceof Element)) return;
            const path = [];
            while (el.nodeType === Node.ELEMENT_NODE) {
                let selector = el.nodeName.toLowerCase();
                if (el.id) {
                    selector += '#' + el.id;
                    path.unshift(selector);
                    break;
                } else {
                    let sib = el, nth = 1;
                    while (sib = sib.previousElementSibling) {
                        if (sib.nodeName.toLowerCase() == selector) nth++;
                    }
                    if (nth != 1) selector += ":nth-of-type("+nth+")";
                }
                path.unshift(selector);
                el = el.parentNode;
            }
            return path.join(" > ");
        }

        function getXPath(element) {
            // 1. ID is best (if simple and looks static)
            if (element.id && element.id.trim() !== '') {
                return "//*[@id='" + element.id + "']";
            }
            
            // 2. Name attribute
            if (element.name && element.name.trim() !== '') {
                var nameMatches = document.getElementsByName(element.name);
                if (nameMatches.length === 1) {
                    return "//" + element.tagName.toLowerCase() + "[@name='" + element.name + "']";
                }
            }
            
            // 3. Smart Class Search (Unique class)
            if (element.className && typeof element.className === 'string' && element.className.trim() !== '') {
                var classes = element.className.trim().split(' ');
                for (var c of classes) {
                     if (c && document.getElementsByClassName(c).length === 1) {
                         return "//" + element.tagName.toLowerCase() + "[contains(@class, '" + c + "')]";
                     }
                }
            }

            // 4. Link Text
            if (element.tagName === 'A' && element.innerText && element.innerText.trim().length > 0 && element.innerText.trim().length < 50) {
                 return "//a[contains(text(), '" + element.innerText.trim() + "')]";
            }
            
            // 5. Parent-based (Relative XPath)
            var path = "";
            var current = element;
            while(current !== document.body && current.parentNode) {
                var ix = 0;
                var siblings = current.parentNode.childNodes;
                for (var i = 0; i < siblings.length; i++) {
                    var sibling = siblings[i];
                    if (sibling === current) {
                        var selector = current.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        path = '/' + selector + path;
                        break;
                    }
                    if (sibling.nodeType === 1 && sibling.tagName === current.tagName)
                        ix++;
                }
                
                current = current.parentNode;
                if (current.id && current.id.trim() !== '') {
                    return "//*[@id='" + current.id + "']" + path;
                }
            }
            
            return "/html/body" + path;
        }

        function getAttributes(el) {
            const attrs = {};
            if (el.hasAttributes()) {
                for (const attr of el.attributes) {
                    attrs[attr.name] = attr.value;
                }
            }
            return attrs;
        }

        // --- SMART COMPONENT DETECTION ---
        function getSmartTarget(el) {
            const MAX_DEPTH = 3; // How many levels up to look
            let current = el;
            
            // 1. Direct Special Handling (Select2, etc.)
            // If we are deep inside a known component structure, jump to container
            if (el.classList.contains('select2-chosen') || el.classList.contains('select2-arrow')) {
               const choice = el.closest('.select2-choice');
               if (choice) return choice;
            }
            if (el.classList.contains('select2-choice')) {
                 const container = el.closest('.select2-container');
                 if (container) return container;
                 return el;
            }

            // 2. Generic Interactive Parent Search
            // If current element is "passive" (span, i, b...), look for interactive parent
            const passiveTags = ['SPAN', 'I', 'B', 'STRONG', 'EM', 'SMALL', 'IMG', 'SVG', 'PATH'];
            
            for (let i = 0; i < MAX_DEPTH; i++) {
                if (!current || current === document.body) break;

                // Check Class Clues for Interactivity
                const cls = (current.className || "").toString().toLowerCase();
                const isClickable = cls.includes('btn') || cls.includes('button') || cls.includes('clickable') || cls.includes('select2-container');
                
                // Check Attributes
                const role = current.getAttribute('role');
                const hasClick = current.onclick || current.getAttribute('onclick');
                
                // Check Tags
                const tag = current.tagName;
                const isInteractiveTag = tag === 'A' || tag === 'BUTTON' || tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA';

                if (isInteractiveTag || hasClick || isClickable || role === 'button' || role === 'combobox') {
                    // We found a better candidate!
                    return current;
                }
                
                // If we started with a passive element, keep looking up.
                // If we started with a DIV that looks plain, keep looking up.
                if (i === 0 && !passiveTags.includes(el.tagName) && el.tagName !== 'DIV') {
                     // If original element was somewhat substantial (e.g. TD, P), maybe it is the target
                     // But let's check one level up just in case it's a TD inside a TR with click?? 
                     // No, usually TD is fine.
                     break; 
                }
                
                current = current.parentElement;
            }
            
            // If nothing better found, return original
            return el;
        }

        // --- PERSISTENCE ---
        try {
            if (typeof sessionStorage !== 'undefined') {
                const savedActions = sessionStorage.getItem('__rpa_actions_backup');
                if (savedActions) {
                    const parsed = JSON.parse(savedActions);
                    if (Array.isArray(parsed) && parsed.length > 0) {
                        console.log("[RPA] Restoring " + parsed.length + " actions from previous page.");
                        window.__rpa_restored = parsed;
                    }
                    sessionStorage.removeItem('__rpa_actions_backup');
                }
            }
        } catch(e) { 
            console.warn("[RPA] Storage error:", e.message); 
        }

        window._rpaRecorder = {
            actions: window.__rpa_restored || [],
            addAction: function(action) {
                const last = this.actions[this.actions.length - 1];
                if (last && last.type === action.type && (action.timestamp - last.timestamp) < 50) {
                    return;
                }
                this.actions.push(action);
                console.log("[RPA] Action captured:", action.type);
            },
            getActions: function() { return this.actions; },
            clearActions: function() { this.actions = []; }
        };
        
        window.addEventListener('beforeunload', function() {
            try {
                if (typeof sessionStorage !== 'undefined' && window._rpaRecorder.actions.length > 0) {
                    sessionStorage.setItem('__rpa_actions_backup', JSON.stringify(window._rpaRecorder.actions));
                }
            } catch(e) {}
        });

        // --- HIGHLIGHTER LOGIC ---
        let lastTarget = null;
        
        document.addEventListener('mouseover', function(e) {
            // Use smart target for highlighting
            const target = getSmartTarget(e.target);
            
            if (lastTarget && lastTarget !== target) {
                 lastTarget.classList.remove('__rpa-highlight');
            }
            
            target.classList.add('__rpa-highlight');
            lastTarget = target;
            
            // Stop propagation to avoid double highlighting (child AND parent)
            // But we can't stop propagation on mouseover easily without side effects?
            // Actually, since we capture (true), we see it first.
            // If we highjack it, maybe. But simpler is just: we highlighted the smart target.
            // The mouseover event bubbles. We use capture=true.
            // Wait, if we use capture=true, we handle it on the way down.
            // We want to suppress highlighting inner elements if we decided the parent is the smart target.
            // But `e.target` is effectively the leaf node.
        }, true);
        
        document.addEventListener('mouseout', function(e) {
             // Just remove from everything to be safe, or track lastTarget
             if (lastTarget) {
                 lastTarget.classList.remove('__rpa-highlight');
                 lastTarget = null; // Clear it so we don't hold ref
             }
             if (e.target) e.target.classList.remove('__rpa-highlight');
        }, true);

        // --- EVENT LISTENERS ---
        
        const clickHandler = function(e) {
            if (e.target === document.body || e.target === document.documentElement) return;
            
            // Use smart target for recording
            const target = getSmartTarget(e.target);
            
            window._rpaRecorder.addAction({
                type: e.type, 
                tag: target.tagName,
                id: target.id || '',
                className: target.className || '',
                xpath: getXPath(target),
                cssSelector: getCssSelector(target),
                text: (target.innerText || target.textContent || '').substring(0, 200),
                attributes: getAttributes(target),
                timestamp: Date.now(),
                x: e.clientX,
                y: e.clientY,
                url: window.location.href
            });
        };

        document.addEventListener('click', clickHandler, true);
        document.addEventListener('dblclick', clickHandler, true);
        document.addEventListener('contextmenu', clickHandler, true);

        const inputHandler = function(e) {
            // Inputs usually don't need smart target, as you click ON the input.
            // But for Select2, the "input" is hidden or handled by JS.
            // If this is a real input event, record it on the target.
            const tag = e.target.tagName;
            if (tag === 'SELECT' || tag === 'INPUT' || tag === 'TEXTAREA') {
                let val = e.target.value;
                let text = '';
                if (tag === 'SELECT') {
                    const selected = e.target.options[e.target.selectedIndex];
                    text = selected ? selected.text : '';
                }
                
                if (e.target.type === 'checkbox' || e.target.type === 'radio') {
                    val = e.target.checked ? 'true' : 'false';
                }

                window._rpaRecorder.addAction({
                    type: tag === 'SELECT' ? 'select' : 'input',
                    tag: tag,
                    id: e.target.id || '',
                    className: e.target.className || '',
                    xpath: getXPath(e.target),
                    cssSelector: getCssSelector(e.target),
                    name: e.target.name || '',
                    value: val,
                    text: text,
                    attributes: getAttributes(e.target),
                    timestamp: Date.now(),
                    url: window.location.href
                });
            }
        };

        document.addEventListener('change', inputHandler, true);
        document.addEventListener('blur', inputHandler, true);
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    inputHandler(e);
                }
                
                window._rpaRecorder.addAction({
                    type: 'keypress',
                    key: 'Enter',
                    tag: e.target.tagName,
                    id: e.target.id || '',
                    className: e.target.className || '',
                    xpath: getXPath(e.target),
                    cssSelector: getCssSelector(e.target),
                    timestamp: Date.now(),
                    url: window.location.href
                });
            }
        }, true);
        
        console.log('RPA Professional Recorder injected successfully');
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
        
        # State to track alert presence during recording
        self.alert_was_present = False
        self.last_action_time = 0 # Track last user action time to filter navs
        
    def _safe_execute(self, script: str, *args) -> Any:
        """
        Executes script safely, handling unexpected alerts.
        """
        if not self.driver:
            return None
            
        try:
            return self.driver.execute_script(script, *args)
        except UnexpectedAlertPresentException as e:
            # Just log it, do not auto-accept. 
            # The monitoring loop will handle the 'alert closed' event.
            print(f"[WebRecorder] Alert present during execution (deferred): {e.alert_text}")
            return None
        except Exception as e:
            # Suppress noisy errors during page transitions
            if "stale element" in str(e).lower() or "javascript error" in str(e).lower():
                pass 
            elif "no such window" in str(e) or "target window already closed" in str(e):
                raise e # Let caller handle window closing
            else:
                print(f"[ERROR] Script execution failed: {e}")
            return None

    def start_browser(self, url: str = "about:blank", maximize: bool = True) -> bool:
        """Starts Chrome browser (Attaches to Port 9222 or Launches new)"""
        try:
            print(f"[WebRecorder] Starting browser: {url}")
            
            # Common options for both attach and launch
            common_chrome_options = ChromeOptions()
            common_chrome_options.set_capability("unhandledPromptBehavior", "ignore")
            common_chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            common_chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            common_chrome_options.add_experimental_option('useAutomationExtension', False)
            common_chrome_options.add_argument("--no-sandbox")
            common_chrome_options.add_argument("--disable-dev-shm-usage")
            common_chrome_options.add_argument("--disable-gpu") 

            # --- FAST PORT CHECK ---
            is_port_open = False
            try:
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5) # Fast check
                    if s.connect_ex(('127.0.0.1', 9222)) == 0:
                        is_port_open = True
            except:
                pass

            # 1. Try to attach to existing Chrome instance
            if is_port_open:
                try:
                    attach_options = ChromeOptions()
                    # IMPORTANT: When using debuggerAddress, most other options cause 'invalid argument'
                    attach_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                    attach_options.set_capability("unhandledPromptBehavior", "ignore")
                    
                    self.driver = webdriver.Chrome(options=attach_options)
                    print("[WebRecorder] Attached to existing Chrome on port 9222")
                except Exception as e:
                    print(f"[WebRecorder] Port 9222 open but failed to attach: {e}")

            # 2. If not attached or port closed, launch new instance
            if not self.driver:
                print("[WebRecorder] Launching new Chrome instance...")
                launch_options = common_chrome_options
                launch_options.add_argument("--remote-debugging-port=9222")
                
                if maximize:
                    launch_options.add_argument("--start-maximized")
                    
                self.driver = webdriver.Chrome(options=launch_options)
                print("[WebRecorder] Launched new Chrome instance on port 9222")

            self.driver.implicitly_wait(10)
            
            # Only navigate if explicitly requested or if it's a fresh launch
            if url and url != "about:blank":
                print(f"[WebRecorder] Navigating to: {url}")
                self.driver.get(url)
            elif 'launch_options' in locals(): # Fresh launch case
                print(f"[WebRecorder] Fresh launch, opening about:blank")
                self.driver.get("about:blank")
            else:
                print(f"[WebRecorder] Staying on current page: {self.driver.current_url}")
                
            self.current_url = self.driver.current_url
            
            # Use safe execute to inject script
            self._safe_execute(self.INJECTION_SCRIPT)
            
            # Start monitoring thread
            self.stop_event.clear()
            self.monitor_thread = Thread(target=self._monitor_actions, daemon=True)
            self.monitor_thread.start()
            
            print("[WebRecorder] Browser started successfully")
            return True
            
        except Exception as e:
            print(f"[WebRecorder] Error starting browser: {e}")
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

                # --- 1. Alert Monitoring ---
                alert_present = False
                try:
                    # Check if alert is present
                    _ = self.driver.switch_to.alert.text
                    alert_present = True
                    if not self.alert_was_present:
                        print(f"[WebRecorder] Alert detected! Waiting for user to handle it...")
                    self.alert_was_present = True
                except NoAlertPresentException:
                    alert_present = False
                except Exception:
                    # Other errors (e.g. window closed)
                    pass
                
                # logic: if alert WAS present and now is NOT, user closed it.
                if self.alert_was_present and not alert_present:
                    print(f"[WebRecorder] Alert disappeared (User handled it). Recording action.")
                    self.alert_was_present = False
                    
                    if self.is_recording and not self.is_paused:
                        self._add_action(WebAction(
                            action_type='handle_alert',
                            timestamp=time.time(),
                            element_info=ElementInfo(tag="ALERT", text="User Handled"),
                            url=self.current_url,
                            value="accept"
                        ))
                    
                    # Re-inject script immediately as it might have been blocked before
                    time.sleep(0.5)
                    self._safe_execute(self.INJECTION_SCRIPT)

                # --- 2. Navigation Monitoring ---
                if not alert_present:
                    try:
                        # Get current URL - this also serves as a check if window is open
                        if self.driver.current_url != self.current_url:
                            current_url = self.driver.current_url
                            # print(f"[WebRecorder] Navigation detected: {self.current_url} -> {current_url}")
                            self.current_url = current_url
                            
                            # START CHANGE: Smart Page Load Detection
                            # If the last action was very recent (<8s), assume this navigation 
                            # was triggered by that action (e.g. click link, submit form).
                            # So DO NOT record an explicit 'driver.get()' page load.
                            time_since_last_action = time.time() - self.last_action_time
                            is_automatic_nav = time_since_last_action < 8.0
                            
                            if self.is_recording and not self.is_paused and not is_automatic_nav:
                                # Log page load action only if it looks like a manual navigation
                                self._add_action(WebAction(
                                    action_type='page_load',
                                    timestamp=time.time(),
                                    element_info=ElementInfo(tag="PAGE"),
                                    url=current_url
                                ))
                            elif is_automatic_nav:
                                # print(f"[WebRecorder] Skipping Page Load record (Auto-navigation detected, diff: {time_since_last_action:.2f}s)")
                                pass
                            # END CHANGE
                            
                            # Re-inject on new page
                            time.sleep(0.5) # Wait for DOM
                            self._safe_execute(self.INJECTION_SCRIPT)

                    except UnexpectedAlertPresentException:
                        # Alert appeared exactly now
                        pass
                    except Exception as e:
                        # Window probably closed
                        if "no such window" in str(e) or "target window already closed" in str(e):
                            print("Browser window closed.")
                            break
                        # Otherwise ignore occasional errors (e.g. during page load)
                
                # --- 3. Script Injection Check ---
                if not alert_present:
                    is_injected = self._safe_execute("return !!window._rpaRecorder")
                    if is_injected is False: # Explicit check for False, not None
                         self._safe_execute(self.INJECTION_SCRIPT)

                if self.is_recording and not self.is_paused and not alert_present:
                    self._capture_actions()
                
                time.sleep(0.2)
                
            except Exception as e:
                print(f"[ERROR] In monitoring loop: {e}")
                time.sleep(1)
    
    def _capture_actions(self):
        """Captures actions from the browser"""
        if not self.driver:
            return
        
        try:
            raw_actions = self._safe_execute(
                "return window._rpaRecorder ? window._rpaRecorder.getActions() : []"
            )
            
            if raw_actions:
                self._safe_execute(
                    "if (window._rpaRecorder) window._rpaRecorder.clearActions();"
                )
                
                for raw_action in raw_actions:
                    action = self._create_web_action(raw_action)
                    if action:
                        self._add_action(action)
            
        except Exception as e:
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
                css_selector=raw_action.get('cssSelector', ''),
                text=raw_action.get('text', ''),
                name=raw_action.get('name', ''),
                placeholder=raw_action.get('placeholder', ''),
                value=raw_action.get('value', ''),
                attributes=raw_action.get('attributes')
            )
            
            screenshot_base64 = None
            screenshot_bbox = None
            
            if self.capture_screenshots and action_type in ['click', 'dblclick', 'contextmenu', 'input', 'select']:
                x = raw_action.get('x', 0)
                y = raw_action.get('y', 0)
                # Sometimes x/y are missing or 0 for non-mouse events, try to get element center?
                # For now use what we have.
                screenshot_base64, screenshot_bbox = self._capture_screenshot_area(x, y)
            
            action = WebAction(
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
            
            # Store key for keypress events
            if action_type == 'keypress':
                action.value = {'key': raw_action.get('key')}
                
            return action
            
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
            # print(f"[ERROR] Capturing screenshot: {e}")
            return None, None
    
    def _add_action(self, action: WebAction):
        """Adds action to the list"""
        with self.lock:
            self.actions.append(action)
            self.last_action_time = time.time() # Update last action time
            
            # Update stats
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

