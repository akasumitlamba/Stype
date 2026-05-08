"""
Stype — Smart Voice Dictation Engine
A polished, user-friendly speech-to-text tool with a premium floating pill overlay, dashboard, and auto-learning dictionary.
"""
import sys
import re
import time
import json
import os
import datetime
import difflib
import threading
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
from faster_whisper import WhisperModel

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QFrame, QScrollArea, QSizePolicy,
    QSystemTrayIcon, QMenu, QStackedWidget, QLineEdit, QFileDialog,
    QCheckBox, QSlider, QTabWidget, QProgressBar
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QObject, QTimer, QPropertyAnimation,
    QRect, QPoint, QSharedMemory, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush,
    QRadialGradient, QCursor, QPainterPath, QPalette, QLinearGradient,
    QIcon, QAction
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
            "dictionary": {
                r'\bout words\b': 'outwards',
                r'\bin words\b': 'inwards',
                r'\bstype\b': 'Stype',
            },
            "history": []
        }
        self.load()

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    loaded = json.load(f)
                    self.data["dictionary"].update(loaded.get("dictionary", {}))
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

    def learn_correction(self, original, corrected):
        if original == corrected:
            return None, None

        orig_words = original.split()
        corr_words = corrected.split()

        s = difflib.SequenceMatcher(None, orig_words, corr_words)
        for tag, i1, i2, j1, j2 in s.get_opcodes():
            if tag == 'replace':
                wrong = " ".join(orig_words[i1:i2])
                right = " ".join(corr_words[j1:j2])

                # Create a smart regex pattern for the wrong phrase
                if re.search(r'\w', wrong):
                    pattern = r'\b' + re.escape(wrong) + r'\b'
                    self.data["dictionary"][pattern] = right
                    self.save()
                    return wrong, right
        return None, None

data_manager = DataManager()

class CorrectionTracker:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.original_text = ""
        self.current_text = ""
        self.active = False
        self.timer = None
        self.hook = None
        
    def start(self, pasted_text):
        self.original_text = pasted_text
        self.current_text = pasted_text
        self.active = True
        
        if self.hook is None:
            self.hook = keyboard.on_press(self._on_key)
            
        self._reset_timer()
        
    def _reset_timer(self):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(6.0, self.finalize)
        self.timer.start()
        
    def _on_key(self, event):
        if not self.active:
            return
            
        name = event.name
        
        if name in ['left', 'right', 'up', 'down', 'home', 'end', 'page up', 'page down', 'tab', 'enter', 'esc']:
            self.finalize()
            return
            
        if name in ['shift', 'caps lock', 'ctrl', 'alt', 'right shift', 'right ctrl', 'right alt', 'windows']:
            return 
            
        self._reset_timer()
        
        if name == 'backspace':
            if keyboard.is_pressed('ctrl'):
                while len(self.current_text) > 0 and self.current_text[-1] == ' ':
                    self.current_text = self.current_text[:-1]
                while len(self.current_text) > 0 and self.current_text[-1] != ' ':
                    self.current_text = self.current_text[:-1]
            else:
                self.current_text = self.current_text[:-1]
        elif name == 'space':
            self.current_text += ' '
        elif len(name) == 1:
            self.current_text += name
            
    def finalize(self):
        if not self.active:
            return
        self.active = False
        if self.timer:
            self.timer.cancel()
            
        original = self.original_text.strip()
        current = self.current_text.strip()
        
        if original != current and len(current) > 0:
            wrong, right = self.data_manager.learn_correction(original, current)
            if wrong and right:
                print(f"[Global Tracker] Auto-learned: '{wrong}' -> '{right}'")


# ═══════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════
MODELS = {
    "Fast (Base)":    "base.en",
    "Balanced (Small)": "small.en",
    "Accurate (Medium)": "medium.en",
    "Best (Large v3)": "large-v3",
}

STATES = {
    "loading":    {"label": "Loading...",    "dot": "#FFA500", "border": "rgba(255,165,0,0.20)"},
    "ready":      {"label": "Ready",         "dot": "#00C853", "border": "rgba(0,200,83,0.15)"},
    "listening":  {"label": "Listening...",   "dot": "#FF4422", "border": "rgba(255,68,34,0.25)"},
    "processing": {"label": "Processing...", "dot": "#FFB420", "border": "rgba(255,180,32,0.25)"},
    "pasted":     {"label": "Pasted",        "dot": "#2DCE6E", "border": "rgba(45,206,110,0.25)"},
}

FORMATTING_PROMPT = (
    "This is a highly accurate, professionally formatted transcription. "
    "It uses proper punctuation: commas, periods, question marks, and exclamation marks. "
    "When the speaker lists items, they are formatted as a bullet list:\n"
    "- First item\n- Second item\n- Third item\n"
    "Sentences are properly capitalized."
)

class Signals(QObject):
    state_changed = pyqtSignal(str)          
    transcription_done = pyqtSignal(str)     
    model_progress = pyqtSignal(str)         

def post_process(text: str) -> str:
    text = text.strip()
    if not text:
        return text

    for pattern, replacement in data_manager.data["dictionary"].items():
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
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(160, 40)

        self._state = "loading"
        self._drag_pos = None
        self._audio_level = 0.0  # 0.0 – 1.0
        self._rec_start = None

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._do_hide)

        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(300)

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_tick)
        self._blink_timer.start(600)
        self._blink_on = True

        # Repaint at 30fps while recording for smooth level meter
        self._paint_timer = QTimer(self)
        self._paint_timer.timeout.connect(self.update)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.left() + (screen.width() - self.width()) // 2,
                  screen.bottom() - self.height() - 60)

    def _do_hide(self):
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.start()

    def set_audio_level(self, level: float):
        self._audio_level = max(0.0, min(1.0, level))

    def set_state(self, state_key: str):
        self._state = state_key

        if self.windowOpacity() < 1.0:
            self._opacity_anim.setEndValue(1.0)
            self._opacity_anim.start()

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

        if state_key == "ready":
            self._hide_timer.start(4000)
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

        path = QPainterPath()
        path.addRoundedRect(2, 2, w - 4, h - 4, (h - 4) / 2, (h - 4) / 2)

        bg_color = QColor(18, 18, 22, 230)
        p.fillPath(path, QBrush(bg_color))

        border_col = QColor(state["border"])
        border_col.setAlpha(160)
        p.setPen(QPen(border_col, 1.5))
        p.drawPath(path)

        highlight = QPen(QColor(255, 255, 255, 12), 1.0)
        p.setPen(highlight)
        p.drawLine(int(h / 2), 3, int(w - h / 2), 3)

        dot_x, dot_y = 18, h // 2 - 3
        dot_color = QColor(state["dot"])
        if self._state == "listening" and not self._blink_on:
            dot_color.setAlpha(60)

        glow = QRadialGradient(dot_x, dot_y, 10)
        glow_color = QColor(state["dot"])
        glow_color.setAlpha(40)
        glow.setColorAt(0, glow_color)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(dot_x, dot_y), 10, 10)

        p.setBrush(QBrush(dot_color))
        p.drawEllipse(QPoint(dot_x, dot_y), 4, 4)

        font = QFont("Inter", 8, QFont.Weight.Medium)
        if not font.exactMatch(): font = QFont("Segoe UI", 8, QFont.Weight.Medium)
        p.setFont(font)
        p.setPen(QColor("#edece8"))
        label = state["label"]
        # Show recording duration
        if self._state == "listening" and self._rec_start:
            elapsed = time.time() - self._rec_start
            label = f"Listening...  {elapsed:.0f}s"
        text_rect = QRect(32, 0, w - 42, h // 2 + 4)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

        # Audio level meter bar (only while listening)
        if self._state == "listening":
            bar_x, bar_y = 32, h // 2 + 5
            bar_w = w - 50
            bar_h = 4
            # Background track
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 255, 255, 20)))
            p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 2, 2)
            # Level fill
            fill_w = int(bar_w * self._audio_level)
            if fill_w > 0:
                level_color = QColor("#ff4422") if self._audio_level > 0.8 else QColor("#2DCE6E") if self._audio_level < 0.5 else QColor("#FFB420")
                p.setBrush(QBrush(level_color))
                p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 2, 2)

        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
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
        self.setStyleSheet("""
            QFrame#HistoryItem {
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.04);
                border-radius: 8px;
            }
            QFrame#HistoryItem:hover {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
            }
            QLabel {
                color: #edece8;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 13px;
                background: transparent;
                border: none;
            }
            QLabel#meta {
                color: #6b6b72;
                font-size: 10px;
            }
            QPushButton {
                background: transparent;
                color: #ff4422;
                border: 1px solid #ff4422;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 68, 34, 0.1);
            }
            QLineEdit {
                background: #1a1a1e;
                border: 1px solid #ff4422;
                border-radius: 4px;
                padding: 4px;
                color: #edece8;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 13px;
            }
        """)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        self.stack = QStackedWidget()

        self.lbl = QLabel(text)
        self.lbl.setWordWrap(True)
        self.lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.stack.addWidget(self.lbl)

        self.editor = QLineEdit(text)
        self.stack.addWidget(self.editor)

        text_col.addWidget(self.stack)

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
        btn_layout.setSpacing(6)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btn_copy.clicked.connect(self._handle_primary)
        btn_layout.addWidget(self.btn_copy)

        self.btn_edit = QPushButton("Fix / Learn")
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btn_edit.clicked.connect(self._handle_secondary)
        btn_layout.addWidget(self.btn_edit)

        main_layout.addLayout(btn_layout)

    def _handle_primary(self):
        if self.stack.currentIndex() == 1:
            # Save mode
            corrected = self.editor.text().strip()
            if corrected and corrected != self.original_text:
                wrong, right = data_manager.learn_correction(self.original_text, corrected)
                if wrong and right:
                    print(f"[Stype] Learned: '{wrong}' -> '{right}'")

                # Update history in datamanager
                for i, entry in enumerate(data_manager.data["history"]):
                    txt = entry["text"] if isinstance(entry, dict) else entry
                    if txt == self.original_text:
                        if isinstance(entry, dict):
                            data_manager.data["history"][i]["text"] = corrected
                        else:
                            data_manager.data["history"][i] = corrected
                        data_manager.save()
                        break

            self.original_text = corrected
            self.lbl.setText(corrected)
            self.stack.setCurrentIndex(0)
            self.btn_edit.setText("Fix / Learn")
            self.btn_copy.setText("Copy")
        else:
            # Copy mode
            pyperclip.copy(self.original_text)
            self.btn_copy.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.btn_copy.setText("Copy"))

    def _handle_secondary(self):
        if self.stack.currentIndex() == 0:
            # Switch to Edit mode
            self.stack.setCurrentIndex(1)
            self.editor.setText(self.original_text)
            self.editor.setFocus()
            self.btn_edit.setText("Cancel")
            self.btn_copy.setText("Save")
        else:
            # Cancel mode
            self.stack.setCurrentIndex(0)
            self.btn_edit.setText("Fix / Learn")
            self.btn_copy.setText("Copy")


# ═══════════════════════════════════════════════════════════
#  MINIMAL BACKGROUND WIDGET
# ═══════════════════════════════════════════════════════════
class PremiumBackgroundWidget(QWidget):
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(0, 0, self.width(), self.height(), QColor("#0a0a0c"))


# ═══════════════════════════════════════════════════════════
#  MAIN WINDOW (DASHBOARD) — Enhanced with tabs
# ═══════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    model_changed = pyqtSignal(str, str)
    settings_changed = pyqtSignal()  # emitted when any setting changes

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stype Dashboard")
        self.setFixedSize(440, 640)

        self.setStyleSheet("""
            QWidget {
                color: #edece8;
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #edece8;
                background: transparent;
            }
            QLabel#muted {
                color: #6b6b72;
                font-size: 11px;
            }
            QLabel#section_title {
                color: #6b6b72;
                font-size: 10px;
                letter-spacing: 1px;
            }
            QFrame#card {
                background-color: rgba(255,255,255,0.025);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 16px;
            }
            QComboBox {
                background-color: #1a1a1e;
                border: 1px solid #272729;
                border-radius: 6px;
                padding: 6px 12px;
                color: #edece8;
                min-height: 26px;
            }
            QComboBox:hover {
                border: 1px solid #333338;
                background-color: #131316;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #6b6b72;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #111114;
                border: 1px solid #272729;
                selection-background-color: #1a1a1e;
                color: #edece8;
                outline: none;
            }
            QPushButton#apply_btn {
                background-color: #ff4422;
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
            }
            QPushButton#apply_btn:hover { background-color: #ff5533; }
            QPushButton#secondary_btn {
                background-color: transparent;
                color: #6b6b72;
                font-weight: 500;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 12px;
            }
            QPushButton#secondary_btn:hover {
                color: #edece8;
                border-color: rgba(255,255,255,0.15);
            }
            QLineEdit#search {
                background: #131316;
                border: 1px solid #272729;
                border-radius: 6px;
                padding: 8px 12px;
                color: #edece8;
                font-size: 12px;
            }
            QLineEdit#search:focus { border-color: #ff4422; }
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: transparent;
                color: #6b6b72;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 500;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #edece8;
                border-bottom: 2px solid #edece8;
            }
            QTabBar::tab:hover { color: #edece8; }
            QCheckBox {
                color: #edece8;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px; height: 16px;
                border-radius: 4px;
                border: 1px solid #333338;
                background: #1a1a1e;
            }
            QCheckBox::indicator:checked {
                background: #ff4422;
                border-color: #ff4422;
            }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                border: none; background: rgba(255,255,255,0.02);
                width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.15); border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.25); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)

        central = PremiumBackgroundWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(28, 28, 28, 20)
        main_layout.setSpacing(16)

        # ── Header
        header = QHBoxLayout()
        title = QLabel("Stype Dashboard")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        header.addWidget(title)
        self.status_label = QLabel("Loading Model...")
        self.status_label.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        self.status_label.setStyleSheet("color: #FFA500;")
        header.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(header)

        # ── Tabs
        tabs = QTabWidget()
        main_layout.addWidget(tabs, stretch=1)

        # ═══ TAB 1: Engine Settings
        engine_tab = QWidget()
        engine_tab.setStyleSheet("background: transparent;")
        el = QVBoxLayout(engine_tab)
        el.setContentsMargins(0, 16, 0, 0)
        el.setSpacing(14)

        def make_row(label_text, widget):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Inter", 11))
            row.addWidget(lbl)
            row.addWidget(widget)
            return row

        self.model_combo = QComboBox()
        self.model_combo.addItems(list(MODELS.keys()))
        self.model_combo.setCurrentText(data_manager.get("model"))
        el.addLayout(make_row("Accuracy:", self.model_combo))

        self.device_combo = QComboBox()
        self.device_combo.addItems(["CPU", "GPU (NVIDIA CUDA)"])
        self.device_combo.setCurrentText(data_manager.get("device"))
        el.addLayout(make_row("Processing:", self.device_combo))

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(list(LANGUAGES.keys()))
        self.lang_combo.setCurrentText(data_manager.get("language"))
        el.addLayout(make_row("Language:", self.lang_combo))

        apply_btn = QPushButton("Apply & Reload Engine")
        apply_btn.setObjectName("apply_btn")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._on_apply)
        el.addWidget(apply_btn)

        el.addStretch()
        tabs.addTab(engine_tab, QIcon(os.path.join(DATA_DIR, "engine.svg")), " Engine")

        # ═══ TAB 2: Audio Settings
        audio_tab = QWidget()
        audio_tab.setStyleSheet("background: transparent;")
        al = QVBoxLayout(audio_tab)
        al.setContentsMargins(0, 16, 0, 0)
        al.setSpacing(14)

        self.mic_combo = QComboBox()
        self._populate_mics()
        al.addLayout(make_row("Microphone:", self.mic_combo))

        # Hotkey
        hk_row = QHBoxLayout()
        hk_lbl = QLabel("Hotkey:")
        hk_lbl.setFont(QFont("Inter", 11))
        hk_row.addWidget(hk_lbl)
        self.hotkey_input = QLineEdit(data_manager.get("hotkey"))
        self.hotkey_input.setObjectName("search")
        self.hotkey_input.setPlaceholderText("e.g. ctrl+space")
        hk_row.addWidget(self.hotkey_input)
        al.addLayout(hk_row)

        # Auto-silence
        self.auto_silence_cb = QCheckBox("Auto-stop after silence")
        self.auto_silence_cb.setChecked(data_manager.get("auto_silence"))
        al.addWidget(self.auto_silence_cb)

        silence_row = QHBoxLayout()
        silence_row.addWidget(QLabel("Silence duration:"))
        self.silence_lbl = QLabel(f"{data_manager.get('silence_seconds'):.1f}s")
        self.silence_lbl.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        self.silence_slider = QSlider(Qt.Orientation.Horizontal)
        self.silence_slider.setRange(10, 80)  # 1.0s – 8.0s
        self.silence_slider.setValue(int(data_manager.get("silence_seconds") * 10))
        self.silence_slider.valueChanged.connect(
            lambda v: self.silence_lbl.setText(f"{v/10:.1f}s"))
        silence_row.addWidget(self.silence_slider)
        silence_row.addWidget(self.silence_lbl)
        al.addLayout(silence_row)

        save_audio_btn = QPushButton("Save Audio Settings")
        save_audio_btn.setObjectName("apply_btn")
        save_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_audio_btn.clicked.connect(self._on_save_audio)
        al.addWidget(save_audio_btn)

        al.addStretch()
        tabs.addTab(audio_tab, QIcon(os.path.join(DATA_DIR, "mic.svg")), " Audio")

        # ═══ TAB 3: History
        history_tab = QWidget()
        history_tab.setStyleSheet("background: transparent;")
        hl = QVBoxLayout(history_tab)
        hl.setContentsMargins(0, 12, 0, 0)
        hl.setSpacing(10)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setObjectName("search")
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

        # Load persistent history
        for entry in data_manager.data["history"]:
            item = HistoryItem(entry)
            self.history_layout.addWidget(item)

        self.scroll.setWidget(self.scroll_content)
        hl.addWidget(self.scroll)

        # Action buttons
        btn_row = QHBoxLayout()
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

        tabs.addTab(history_tab, QIcon(os.path.join(DATA_DIR, "history.svg")), " History")

        # ── Footer hint
        hotkey_text = data_manager.get("hotkey").upper().replace("+", " + ")
        hint = QLabel(f"<b>{hotkey_text}</b> to talk. Close this window to run in background.")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

    def _on_apply(self):
        model_name = self.model_combo.currentText()
        model_id = MODELS[model_name]
        device = "cuda" if "GPU" in self.device_combo.currentText() else "cpu"
        data_manager.set("model", model_name)
        data_manager.set("device", self.device_combo.currentText())
        data_manager.set("language", self.lang_combo.currentText())
        self.model_changed.emit(model_id, device)

    def _on_save_audio(self):
        data_manager.set("mic_device", self.mic_combo.currentText())
        data_manager.set("hotkey", self.hotkey_input.text().strip() or "ctrl+space")
        data_manager.set("auto_silence", self.auto_silence_cb.isChecked())
        data_manager.set("silence_seconds", self.silence_slider.value() / 10.0)
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

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export History", "stype_history.txt", "Text Files (*.txt)")
        if path:
            if data_manager.export_history(path):
                self.status_label.setText("Exported!")
                self.status_label.setStyleSheet("color: #2DCE6E;")
                QTimer.singleShot(2000, lambda: self.update_status("ready"))

    def _on_clear_history(self):
        data_manager.clear_history()
        while self.history_layout.count():
            child = self.history_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def update_status(self, state_key):
        state = STATES.get(state_key, STATES["ready"])
        self.status_label.setText(state['label'])
        self.status_label.setStyleSheet(f"color: {state['dot']};")


# ═══════════════════════════════════════════════════════════
#  MAIN ENGINE — Enhanced
# ═══════════════════════════════════════════════════════════
class StypeEngine:
    def __init__(self):
        self.signals = Signals()
        self.model = None
        self.recording = False
        self.processing = False
        self.audio_frames = []
        self._silence_frames = 0  # count of consecutive silent frames
        self._current_hotkey = None

        self.pill = PillOverlay()
        self.dashboard = MainWindow()

        self.dashboard.model_changed.connect(self._reload_model)
        self.dashboard.settings_changed.connect(self._on_settings_changed)
        self.signals.state_changed.connect(self.pill.set_state)
        self.signals.state_changed.connect(self.dashboard.update_status)
        self.signals.transcription_done.connect(self._on_transcription)

        self.tracker = CorrectionTracker(data_manager)

        self._pasted_timer = QTimer()
        self._pasted_timer.setSingleShot(True)
        self._pasted_timer.timeout.connect(lambda: self.signals.state_changed.emit("ready"))

        # Audio stream setup
        self._setup_audio_stream()

        # Hotkey setup
        self._register_hotkey()

        # Tray icon
        qapp = QApplication.instance()
        icon_path = os.path.join(DATA_DIR, "icon.ico")
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
        self.dashboard.show()

        # Load saved model/device
        saved_model = data_manager.get("model")
        model_id = MODELS.get(saved_model, "small.en")
        saved_device = data_manager.get("device")
        device = "cuda" if "GPU" in saved_device else "cpu"
        threading.Thread(target=self._load_model, args=(model_id, device), daemon=True).start()

    def _setup_audio_stream(self):
        """Create or recreate the audio input stream with current mic settings."""
        if hasattr(self, 'stream') and self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass

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

        self.stream = sd.InputStream(
            samplerate=16000,
            channels=1,
            device=device_idx,
            callback=self._audio_callback
        )
        self.stream.start()

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
        self._setup_audio_stream()

    def _audio_callback(self, indata, frames, time_info, status):
        if self.recording:
            self.audio_frames.append(indata.copy())

            # Audio level for pill VU meter
            rms = np.sqrt(np.mean(indata ** 2))
            level = min(1.0, rms / 0.08)  # normalize
            self.pill.set_audio_level(level)

            # Auto-silence detection
            if data_manager.get("auto_silence"):
                silence_threshold = 0.005
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
            self.processing = True
            self.signals.state_changed.emit("processing")
            threading.Thread(target=self._process, daemon=True).start()

    def _toggle(self):
        current_time = time.time()
        if hasattr(self, '_last_toggle') and current_time - self._last_toggle < 0.5:
            return
        self._last_toggle = current_time

        if self.model is None or self.processing:
            return

        if not self.recording:
            self.recording = True
            self.audio_frames = []
            self._silence_frames = 0
            self.signals.state_changed.emit("listening")
            self.tray_icon.setToolTip("Stype — Recording...")
        else:
            self.recording = False
            self.processing = True
            self.signals.state_changed.emit("processing")
            self.tray_icon.setToolTip("Stype — Processing...")
            threading.Thread(target=self._process, daemon=True).start()

    def _load_model(self, model_id, device):
        self.signals.state_changed.emit("loading")
        try:
            compute_type = "float16" if device == "cuda" else "int8"
            self.model = WhisperModel(
                model_id,
                device=device,
                compute_type=compute_type,
                cpu_threads=4,
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
            # Build dynamic prompt with learned vocabulary
            vocab = [v for v in data_manager.data["dictionary"].values() if v.isalpha()]
            prompt = FORMATTING_PROMPT
            if vocab:
                prompt += " Vocabulary: " + ", ".join(list(set(vocab))[:50])

            # Language selection
            lang_name = data_manager.get("language")
            lang_code = LANGUAGES.get(lang_name)

            transcribe_kwargs = dict(
                beam_size=1,
                vad_filter=True,
                condition_on_previous_text=False,
                initial_prompt=prompt
            )
            if lang_code:
                transcribe_kwargs["language"] = lang_code

            segments, _ = self.model.transcribe(audio_data, **transcribe_kwargs)
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
        pyperclip.copy(" " + text)
        for key in hotkey.split("+"):
            try:
                keyboard.release(key.strip())
            except Exception:
                pass
        time.sleep(0.05)
        keyboard.send('ctrl+v')

        self.tracker.start(" " + text)

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
