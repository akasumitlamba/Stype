"""
Stype — Smart Voice Dictation Engine
A polished, user-friendly speech-to-text tool with a premium floating pill overlay, dashboard, and auto-learning dictionary.
"""
import sys
import re
import time
import json
import os

# Silence huggingface_hub warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import datetime
import difflib
import threading
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
import shutil

# ═══════════════════════════════════════════════════════════
# WINDOWS SYMLINK FIX
# ═══════════════════════════════════════════════════════════
# HuggingFace Hub tries to use symlinks for caching models. On Windows, 
# this requires Developer Mode or Admin rights, otherwise it throws WinError 1314.
# We intercept os.symlink and force it to copy the file instead.
if os.name == "nt":
    def _patched_symlink(src, dst, target_is_directory=False, **kwargs):
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    os.symlink = _patched_symlink

from faster_whisper import WhisperModel

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QFrame, QScrollArea, QSizePolicy,
    QSystemTrayIcon, QMenu, QStackedWidget, QLineEdit, QFileDialog,
    QCheckBox, QSlider, QTabWidget, QProgressBar, QTextEdit
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, pyqtProperty, QObject, QTimer, QPropertyAnimation,
    QRect, QPoint, QSharedMemory, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush,
    QRadialGradient, QCursor, QPainterPath, QPalette, QLinearGradient,
    QIcon, QAction, QKeySequence
)
# ═══════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════
FORMATTING_PROMPT = (
    "This is a highly accurate, professionally formatted transcription. "
    "It uses proper punctuation: commas, periods, question marks, and exclamation marks. "
    "When the speaker lists items, they are formatted as a bullet list:\n"
    "- First item\n- Second item\n- Third item\n"
    "Sentences are properly capitalized."
)


# ═══════════════════════════════════════════════════════════
#  DATA MANAGER (Persistence & Learning)
# ═══════════════════════════════════════════════════════════
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, "stype_data.json")

DEFAULT_SETTINGS = {
    "hotkey": "ctrl+space",
    "model": "Balanced (Small)",
    "device": "CPU",
    "language": "English",
    "mic_device": "",  # empty = system default
    "auto_silence": True,
    "silence_seconds": 3.0,
    "launch_on_startup": False,
}

LANGUAGES = {
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Japanese": "ja",
    "Chinese": "zh",
    "Korean": "ko",
    "Hindi": "hi",
    "Russian": "ru",
    "Arabic": "ar",
    "Auto-Detect": None,
}

class DataManager:
    def __init__(self):
        self.data = {
            "settings": dict(DEFAULT_SETTINGS),
            "personal_dict": [],
            "history": []
        }
        self.load()

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    loaded = json.load(f)
                    self.data["personal_dict"] = loaded.get("personal_dict", [])
                    if not self.data["personal_dict"] and "dictionary" in loaded:
                        for k, v in loaded["dictionary"].items():
                            clean_k = k.replace(r'\b', '').replace('\\', '')
                            self.data["personal_dict"].append({"target": clean_k, "replacement": v})
                    self.data["history"] = loaded.get("history", [])
                    saved_settings = loaded.get("settings", {})
                    for k, v in DEFAULT_SETTINGS.items():
                        self.data["settings"][k] = saved_settings.get(k, v)
            except Exception as e:
                print(f"[Stype] Error loading data: {e}")

    def save(self):
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"[Stype] Error saving data: {e}")

    def get(self, key):
        return self.data["settings"].get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data["settings"][key] = value
        self.save()

    def add_history(self, text):
        import datetime
        entry = {"text": text, "time": datetime.datetime.now().isoformat()}
        self.data["history"].insert(0, entry)
        if len(self.data["history"]) > 100:
            self.data["history"] = self.data["history"][:100]
        self.save()

    def clear_history(self):
        self.data["history"] = []
        self.save()

    def export_history(self, filepath):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for entry in self.data["history"]:
                    txt = entry["text"] if isinstance(entry, dict) else entry
                    ts = entry.get("time", "") if isinstance(entry, dict) else ""
                    f.write(f"[{ts}] {txt}\n\n")
            return True
        except Exception:
            return False

    def import_history(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                raw = f.read().strip()
            if not raw:
                return 0

            imported = []
            try:
                loaded = json.loads(raw)
                source = loaded.get("history", []) if isinstance(loaded, dict) else loaded
                if isinstance(source, list):
                    for item in source:
                        if isinstance(item, dict):
                            text = str(item.get("text", "")).strip()
                            ts = str(item.get("time", "")).strip()
                        else:
                            text = str(item).strip()
                            ts = ""
                        if text:
                            imported.append({"text": text, "time": ts or datetime.datetime.now().isoformat()})
            except Exception:
                blocks = [b.strip() for b in re.split(r"\n\s*\n", raw) if b.strip()]
                for block in blocks:
                    match = re.match(r"^\[([^\]]*)\]\s*(.*)$", block, re.S)
                    if match:
                        ts = match.group(1).strip()
                        text = match.group(2).strip()
                    else:
                        ts = ""
                        text = block
                    if text:
                        imported.append({"text": text, "time": ts or datetime.datetime.now().isoformat()})

            if not imported:
                return 0

            existing_keys = {
                (entry.get("time", ""), entry.get("text", ""))
                for entry in self.data.get("history", [])
                if isinstance(entry, dict)
            }
            merged = []
            for entry in imported:
                key = (entry.get("time", ""), entry.get("text", ""))
                if key not in existing_keys:
                    merged.append(entry)
                    existing_keys.add(key)

            if not merged:
                return 0

            self.data["history"] = (merged + self.data.get("history", []))[:100]
            self.save()
            return len(merged)
        except Exception as e:
            print(f"[Stype] Error importing history: {e}")
            return 0

data_manager = DataManager()

STARTUP_APP_NAME = "Stype"
STARTUP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{os.path.abspath(__file__)}"'

def is_launch_on_startup_enabled():
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, STARTUP_APP_NAME)
        return bool(value)
    except (FileNotFoundError, OSError):
        return False

def set_launch_on_startup(enabled):
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, STARTUP_APP_NAME, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, STARTUP_APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        print(f"[Stype] Startup setting failed: {e}")
        return False

# ═══════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════
MODELS = {
    "Fast (Base)":    "base.en",
    "Balanced (Small)": "small.en",
    "Accurate (Medium)": "medium.en",
    "Best (Large v3)": "large-v3",
}

# ── Neobrutalism Palette ──
NB_BG       = "#FFFDF7"   # warm cream background
NB_CARD     = "#FFFFFF"   # card white
NB_INK      = "#1A1A2E"   # near-black ink
NB_ORANGE   = "#FF6B35"   # primary accent
NB_PURPLE   = "#7B61FF"   # secondary accent
NB_GREEN    = "#06D6A0"   # success / listening
NB_YELLOW   = "#FFD166"   # warning / processing
NB_PINK     = "#EF476F"   # danger / cancel
NB_BLUE     = "#118AB2"   # info
NB_MUTED    = "#6C757D"   # muted text
NB_BORDER   = "#1A1A2E"   # thick borders
NB_SHADOW   = "#1A1A2E"   # hard shadow color

STATES = {
    "loading":      {"label": "Loading...",    "dot": NB_YELLOW, "border": NB_INK},
    "starting_mic": {"label": "Opening Mic...", "dot": NB_MUTED,  "border": NB_INK},
    "ready":        {"label": "Ready",         "dot": NB_GREEN,  "border": NB_INK},
    "listening":    {"label": "Listening...",  "dot": NB_GREEN,  "border": NB_INK},
    "processing":   {"label": "Processing...", "dot": NB_YELLOW, "border": NB_INK},
    "pasted":       {"label": "Pasted",        "dot": NB_GREEN,  "border": NB_INK},
}

# ═══════════════════════════════════════════════════════════
#  TOGGLE SWITCH WIDGET
# ═══════════════════════════════════════════════════════════
class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(38, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 2
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(120)

    @pyqtProperty(int)
    def pos(self): return self._pos
    @pos.setter
    def pos(self, p):
        self._pos = p
        self.update()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._anim.setEndValue(20 if checked else 2)
        self._anim.start()

    def nextCheckState(self):
        super().nextCheckState()
        self._anim.setEndValue(20 if self.isChecked() else 2)
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Track — neobrutalism: solid color, thick border, subtle rounding
        track_color = QColor(NB_ORANGE) if self.isChecked() else QColor("#E0DDD5")
        p.setPen(QPen(QColor(NB_BORDER), 2.0))
        p.setBrush(track_color)
        p.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 10, 10)
        
        # Thumb — white circle with black border
        p.setPen(QPen(QColor(NB_BORDER), 1.5))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(self._pos, 2, 16, 16)


class BrutalComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._arrow = QLabel("▼", self)
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._arrow.setStyleSheet(f"color: {NB_INK}; font-size: 11px; font-weight: 900; background: transparent;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrow.setGeometry(self.width() - 31, 1, 30, self.height() - 2)


class Signals(QObject):
    state_changed = pyqtSignal(str)          
    transcription_done = pyqtSignal(str)     
    model_progress = pyqtSignal(str)         

def post_process(text: str) -> str:
    text = text.strip()
    if not text:
        return text

    for entry in data_manager.data.get("personal_dict", []):
        target = entry.get("target", "").strip()
        replacement = entry.get("replacement", "").strip()
        if target and replacement and target.lower() != replacement.lower():
            pattern = r'\b' + re.escape(target) + r'\b'
            try:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            except Exception:
                pass

    ordinal_pattern = re.compile(
        r'\b(first(?:ly)?|second(?:ly)?|third(?:ly)?|fourth(?:ly)?|fifth(?:ly)?|'
        r'sixth(?:ly)?|seventh(?:ly)?|eighth(?:ly)?|ninth(?:ly)?|tenth(?:ly)?)\b[,:]?\s*',
        re.IGNORECASE
    )
    ordinal_matches = ordinal_pattern.findall(text)
    if len(ordinal_matches) >= 2:
        parts = ordinal_pattern.split(text)
        items, i, prefix = [], 0, ""
        while i < len(parts):
            part = parts[i].strip().rstrip('.,;')
            if part and not ordinal_pattern.match(part):
                if not items:
                    prefix = part.rstrip(':').rstrip(',').strip()
                else:
                    items[-1] = items[-1].rstrip('.,;').strip()
            elif ordinal_pattern.match(part + " "):
                if i + 1 < len(parts):
                    items.append(parts[i + 1].strip().rstrip('.,;'))
                    i += 1
            i += 1
        if len(items) >= 2:
            result = prefix + (":\n" if prefix else "")
            for item in items:
                if item:
                    item = item[0].upper() + item[1:] if item else item
                    result += f"- {item}\n"
            return result.strip()

    number_pattern = re.compile(
        r'\b(?:number\s+)?(one|two|three|four|five|six|seven|eight|nine|ten)[,:]?\s*',
        re.IGNORECASE
    )
    number_matches = number_pattern.findall(text)
    if len(number_matches) >= 2 and 'number' in text.lower():
        parts = number_pattern.split(text)
        items, i, prefix = [], 0, ""
        while i < len(parts):
            part = parts[i].strip().rstrip('.,;')
            if part and not number_pattern.match(part):
                if not items:
                    prefix = part.rstrip(':').rstrip(',').strip()
                else:
                    items[-1] = items[-1].rstrip('.,;').strip()
            elif number_pattern.match("number " + part + " "):
                if i + 1 < len(parts):
                    items.append(parts[i + 1].strip().rstrip('.,;'))
                    i += 1
            i += 1
        if len(items) >= 2:
            result = prefix + (":\n" if prefix else "")
            for item in items:
                if item:
                    item = item[0].upper() + item[1:] if item else item
                    result += f"- {item}\n"
            return result.strip()

    if text and text[-1] not in '.!?':
        text += '.'
    return text


# ═══════════════════════════════════════════════════════════
#  FLOATING PILL OVERLAY (with audio level + recording time)
# ═══════════════════════════════════════════════════════════
class PillOverlay(QWidget):
    clicked_toggle = pyqtSignal()
    clicked_cancel = pyqtSignal()
    clicked_dashboard = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Ready size
        self._ready_w, self._ready_h = 56, 26
        # Active size
        self._active_w, self._active_h = 130, 26
        
        self.resize(self._ready_w, self._ready_h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._state = "loading"
        self._drag_pos = None
        self._drag_moved = False
        self._audio_level = 0.0  # 0.0 – 1.0
        self._rec_start = None
        self._manually_hidden = False

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._do_hide)

        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(300)

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_tick)
        self._blink_timer.start(600)
        self._blink_on = True


        self._paint_timer = QTimer(self)
        self._paint_timer.timeout.connect(self.update)

        self._reshow_timer = QTimer(self)
        self._reshow_timer.setSingleShot(True)
        self._reshow_timer.timeout.connect(self._reshow_pill)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.left() + (screen.width() - self.width()) // 2,
                  screen.bottom() - self.height() - 18)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {NB_BG};
                border: 2px solid {NB_BORDER};
                color: {NB_INK};
                padding: 4px;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-weight: 600;
            }}
            QMenu::item {{
                padding: 8px 20px;
            }}
            QMenu::item:selected {{
                background-color: {NB_ORANGE};
                color: white;
            }}
            QMenu::separator {{
                height: 2px;
                background: {NB_BORDER};
                margin: 4px 8px;
            }}
        """)
        hide_action = QAction("Hide for 1 hour", self)
        hide_action.triggered.connect(self._hide_for_hour)
        menu.addAction(hide_action)
        
        dash_action = QAction("Dashboard / Settings", self)
        dash_action.triggered.connect(self.clicked_dashboard.emit)
        menu.addAction(dash_action)

        menu.addSeparator()
        quit_action = menu.addAction("Quit App")
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.exec(event.globalPos())

    def _hide_for_hour(self):
        self._manually_hidden = True
        self.hide()
        self._reshow_timer.start(3600 * 1000) # 1 hour

    def _reshow_pill(self):
        self._manually_hidden = False
        self.show()
        self.setWindowOpacity(1.0)


    def _do_hide(self):
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.start()

    def _resize_and_center(self, target_w, target_h):
        if self.width() == target_w and self.height() == target_h: return
        self.resize(target_w, target_h)
        screen = QApplication.primaryScreen().availableGeometry()
        cx = screen.left() + screen.width() // 2
        self.move(cx - target_w // 2, screen.bottom() - target_h - 18)

    def set_audio_level(self, level: float):
        self._audio_level = max(0.0, min(1.0, level))

    def set_state(self, state_key: str):
        self._state = state_key

        # If manually hidden, only show for active recording/pasting states
        is_active = state_key in ["listening", "processing", "pasted", "starting_mic"]
        should_be_visible = not self._manually_hidden or is_active

        if should_be_visible:
            if self.windowOpacity() < 1.0:
                self._opacity_anim.setEndValue(1.0)
                self._opacity_anim.start()
            if self.isHidden(): 
                self.show()
        else:
            # If we return to ready and were manually hidden, hide again
            if self.isVisible():
                self.hide()

        if state_key == "listening":
            self._blink_timer.start(600)
            self._hide_timer.stop()
            self._paint_timer.start(33)  # ~30fps
            self._rec_start = time.time()
        else:
            self._blink_timer.stop()
            self._blink_on = True
            self._paint_timer.stop()
            self._rec_start = None
            self._audio_level = 0.0

        if state_key in ["starting_mic", "listening"]:
            target_w = 84  # Increased for better gap
        elif state_key in ["processing"]:
            target_w = 134 # Reduced to tighten gap
        elif state_key in ["loading", "pasted"]:
            target_w = 106
        else:
            target_w = self._ready_w
            
        self._resize_and_center(target_w, self._active_h if target_w != self._ready_w else self._ready_h)

        if state_key == "ready":
            self._hide_timer.stop() # Keep it always visible!
        elif state_key == "pasted":
            self._hide_timer.start(2500)
        else:
            self._hide_timer.stop()

        self.update()

    def _blink_tick(self):
        self._blink_on = not self._blink_on
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        state = STATES.get(self._state, STATES["ready"])
        w, h = self.width(), self.height()

        # ── Neobrutalism pill: solid bg, thick border, hard shadow ──
        shadow_offset = 3
        radius = 6

        # Hard shadow (offset rectangle)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(2 + shadow_offset, 2 + shadow_offset, w - 6, h - 6, radius, radius)
        p.fillPath(shadow_path, QBrush(QColor(NB_BORDER)))

        # Main pill body
        pill_path = QPainterPath()
        pill_path.addRoundedRect(2, 2, w - 6, h - 6, radius, radius)
        p.fillPath(pill_path, QBrush(QColor(NB_BG)))

        # ── Draw RED cancel section if active ──
        has_cancel = self._state in ["starting_mic", "listening", "processing"]
        cancel_sec_w = 26
        if has_cancel:
            # Corrected right edge to w-4 to match rounded rect end
            red_rect = QRect(w - 4 - cancel_sec_w, 2, cancel_sec_w, h - 6)
            p.save()
            p.setClipPath(pill_path)
            p.fillRect(red_rect, QColor(NB_PINK))
            # Separator line
            p.setPen(QPen(QColor(NB_BORDER), 2.0))
            p.drawLine(w - 4 - cancel_sec_w, 2, w - 4 - cancel_sec_w, h - 4)
            p.restore()

        # Thick border around the whole thing
        p.setPen(QPen(QColor(NB_BORDER), 2.5))
        p.drawPath(pill_path)

        if self._state == "ready":
            # Three bold dots in orange
            p.setBrush(QBrush(QColor(NB_ORANGE)))
            p.setPen(QPen(QColor(NB_BORDER), 1.0))
            cx, cy = (w - shadow_offset) // 2, (h - shadow_offset + 4) // 2
            p.drawEllipse(QPoint(cx - 9, cy), 3, 3)
            p.drawEllipse(QPoint(cx, cy), 3, 3)
            p.drawEllipse(QPoint(cx + 9, cy), 3, 3)
            p.end()
            return

        use_equalizer = self._state in ["starting_mic", "listening"]

        if use_equalizer:
            bars = 5
            bar_w = 4
            spacing = 3
            start_x = 14
            
            if self._state == "starting_mic":
                heights = [6, 8, 12, 8, 6]
                for i in range(bars):
                    bx = start_x + i * (bar_w + spacing)
                    by = (h - shadow_offset + 4) // 2 - heights[i] // 2
                    p.setBrush(QBrush(QColor(NB_MUTED)))
                    p.setPen(QPen(QColor(NB_BORDER), 1.0))
                    p.drawRect(bx, by, bar_w, heights[i])
            else:
                if not hasattr(self, '_smoothed_level'): self._smoothed_level = 0.0
                self._smoothed_level += (self._audio_level - self._smoothed_level) * 0.35
                
                max_h = h - 10
                center_h = 4 + int((max_h - 4) * self._smoothed_level)
                mid_h = 4 + int((max_h - 6) * self._smoothed_level)
                side_h = 4 + int((max_h - 10) * self._smoothed_level)

                heights = [side_h, mid_h, center_h, mid_h, side_h]
                bar_colors = [NB_ORANGE, NB_YELLOW, NB_GREEN, NB_YELLOW, NB_ORANGE]
                
                for i in range(bars):
                    bar_h = max(4, heights[i])
                    bx = start_x + i * (bar_w + spacing)
                    by = (h - shadow_offset + 4) // 2 - bar_h // 2
                    p.setBrush(QBrush(QColor(bar_colors[i])))
                    p.setPen(QPen(QColor(NB_BORDER), 1.0))
                    p.drawRect(bx, by, bar_w, bar_h)

            # Draw White X in the red section
            p.setPen(QPen(Qt.GlobalColor.white, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            cx = (w - 4) - (cancel_sec_w // 2)
            cy = (h - shadow_offset + 4) // 2
            r = 4
            p.drawLine(cx - r, cy - r, cx + r, cy + r)
            p.drawLine(cx - r, cy + r, cx + r, cy - r)
        else:
            dot_x = 16
            dot_y = (h - shadow_offset + 4) // 2
            dot_color = QColor(state["dot"])
            if self._state == "processing" and not self._blink_on:
                dot_color.setAlpha(80)

            # Solid dot with border (no glow)
            if self._state == "pasted":
                # Draw boxy tick for 'pasted'
                p.setPen(QPen(QColor(NB_GREEN), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
                p.drawLine(dot_x - 4, dot_y + 1, dot_x - 1, dot_y + 4)
                p.drawLine(dot_x - 1, dot_y + 4, dot_x + 5, dot_y - 3)
            else:
                p.setPen(QPen(QColor(NB_BORDER), 1.5))
                p.setBrush(QBrush(dot_color))
                p.drawEllipse(QPoint(dot_x, dot_y), 5, 5)

            # Text label — bold and dark
            font = QFont("Inter", 8, QFont.Weight.Bold)
            if not font.exactMatch(): font = QFont("Segoe UI", 8, QFont.Weight.Bold)
            p.setFont(font)
            p.setPen(QColor(NB_INK))
            label = state["label"]
            # Ensure text doesn't hit the cancel section
            text_rect = QRect(28, 0, w - (40 if self._state == "processing" else 34), h - shadow_offset + 2)
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

            if self._state == "processing":
                # Draw White X in the red section
                p.setPen(QPen(Qt.GlobalColor.white, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                cx = (w - 4) - (cancel_sec_w // 2)
                cy = (h - shadow_offset + 4) // 2
                r = 4
                p.drawLine(cx - r, cy - r, cx + r, cy + r)
                p.drawLine(cx - r, cy + r, cx + r, cy - r)

        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_moved = False

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._drag_moved = True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._drag_moved:
            w = self.width()
            # If clicked on X button during active states
            if self._state in ["listening", "starting_mic", "processing"] and event.pos().x() > w - 34:
                self.clicked_cancel.emit()
            else:
                self.clicked_toggle.emit()
        self._drag_pos = None


# ═══════════════════════════════════════════════════════════
#  HISTORY ITEM WIDGET (Editable & Auto-learning)
# ═══════════════════════════════════════════════════════════
class HistoryItem(QFrame):
    def __init__(self, entry):
        super().__init__()
        # Support both old string format and new dict format
        if isinstance(entry, dict):
            text = entry.get("text", "")
            self._timestamp = entry.get("time", "")
        else:
            text = str(entry)
            self._timestamp = ""
        self.original_text = text
        self.setObjectName("HistoryItem")
        self.setStyleSheet(f"""
            QFrame#HistoryItem {{
                background: {NB_CARD};
                border: 2px solid {NB_BORDER};
            }}
            QFrame#HistoryItem:hover {{
                background: #FFF8ED;
                border: 2px solid {NB_ORANGE};
            }}
            QLabel {{
                color: {NB_INK};
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 13px;
                background: transparent;
                border: none;
            }}
            QLabel#meta {{
                color: {NB_MUTED};
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton {{
                background: {NB_YELLOW};
                color: {NB_INK};
                border: 2px solid {NB_BORDER};
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 800;
                min-width: 70px;
            }}
            QPushButton:hover {{
                background: {NB_ORANGE};
                color: white;
            }}
            QTextEdit {{
                background: {NB_BG};
                border: 2px solid {NB_BORDER};
                padding: 10px;
                color: {NB_INK};
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 13px;
            }}
        """)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)
        text_col.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lbl = QLabel(text)
        self.lbl.setWordWrap(True)
        self.lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        text_col.addWidget(self.lbl)

        # Meta row: timestamp + word/char count
        meta_parts = []
        if self._timestamp:
            try:
                dt = datetime.datetime.fromisoformat(self._timestamp)
                delta = datetime.datetime.now() - dt
                if delta.total_seconds() < 60:
                    meta_parts.append("just now")
                elif delta.total_seconds() < 3600:
                    meta_parts.append(f"{int(delta.total_seconds()//60)}m ago")
                elif delta.total_seconds() < 86400:
                    meta_parts.append(f"{int(delta.total_seconds()//3600)}h ago")
                else:
                    meta_parts.append(dt.strftime("%b %d, %H:%M"))
            except Exception:
                pass
        words = len(text.split()) if text.strip() else 0
        chars = len(text)
        meta_parts.append(f"{words} words · {chars} chars")
        self.meta_lbl = QLabel("  ·  ".join(meta_parts))
        self.meta_lbl.setObjectName("meta")
        text_col.addWidget(self.meta_lbl)

        main_layout.addLayout(text_col, stretch=1)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._handle_primary)
        btn_layout.addWidget(self.btn_copy)



        main_layout.addLayout(btn_layout)

    def _handle_primary(self):
        pyperclip.copy(self.original_text)
        self.btn_copy.setText("Copied!")
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("Copy"))


# ═══════════════════════════════════════════════════════════
#  DICTIONARY ENTRY WIDGET
# ═══════════════════════════════════════════════════════════
class DictEntryWidget(QFrame):
    def __init__(self, entry_data, on_delete, on_change):
        super().__init__()
        self.entry_data = entry_data
        self.on_change = on_change
        self.setObjectName("DictEntryWidget")
        self.setStyleSheet(f"""
            QFrame#DictEntryWidget {{
                background: {NB_CARD};
                border: 2px solid {NB_BORDER};
            }}
            QPushButton {{
                background: {NB_PINK};
                color: white;
                border: 2px solid {NB_BORDER};
                font-weight: 800;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: #D63B5C;
            }}
            QLineEdit {{
                background: {NB_BG};
                border: 2px solid {NB_BORDER};
                padding: 4px 8px;
                color: {NB_INK};
                font-size: 12px;
                font-weight: 500;
            }}
            QLineEdit:focus {{ border-color: {NB_ORANGE}; }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        
        self.entry_type = entry_data.get("type", "replace") # default to replace for legacy entries
        
        type_lbl = QLabel("Vocab" if self.entry_type == "vocab" else "Replace")
        type_lbl.setStyleSheet(f"color: {NB_PURPLE}; font-weight: 800; font-size: 11px; min-width: 45px;")
        layout.addWidget(type_lbl)
        
        self.target_edit = QLineEdit(entry_data.get("target", ""))
        self.target_edit.editingFinished.connect(self._notify_change)
        
        if self.entry_type == "vocab":
            self.target_edit.setPlaceholderText("Word to learn (e.g. Payal)")
            layout.addWidget(self.target_edit, stretch=1)
        else:
            self.target_edit.setPlaceholderText("When I say...")
            layout.addWidget(self.target_edit, stretch=1)
            
            arrow = QLabel("→")
            arrow.setStyleSheet(f"color: {NB_INK}; font-weight: 900; font-size: 16px;")
            layout.addWidget(arrow)
            
            self.repl_edit = QLineEdit(entry_data.get("replacement", ""))
            self.repl_edit.setPlaceholderText("Replace with...")
            self.repl_edit.editingFinished.connect(self._notify_change)
            layout.addWidget(self.repl_edit, stretch=1)
            
        del_btn = QPushButton("×")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFixedSize(24, 24)
        del_btn.clicked.connect(lambda: on_delete(self))
        
        layout.addWidget(del_btn)
        
    def _notify_change(self):
        new_target = self.target_edit.text()
        new_repl = self.repl_edit.text() if hasattr(self, 'repl_edit') else ""
        if new_target != self.entry_data.get("target") or new_repl != self.entry_data.get("replacement"):
            self.entry_data["target"] = new_target
            self.entry_data["replacement"] = new_repl
            self.on_change()

# ═══════════════════════════════════════════════════════════
#  MINIMAL BACKGROUND WIDGET
# ═══════════════════════════════════════════════════════════
class PremiumBackgroundWidget(QWidget):
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(0, 0, self.width(), self.height(), QColor(NB_BG))


# ═══════════════════════════════════════════════════════════
#  MAIN WINDOW (DASHBOARD) — Enhanced with tabs
# ═══════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    model_changed = pyqtSignal(str, str)
    settings_changed = pyqtSignal()  # emitted when any setting changes

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stype Dashboard")
        self.setMinimumSize(440, 640)

        self.setStyleSheet(f"""
            * {{
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }}
            QWidget {{
                color: {NB_INK};
                background: transparent;
            }}
            QLabel {{
                color: {NB_INK};
                background: transparent;
                border: none;
            }}
            QLabel#muted {{
                color: {NB_MUTED};
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#section_lbl {{
                color: {NB_INK};
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 1.2px;
                text-transform: uppercase;
            }}
            QComboBox {{
                background-color: {NB_CARD};
                border: 2px solid {NB_BORDER};
                padding: 7px 38px 7px 12px;
                color: {NB_INK};
                font-size: 12px;
                font-weight: 600;
                min-height: 28px;
            }}
            QComboBox:hover {{
                border-color: {NB_ORANGE};
            }}
            QComboBox:focus {{
                border-color: {NB_ORANGE};
            }}
            QComboBox::drop-down {{
                border: none;
                border-left: 2px solid {NB_BORDER};
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 10px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {NB_CARD};
                border: 2px solid {NB_BORDER};
                color: {NB_INK};
                selection-background-color: {NB_ORANGE};
                outline: 0;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                min-height: 28px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {NB_ORANGE};
                color: white;
            }}
            QPushButton#apply_btn {{
                background-color: {NB_ORANGE};
                color: #ffffff;
                font-weight: 800;
                font-size: 13px;
                border: 3px solid {NB_BORDER};
                padding: 11px 20px;
                min-height: 38px;
            }}
            QPushButton#apply_btn:hover {{ background-color: #E85D2A; }}
            QPushButton#apply_btn:pressed {{ background-color: #CC4F22; }}
            QPushButton#secondary_btn {{
                background-color: {NB_YELLOW};
                color: {NB_INK};
                font-weight: 700;
                font-size: 12px;
                border: 2px solid {NB_BORDER};
                padding: 8px 16px;
                min-height: 32px;
            }}
            QPushButton#secondary_btn:hover {{
                background-color: {NB_ORANGE};
                color: white;
            }}
            QPushButton#quit_btn {{
                background-color: {NB_PINK};
                color: #ffffff;
                font-weight: 900;
                font-size: 12px;
                border: 2px solid {NB_BORDER};
                padding: 4px 10px;
                min-height: 24px;
            }}
            QPushButton#quit_btn:hover {{
                background-color: #D63B5C;
            }}
            QPushButton#hotkey_btn {{
                background-color: {NB_PURPLE};
                color: #ffffff;
                font-weight: 800;
                font-size: 13px;
                border: 2px solid {NB_BORDER};
                padding: 8px 16px;
                min-height: 32px;
                letter-spacing: 1px;
            }}
            QPushButton#hotkey_btn:hover {{
                background-color: #6A50E0;
            }}
            QLineEdit {{
                background: {NB_CARD};
                border: 2px solid {NB_BORDER};
                padding: 7px 12px;
                color: {NB_INK};
                font-size: 12px;
                font-weight: 500;
                min-height: 28px;
            }}
            QLineEdit:focus {{ border-color: {NB_ORANGE}; }}
            QTabWidget::pane {{
                border: none;
                background: transparent;
            }}
            QTabBar::tab {{
                background: {NB_CARD};
                color: {NB_MUTED};
                padding: 10px 18px;
                font-size: 12px;
                font-weight: 700;
                border: 2px solid {NB_BORDER};
                border-bottom: none;
                min-width: 70px;
                margin-right: -2px;
            }}
            QTabBar::tab:selected {{
                color: {NB_INK};
                background: {NB_ORANGE};
                color: white;
            }}
            QTabBar::tab:hover {{ color: {NB_INK}; }}
            QCheckBox {{
                color: {NB_INK};
                font-size: 12px;
                font-weight: 600;
                spacing: 9px;
            }}
            QCheckBox::indicator {{
                width: 17px; height: 17px;
                border: 2px solid {NB_BORDER};
                background: {NB_CARD};
            }}
            QCheckBox::indicator:checked {{
                background: {NB_ORANGE};
                border-color: {NB_BORDER};
            }}
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                border: 2px solid {NB_BORDER};
                background: {NB_BG};
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background: {NB_ORANGE};
                border: 1px solid {NB_BORDER};
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #E85D2A; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

        central = PremiumBackgroundWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(28, 28, 28, 20)
        main_layout.setSpacing(16)

        # ── Header
        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("Stype Dashboard")
        title.setFont(QFont("Inter", 18, QFont.Weight.ExtraBold))
        header.addWidget(title)
        header.addStretch()
        self.status_label = QLabel("Loading Model...")
        self.status_label.setObjectName("status_label")
        self.status_label.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.status_label.setStyleSheet(f"color: {NB_YELLOW}; background: {NB_INK}; padding: 4px 10px; border: 2px solid {NB_BORDER};")
        header.addWidget(self.status_label)
        quit_btn = QPushButton("Quit")
        quit_btn.setObjectName("quit_btn")
        quit_btn.setFixedWidth(62)
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.setToolTip("Quit Stype completely")
        quit_btn.clicked.connect(QApplication.instance().quit)
        header.addWidget(quit_btn)
        main_layout.addLayout(header)

        # ── Tabs
        tabs = QTabWidget()
        main_layout.addWidget(tabs, stretch=1)

        # ═══ TAB 1: Engine Settings
        engine_tab = QWidget()
        el = QVBoxLayout(engine_tab)
        el.setContentsMargins(0, 20, 0, 16)
        el.setSpacing(20)

        def section_label(text):
            lbl = QLabel(text)
            lbl.setObjectName("section_lbl")
            return lbl

        def field_block(title, widget):
            block = QVBoxLayout()
            block.setSpacing(6)
            block.addWidget(section_label(title))
            block.addWidget(widget)
            return block

        self.model_combo = BrutalComboBox()
        self.model_combo.addItems(list(MODELS.keys()))
        self.model_combo.setCurrentText(data_manager.get("model") or "Balanced (Small)")
        el.addLayout(field_block("Accuracy Model", self.model_combo))

        self.device_combo = BrutalComboBox()
        self.device_combo.addItems(["CPU", "GPU (NVIDIA CUDA)"])
        self.device_combo.setCurrentText(data_manager.get("device") or "CPU")
        el.addLayout(field_block("Processing Device", self.device_combo))

        startup_block = QVBoxLayout()
        startup_block.setSpacing(10)
        startup_block.addWidget(section_label("Launch on Startup"))
        startup_row = QHBoxLayout()
        self.launch_startup_cb = ToggleSwitch()
        startup_enabled = bool(data_manager.get("launch_on_startup")) or is_launch_on_startup_enabled()
        self.launch_startup_cb.setChecked(startup_enabled)
        startup_row.addWidget(self.launch_startup_cb)
        startup_row.addWidget(QLabel("Start Stype when Windows signs in"))
        startup_row.addStretch()
        startup_block.addLayout(startup_row)
        el.addLayout(startup_block)

        el.addStretch()

        apply_btn = QPushButton("Apply & Reload Engine")
        apply_btn.setObjectName("apply_btn")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._on_apply)
        el.addWidget(apply_btn)

        tabs.addTab(engine_tab, " Engine")

        # ═══ TAB 2: Audio Settings
        audio_tab = QWidget()
        al = QVBoxLayout(audio_tab)
        al.setContentsMargins(0, 20, 0, 16)
        al.setSpacing(20)

        # Mic
        self.mic_combo = BrutalComboBox()
        self._populate_mics()
        al.addLayout(field_block("Microphone", self.mic_combo))

        # Hotkey
        hk_block = QVBoxLayout()
        hk_block.setSpacing(6)
        hk_block.addWidget(section_label("Global Hotkey"))
        self.current_hotkey_value = data_manager.get("hotkey") or "ctrl+space"
        self.hotkey_btn = QPushButton(self.current_hotkey_value.upper())
        self.hotkey_btn.setObjectName("hotkey_btn")
        self.hotkey_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hotkey_btn.setToolTip("Click, then press your key combination")
        self.hotkey_btn.clicked.connect(self._listen_hotkey)
        hk_block.addWidget(self.hotkey_btn)
        hk_hint = QLabel("Click to change — then press your new key combo")
        hk_hint.setObjectName("muted")
        hk_block.addWidget(hk_hint)
        al.addLayout(hk_block)

        # Auto-silence block
        silence_block = QVBoxLayout()
        silence_block.setSpacing(10)
        silence_block.addWidget(section_label("Auto-Stop on Silence"))

        silence_top_row = QHBoxLayout()
        self.auto_silence_cb = ToggleSwitch()
        auto_silence_val = data_manager.get("auto_silence")
        self.auto_silence_cb.setChecked(bool(auto_silence_val))
        silence_top_row.addWidget(self.auto_silence_cb)
        silence_top_row.addWidget(QLabel("Enable auto-stop after silence"))
        silence_top_row.addStretch()
        silence_block.addLayout(silence_top_row)

        sec_row = QHBoxLayout()
        sec_row.setSpacing(10)
        sec_lbl = QLabel("Duration:")
        sec_lbl.setStyleSheet(f"color: {NB_INK}; font-size: 12px; font-weight: 600;")
        sec_row.addWidget(sec_lbl)
        self.silence_input = QLineEdit()
        self.silence_input.setFixedWidth(64)
        self.silence_input.setFixedHeight(24)
        self.silence_input.setPlaceholderText("3.0")
        self.silence_input.setText(f"{data_manager.get('silence_seconds'):.1f}")
        sec_row.addWidget(self.silence_input)
        sec_unit_lbl = QLabel("seconds")
        sec_unit_lbl.setStyleSheet(f"color: {NB_MUTED}; font-size: 12px; font-weight: 600;")
        sec_row.addWidget(sec_unit_lbl)
        sec_row.addStretch()
        silence_block.addLayout(sec_row)
        al.addLayout(silence_block)

        al.addStretch()

        save_audio_btn = QPushButton("Save Audio Settings")
        save_audio_btn.setObjectName("apply_btn")
        save_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_audio_btn.clicked.connect(self._on_save_audio)
        al.addWidget(save_audio_btn)

        tabs.addTab(audio_tab, " Audio")

        # ═══ TAB 3: Dictionary
        dict_tab = QWidget()
        dl = QVBoxLayout(dict_tab)
        dl.setContentsMargins(0, 14, 0, 0)
        dl.setSpacing(10)

        # Header layout
        dict_header = QHBoxLayout()
        dict_lbl = QLabel("Personal Dictionary")
        dict_lbl.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {NB_INK};")
        dict_header.addWidget(dict_lbl)
        dict_header.addStretch()

        add_vocab_btn = QPushButton("+ Word")
        add_vocab_btn.setObjectName("secondary_btn")
        add_vocab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_vocab_btn.clicked.connect(lambda: self._on_add_dict_entry("vocab"))
        dict_header.addWidget(add_vocab_btn)

        add_repl_btn = QPushButton("+ Replacement")
        add_repl_btn.setObjectName("secondary_btn")
        add_repl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_repl_btn.clicked.connect(lambda: self._on_add_dict_entry("replace"))
        dict_header.addWidget(add_repl_btn)
        dl.addLayout(dict_header)

        # Helper info
        info_lbl = QLabel("Add words to improve recognition, or set replacements (e.g., 'address' → '123 Main St').")
        info_lbl.setStyleSheet(f"color: {NB_MUTED}; font-size: 11px; font-weight: 600;")
        info_lbl.setWordWrap(True)
        dl.addWidget(info_lbl)

        # Dictionary Scroll
        self.dict_scroll = QScrollArea()
        self.dict_scroll.setWidgetResizable(True)
        self.dict_scroll_content = QWidget()
        self.dict_scroll_content.setStyleSheet("background: transparent;")
        
        self.dict_layout = QVBoxLayout(self.dict_scroll_content)
        self.dict_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dict_layout.setContentsMargins(0, 0, 6, 0)
        self.dict_layout.setSpacing(8)
        
        self._load_dictionary_ui()

        self.dict_scroll.setWidget(self.dict_scroll_content)
        dl.addWidget(self.dict_scroll)
        self.dict_layout.addStretch()
        
        tabs.addTab(dict_tab, " Dictionary")

        # ═══ TAB 4: History
        history_tab = QWidget()
        hl = QVBoxLayout(history_tab)
        hl.setContentsMargins(0, 14, 0, 0)
        hl.setSpacing(10)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search transcriptions...")
        self.search_input.textChanged.connect(self._on_search)
        hl.addWidget(self.search_input)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")

        self.history_layout = QVBoxLayout(self.scroll_content)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_layout.setContentsMargins(0, 0, 6, 0)
        self.history_layout.setSpacing(8)

        self.scroll.setWidget(self.scroll_content)
        hl.addWidget(self.scroll)
        self._rebuild_history_ui()

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        import_btn = QPushButton("Import History")
        import_btn.setObjectName("secondary_btn")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._on_import)
        btn_row.addWidget(import_btn)

        export_btn = QPushButton("Export History")
        export_btn.setObjectName("secondary_btn")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._on_export)
        btn_row.addWidget(export_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("secondary_btn")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._on_clear_history)
        btn_row.addWidget(clear_btn)
        hl.addLayout(btn_row)

        tabs.addTab(history_tab, " History")

        # ── Footer hint
        hotkey_text = (data_manager.get("hotkey") or "ctrl+space").upper().replace("+", " + ")
        hint = QLabel(f"<b>{hotkey_text}</b>  •  Close this window to run in background")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setContentsMargins(0, 4, 0, 0)
        main_layout.addWidget(hint)
        self._hint_label = hint

    def _populate_mics(self):
        self.mic_combo.clear()
        self.mic_combo.addItem("System Default")
        try:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    self.mic_combo.addItem(f"{d['name']}", i)
        except Exception:
            pass
        saved = data_manager.get("mic_device")
        if saved:
            idx = self.mic_combo.findText(saved)
            if idx >= 0:
                self.mic_combo.setCurrentIndex(idx)

    def _listen_hotkey(self):
        """Temporarily unregister the active hotkey, wait for PyQT key event."""
        if hasattr(self, '_engine_ref') and self._engine_ref:
            try:
                keyboard.remove_hotkey(self._engine_ref._current_hotkey)
                self._engine_ref._current_hotkey = None
            except Exception:
                pass

        self.hotkey_btn.setText("Press key combo...")
        self.hotkey_btn.setEnabled(False)
        self._capturing_hotkey = True
        self.grabKeyboard()

    def keyPressEvent(self, event):
        if getattr(self, '_capturing_hotkey', False):
            key = event.key()
            # Ignore if only modifier is pressed (wait for a real key)
            if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
                return
                
            if key == Qt.Key.Key_Escape:
                # Cancel capture
                self._capturing_hotkey = False
                self.releaseKeyboard()
                self._on_hotkey_captured(self.current_hotkey_value)
                return

            mods = event.modifiers()
            parts = []
            if mods & Qt.KeyboardModifier.ControlModifier: parts.append("ctrl")
            if mods & Qt.KeyboardModifier.AltModifier: parts.append("alt")
            if mods & Qt.KeyboardModifier.ShiftModifier: parts.append("shift")
            if mods & Qt.KeyboardModifier.MetaModifier: parts.append("windows")

            key_str = QKeySequence(key).toString().lower()
            if key_str == " ": 
                key_str = "space"
            
            if key_str:
                parts.append(key_str)
                
            hotkey = "+".join(parts)
            self._capturing_hotkey = False
            self.releaseKeyboard()
            self._on_hotkey_captured(hotkey)
            return
            
        super().keyPressEvent(event)

    def _on_hotkey_captured(self, hotkey):
        self.current_hotkey_value = hotkey
        self.hotkey_btn.setText(hotkey.upper())
        self.hotkey_btn.setEnabled(True)
        # Re-register the hotkey if engine is linked
        if hasattr(self, '_engine_ref') and self._engine_ref:
            self._engine_ref._register_hotkey()

    def _on_apply(self):
        model_name = self.model_combo.currentText()
        model_id = MODELS[model_name]
        device = "cuda" if "GPU" in self.device_combo.currentText() else "cpu"
        launch_on_startup = self.launch_startup_cb.isChecked()
        data_manager.set("model", model_name)
        data_manager.set("device", self.device_combo.currentText())
        data_manager.set("launch_on_startup", launch_on_startup)
        if set_launch_on_startup(launch_on_startup):
            self.status_label.setText("Startup Saved")
            self.status_label.setStyleSheet(f"color: white; background: {NB_GREEN}; padding: 4px 10px; border: 2px solid {NB_BORDER};")
        self.model_changed.emit(model_id, device)

    def _on_save_audio(self):
        data_manager.set("mic_device", self.mic_combo.currentText())
        data_manager.set("hotkey", self.current_hotkey_value.strip() or "ctrl+space")
        data_manager.set("auto_silence", self.auto_silence_cb.isChecked())
        try:
            secs = float(self.silence_input.text().strip())
            secs = max(0.5, min(30.0, secs))
        except ValueError:
            secs = 3.0
            self.silence_input.setText("3.0")
        data_manager.set("silence_seconds", secs)
        hotkey_text = data_manager.get("hotkey").upper().replace("+", " + ")
        self._hint_label.setText(f"<b>{hotkey_text}</b> to talk. Close window to run in background.")
        self.settings_changed.emit()

    def _on_search(self, query):
        query = query.lower().strip()
        for i in range(self.history_layout.count()):
            widget = self.history_layout.itemAt(i).widget()
            if widget:
                visible = not query or query in widget.original_text.lower()
                widget.setVisible(visible)

    def _rebuild_history_ui(self):
        while self.history_layout.count():
            child = self.history_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for entry in data_manager.data["history"]:
            item = HistoryItem(entry)
            self.history_layout.addWidget(item)
        self.history_layout.addStretch()

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import History", "", "Text or JSON Files (*.txt *.json);;All Files (*)")
        if not path:
            return
        count = data_manager.import_history(path)
        if count:
            self._rebuild_history_ui()
            self.status_label.setText(f"Imported {count}")
            self.status_label.setStyleSheet(f"color: white; background: {NB_GREEN}; padding: 4px 10px; border: 2px solid {NB_BORDER};")
        else:
            self.status_label.setText("Nothing Imported")
            self.status_label.setStyleSheet(f"color: {NB_INK}; background: {NB_YELLOW}; padding: 4px 10px; border: 2px solid {NB_BORDER};")
        QTimer.singleShot(2000, lambda: self.update_status("ready"))

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export History", "stype_history.txt", "Text Files (*.txt)")
        if path:
            if data_manager.export_history(path):
                self.status_label.setText("Exported!")
                self.status_label.setStyleSheet(f"color: white; background: {NB_GREEN}; padding: 4px 10px; border: 2px solid {NB_BORDER};")
                QTimer.singleShot(2000, lambda: self.update_status("ready"))

    def _on_clear_history(self):
        data_manager.clear_history()
        self._rebuild_history_ui()

    def _load_dictionary_ui(self):
        # Clear existing except stretch
        while self.dict_layout.count():
            child = self.dict_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        for entry in data_manager.data.get("personal_dict", []):
            item = DictEntryWidget(entry, self._on_dict_delete, self._on_dict_change)
            self.dict_layout.addWidget(item)

    def _on_add_dict_entry(self, entry_type="vocab"):
        new_entry = {"type": entry_type, "target": "", "replacement": ""}
        if "personal_dict" not in data_manager.data:
            data_manager.data["personal_dict"] = []
        data_manager.data["personal_dict"].insert(0, new_entry)
        data_manager.save()
        item = DictEntryWidget(new_entry, self._on_dict_delete, self._on_dict_change)
        self.dict_layout.insertWidget(0, item)

    def _on_dict_delete(self, widget):
        if widget.entry_data in data_manager.data.get("personal_dict", []):
            data_manager.data["personal_dict"].remove(widget.entry_data)
            data_manager.save()
        widget.deleteLater()

    def _on_dict_change(self):
        data_manager.save()


    def update_status(self, state_key):
        if not state_key in STATES: return
        state = STATES[state_key]
        self.status_label.setText(state["label"])
        dot = state['dot']
        self.status_label.setStyleSheet(f"color: white; background: {dot}; padding: 4px 10px; border: 2px solid {NB_BORDER};")

    def closeEvent(self, event):
        """Override close to just hide the window, keeping it out of the taskbar."""
        event.ignore()
        self.hide()


# ═══════════════════════════════════════════════════════════
#  MAIN ENGINE — Enhanced
# ═══════════════════════════════════════════════════════════
class StypeEngine:
    def __init__(self):
        self.signals = Signals()
        self.model = None
        self.recording = False
        self.processing = False
        self.cancelled = False
        self.audio_frames = []
        self._silence_frames = 0  # count of consecutive silent frames
        self._current_hotkey = None

        self.pill = PillOverlay()
        self.dashboard = MainWindow()
        self.dashboard._engine_ref = self  # allow hotkey capture to pause/resume hotkey

        self.dashboard.model_changed.connect(self._reload_model)
        self.dashboard.settings_changed.connect(self._on_settings_changed)
        self.signals.state_changed.connect(self.pill.set_state)
        self.signals.state_changed.connect(self.dashboard.update_status)
        self.signals.transcription_done.connect(self._on_transcription)
        
        self.pill.clicked_toggle.connect(self._toggle)
        self.pill.clicked_cancel.connect(self._cancel)
        self.pill.clicked_dashboard.connect(self.dashboard.show)


        self._pasted_timer = QTimer()
        self._pasted_timer.setSingleShot(True)
        self._pasted_timer.timeout.connect(lambda: self.signals.state_changed.emit("ready"))

        # Stream is created on demand
        
        # Hotkey setup
        self._register_hotkey()

        # Tray icon
        qapp = QApplication.instance()
        icon_path = os.path.join(DATA_DIR, "assets", "icon.ico")
        icon_path = icon_path if os.path.exists(icon_path) else ""
        self.tray_icon = QSystemTrayIcon(QIcon(icon_path), qapp)
        self.tray_icon.setToolTip("Stype Dictation Engine")

        tray_menu = QMenu()
        show_action = QAction("Show Dashboard", qapp)
        show_action.triggered.connect(self.dashboard.show)
        tray_menu.addAction(show_action)

        toggle_action = QAction("Start/Stop Recording", qapp)
        toggle_action.triggered.connect(self._toggle)
        tray_menu.addAction(toggle_action)

        tray_menu.addSeparator()
        quit_action = QAction("Quit Completely", qapp)
        quit_action.triggered.connect(qapp.quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        self.pill.show()
        # self.dashboard.show() # Hide dashboard on launch as requested

        # Load saved model/device
        saved_model = data_manager.get("model")
        model_id = MODELS.get(saved_model, "small.en")
        saved_device = data_manager.get("device")
        device = "cuda" if "GPU" in saved_device else "cpu"
        threading.Thread(target=self._load_model, args=(model_id, device), daemon=True).start()

    def _start_audio_stream(self):
        """Create or recreate the audio input stream with current mic settings."""
        if hasattr(self, 'stream') and self.stream:
            return

        mic_name = data_manager.get("mic_device")
        device_idx = None
        if mic_name and mic_name != "System Default":
            try:
                devices = sd.query_devices()
                for i, d in enumerate(devices):
                    if d['name'] == mic_name and d['max_input_channels'] > 0:
                        device_idx = i
                        break
            except Exception:
                pass

        try:
            self.stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                device=device_idx,
                callback=self._audio_callback
            )
            self.stream.start()
        except Exception as e:
            print(f"[Stype] Failed to start audio stream: {e}")

    def _stop_audio_stream(self):
        if hasattr(self, 'stream') and self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def _register_hotkey(self):
        """Register the global hotkey from settings."""
        if self._current_hotkey:
            try:
                keyboard.remove_hotkey(self._current_hotkey)
            except Exception:
                pass
        hotkey = data_manager.get("hotkey") or "ctrl+space"
        try:
            self._current_hotkey = keyboard.add_hotkey(hotkey, self._toggle)
        except Exception as e:
            print(f"[Stype] Failed to register hotkey '{hotkey}': {e}")
            self._current_hotkey = keyboard.add_hotkey('ctrl+space', self._toggle)

    def _on_settings_changed(self):
        """Called when audio/hotkey settings are saved."""
        self._register_hotkey()
        self._stop_audio_stream()

    def _audio_callback(self, indata, frames, time_info, status):
        if self.recording:
            self.audio_frames.append(indata.copy())

            # Audio level for pill VU meter
            rms = np.sqrt(np.mean(indata ** 2))
            level = min(1.0, (rms / 0.03) ** 0.5)  # boost lower volumes
            self.pill.set_audio_level(level)

            # Auto-silence detection
            if data_manager.get("auto_silence"):
                silence_threshold = 0.002
                if rms < silence_threshold:
                    self._silence_frames += 1
                else:
                    self._silence_frames = 0

                silence_limit = data_manager.get("silence_seconds")
                # 16000 Hz, ~1024 frames per callback → ~62 callbacks/sec
                if self._silence_frames > (silence_limit * 62):
                    self._silence_frames = 0
                    # Auto-stop on main thread
                    QTimer.singleShot(0, self._auto_stop)

    def _auto_stop(self):
        """Stop recording due to silence detection."""
        if self.recording and not self.processing:
            self.recording = False
            self._stop_audio_stream()
            self.processing = True
            self.cancelled = False
            self.signals.state_changed.emit("processing")
            threading.Thread(target=self._process, daemon=True).start()

    def _cancel(self):
        if self.recording:
            self.recording = False
            self._stop_audio_stream()
            self.audio_frames = []
            self.signals.state_changed.emit("ready")
            self.tray_icon.setToolTip("Stype — Ready")
        elif self.processing:
            self.cancelled = True
            self.processing = False
            self.audio_frames = []
            self.signals.state_changed.emit("ready")
            self.tray_icon.setToolTip("Stype — Ready")

    def _toggle(self):
        current_time = time.time()
        if hasattr(self, '_last_toggle') and current_time - self._last_toggle < 0.5:
            return
        self._last_toggle = current_time

        if self.model is None or self.processing:
            return

        if not self.recording:
            self.signals.state_changed.emit("starting_mic")
            self.tray_icon.setToolTip("Stype — Opening Mic...")
            self.audio_frames = []
            self._silence_frames = 0
            threading.Thread(target=self._init_mic_and_record, daemon=True).start()
        else:
            self.recording = False
            self._stop_audio_stream()
            self.processing = True
            self.cancelled = False
            self.signals.state_changed.emit("processing")
            self.tray_icon.setToolTip("Stype — Processing...")
            threading.Thread(target=self._process, daemon=True).start()

    def _init_mic_and_record(self):
        self._start_audio_stream()
        if hasattr(self, 'stream') and self.stream is not None:
            self.recording = True
            self.signals.state_changed.emit("listening")
            self.tray_icon.setToolTip("Stype — Recording...")
        else:
            self.signals.state_changed.emit("ready")
            self.tray_icon.setToolTip("Stype — Ready")

    def _load_model(self, model_id, device):
        self.signals.state_changed.emit("loading")
        try:
            compute_type = "float16" if device == "cuda" else "int8"
            self.model = WhisperModel(
                model_id,
                device=device,
                compute_type=compute_type,
                cpu_threads=os.cpu_count() or 4,
                num_workers=1,
                download_root=os.path.join(DATA_DIR, "whisper_model")
            )
            self.signals.state_changed.emit("ready")
            self.tray_icon.setToolTip("Stype — Ready")
        except Exception as e:
            print(f"[Stype] Model load error: {e}")
            self.signals.state_changed.emit("ready")

    def _reload_model(self, model_id, device):
        self.model = None
        threading.Thread(target=self._load_model, args=(model_id, device), daemon=True).start()

    def _process(self):
        if not self.audio_frames:
            self.processing = False
            self.signals.state_changed.emit("ready")
            self.tray_icon.setToolTip("Stype — Ready")
            return

        audio_data = np.concatenate(self.audio_frames, axis=0).flatten()
        self.audio_frames = []

        try:
            vocab = []
            for entry in data_manager.data.get("personal_dict", []):
                target = entry.get("target", "").strip()
                replacement = entry.get("replacement", "").strip()
                if target:
                    if not replacement or target.lower() == replacement.lower():
                        vocab.append(target)
                    elif replacement:
                        vocab.append(replacement)
            
            prompt = FORMATTING_PROMPT
            if vocab:
                prompt += " Vocabulary: " + ", ".join(list(set(vocab))[:50])
            transcribe_kwargs = dict(
                beam_size=1,            # 1 is much faster (greedy search), 5 is for high accuracy
                vad_filter=True,        # Enable VAD filter to ignore silence
                vad_parameters=dict(min_silence_duration_ms=500), # Aggressive VAD
                condition_on_previous_text=False,
                initial_prompt=prompt,
                language="en"
            )

            segments, _ = self.model.transcribe(audio_data, **transcribe_kwargs)
            
            # Check if user cancelled while we were working
            if self.cancelled:
                return

            raw_text = "".join([s.text for s in segments]).strip()

            if raw_text:
                final_text = post_process(raw_text)
                self.signals.transcription_done.emit(final_text)
            else:
                self.signals.state_changed.emit("ready")
                self.tray_icon.setToolTip("Stype — Ready")
                self.processing = False

        except Exception as e:
            print(f"[Stype] Transcription error: {e}")
            self.signals.state_changed.emit("ready")
            self.processing = False

    def _on_transcription(self, text):
        data_manager.add_history(text)

        # Get the latest history entry (dict with timestamp)
        latest_entry = data_manager.data["history"][0]
        item = HistoryItem(latest_entry)
        self.dashboard.history_layout.insertWidget(0, item)

        # Paste text
        hotkey = data_manager.get("hotkey") or "ctrl+space"
        pyperclip.copy(text)
        for key in hotkey.split("+"):
            try:
                keyboard.release(key.strip())
            except Exception:
                pass
        time.sleep(0.05)
        keyboard.send('ctrl+v')


        self.signals.state_changed.emit("pasted")
        self.tray_icon.setToolTip("Stype — Ready")
        self._pasted_timer.start(2000)
        self.processing = False


if __name__ == "__main__":
    app = QApplication(sys.argv)

    shared_mem = QSharedMemory("StypeVoiceDictationLockID_v1")
    if not shared_mem.create(1):
        print("[Stype] Another instance is already running! Exiting immediately to prevent double pasting.")
        sys.exit(0)

    app.setQuitOnLastWindowClosed(False)
    engine = StypeEngine()
    sys.exit(app.exec())
