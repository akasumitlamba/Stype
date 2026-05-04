"""
Stype — Smart Voice Dictation Engine
A polished, user-friendly speech-to-text tool with a premium floating pill overlay and dashboard.
"""
import sys
import re
import time
import threading
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
from faster_whisper import WhisperModel

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QObject, QTimer, QPropertyAnimation,
    QRect, QPoint
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush,
    QRadialGradient, QCursor, QPainterPath, QPalette, QLinearGradient
)

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
    "pasted":     {"label": "Pasted",      "dot": "#2DCE6E", "border": "rgba(45,206,110,0.25)"},
}

FORMATTING_PROMPT = (
    "This is a highly accurate, professionally formatted transcription. "
    "It uses proper punctuation: commas, periods, question marks, and exclamation marks. "
    "When the speaker lists items, they are formatted as a bullet list:\n"
    "- First item\n- Second item\n- Third item\n"
    "Sentences are properly capitalized."
)

SMART_REPLACEMENTS = {
    r'\bout words\b': 'outwards',
    r'\bin words\b': 'inwards',
    r'\bstype\b': 'Stype',
}

# ═══════════════════════════════════════════════════════════
#  SIGNALS
# ═══════════════════════════════════════════════════════════
class Signals(QObject):
    state_changed = pyqtSignal(str)          
    transcription_done = pyqtSignal(str)     
    model_progress = pyqtSignal(str)         


# ═══════════════════════════════════════════════════════════
#  POST-PROCESSOR
# ═══════════════════════════════════════════════════════════
def post_process(text: str) -> str:
    text = text.strip()
    if not text:
        return text

    # Smart Context Replacements (Algorithm)
    for pattern, replacement in SMART_REPLACEMENTS.items():
        # Use regex to replace whole words only, preserving case natively handled by the user's speech mostly
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

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
#  FLOATING PILL OVERLAY
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
        # Made pill narrower as requested
        self.setFixedSize(105, 34)
        
        self._state = "loading"
        self._drag_pos = None
        
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._do_hide)
        
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(300)
        
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_tick)
        self._blink_timer.start(600)
        self._blink_on = True
        
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.left() + (screen.width() - self.width()) // 2,
                  screen.bottom() - self.height() - 60)
        
    def _do_hide(self):
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.start()

    def set_state(self, state_key: str):
        self._state = state_key
        
        if self.windowOpacity() < 1.0:
            self._opacity_anim.setEndValue(1.0)
            self._opacity_anim.start()
            
        if state_key == "listening":
            self._blink_timer.start(600)
            self._hide_timer.stop()
        else:
            self._blink_timer.stop()
            self._blink_on = True
            
        if state_key == "ready":
            self._hide_timer.start(4000)
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
        
        bg_color = QColor(18, 18, 22, 220)
        p.fillPath(path, QBrush(bg_color))
        
        border_col = QColor(state["border"])
        border_col.setAlpha(160)
        p.setPen(QPen(border_col, 1.5))
        p.drawPath(path)
        
        highlight = QPen(QColor(255, 255, 255, 12), 1.0)
        p.setPen(highlight)
        p.drawLine(int(h / 2), 3, int(w - h / 2), 3)
        
        dot_x, dot_y = 16, h // 2
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
        text_rect = QRect(28, 0, w - 36, h)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, state["label"])
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
#  HISTORY ITEM WIDGET
# ═══════════════════════════════════════════════════════════
class HistoryItem(QFrame):
    def __init__(self, text):
        super().__init__()
        self.text = text
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
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(lbl, stretch=1)
        
        self.btn = QPushButton("Copy")
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self._copy)
        self.btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.btn, alignment=Qt.AlignmentFlag.AlignTop)
        
    def _copy(self):
        pyperclip.copy(self.text)
        self.btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self.btn.setText("Copy"))


# ═══════════════════════════════════════════════════════════
#  PREMIUM BACKGROUND WIDGET
# ═══════════════════════════════════════════════════════════
class PremiumBackgroundWidget(QWidget):
    """Draws the beautiful mesh gradient blobs from style.css"""
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        
        # Base Dark Background
        p.fillRect(0, 0, w, h, QColor("#0a0a0c"))
        
        # Blob 1: Orange at top left
        grad1 = QRadialGradient(w * 0.2, h * 0.3, w * 0.7)
        grad1.setColorAt(0, QColor(255, 68, 34, 18))
        grad1.setColorAt(1, QColor(255, 68, 34, 0))
        p.fillRect(0, 0, w, h, QBrush(grad1))
        
        # Blob 2: Purple at top right
        grad2 = QRadialGradient(w * 0.8, h * 0.1, w * 0.6)
        grad2.setColorAt(0, QColor(120, 80, 255, 13))
        grad2.setColorAt(1, QColor(120, 80, 255, 0))
        p.fillRect(0, 0, w, h, QBrush(grad2))


# ═══════════════════════════════════════════════════════════
#  MAIN WINDOW (DASHBOARD)
# ═══════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    model_changed = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stype Dashboard")
        self.setFixedSize(450, 650)
        
        # Global CSS resets
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
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
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
            QPushButton#apply_btn:hover {
                background-color: #ff5533;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255,255,255,0.02);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15);
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,0.25);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        central = PremiumBackgroundWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 32, 28, 24)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Stype Dashboard")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        self.status_label = QLabel("Loading Model...")
        self.status_label.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        self.status_label.setStyleSheet("color: #FFA500;")
        header_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header_layout)
        
        # Settings Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(16)
        
        settings_title = QLabel("Engine Settings")
        settings_title.setFont(QFont("Inter", 11, QFont.Weight.DemiBold))
        card_layout.addWidget(settings_title)

        m_layout = QHBoxLayout()
        m_lbl = QLabel("Accuracy:")
        m_lbl.setFont(QFont("Inter", 10))
        m_layout.addWidget(m_lbl)
        self.model_combo = QComboBox()
        self.model_combo.addItems(list(MODELS.keys()))
        self.model_combo.setCurrentText("Balanced (Small)")
        m_layout.addWidget(self.model_combo)
        card_layout.addLayout(m_layout)

        d_layout = QHBoxLayout()
        d_lbl = QLabel("Processing:")
        d_lbl.setFont(QFont("Inter", 10))
        d_layout.addWidget(d_lbl)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["CPU", "GPU (NVIDIA CUDA)"])
        d_layout.addWidget(self.device_combo)
        card_layout.addLayout(d_layout)

        apply_btn = QPushButton("Apply & Reload")
        apply_btn.setObjectName("apply_btn")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._on_apply)
        card_layout.addWidget(apply_btn)
        
        layout.addWidget(card)
        
        # Log Section
        log_lbl = QLabel("Recent Transcriptions:")
        log_lbl.setFont(QFont("Inter", 11, QFont.Weight.DemiBold))
        layout.addWidget(log_lbl)
        
        # Premium Scroll Area for History
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        
        self.history_layout = QVBoxLayout(self.scroll_content)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_layout.setContentsMargins(0, 0, 12, 0)
        self.history_layout.setSpacing(10)
        
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)
        
        hint = QLabel("<b>CTRL + SPACE</b> to talk. Close this window to run in background.")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        
    def _on_apply(self):
        model_name = self.model_combo.currentText()
        model_id = MODELS[model_name]
        device = "cuda" if "GPU" in self.device_combo.currentText() else "cpu"
        self.model_changed.emit(model_id, device)

    def update_status(self, state_key):
        state = STATES.get(state_key, STATES["ready"])
        self.status_label.setText(state['label'])
        self.status_label.setStyleSheet(f"color: {state['dot']};")


# ═══════════════════════════════════════════════════════════
#  MAIN ENGINE
# ═══════════════════════════════════════════════════════════
class StypeEngine:
    def __init__(self):
        self.signals = Signals()
        self.model = None
        self.recording = False
        self.processing = False
        self.audio_frames = []
        
        self.pill = PillOverlay()
        self.dashboard = MainWindow()
        
        self.dashboard.model_changed.connect(self._reload_model)
        self.signals.state_changed.connect(self.pill.set_state)
        self.signals.state_changed.connect(self.dashboard.update_status)
        self.signals.transcription_done.connect(self._on_transcription)
        
        self._pasted_timer = QTimer()
        self._pasted_timer.setSingleShot(True)
        self._pasted_timer.timeout.connect(lambda: self.signals.state_changed.emit("ready"))
        
        self.stream = sd.InputStream(
            samplerate=16000,
            channels=1,
            callback=self._audio_callback
        )
        self.stream.start()
        
        keyboard.add_hotkey('ctrl+space', self._toggle)
        
        self.pill.show()
        self.dashboard.show()
        
        threading.Thread(target=self._load_model, args=("small.en", "cpu"), daemon=True).start()
    
    def _audio_callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_frames.append(indata.copy())
    
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
            self.signals.state_changed.emit("listening")
        else:
            self.recording = False
            self.processing = True
            self.signals.state_changed.emit("processing")
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
                download_root="./whisper_model"
            )
            self.signals.state_changed.emit("ready")
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
            return
        
        audio_data = np.concatenate(self.audio_frames, axis=0).flatten()
        self.audio_frames = []
        
        try:
            # Important: condition_on_previous_text=False prevents Whisper stutter/loops!
            segments, _ = self.model.transcribe(
                audio_data,
                beam_size=1,
                vad_filter=True,
                condition_on_previous_text=False,
                initial_prompt=FORMATTING_PROMPT
            )
            raw_text = "".join([s.text for s in segments]).strip()
            
            if raw_text:
                final_text = post_process(raw_text)
                self.signals.transcription_done.emit(final_text)
            else:
                self.signals.state_changed.emit("ready")
                self.processing = False
                
        except Exception as e:
            print(f"[Stype] Transcription error: {e}")
            self.signals.state_changed.emit("ready")
            self.processing = False
    
    def _on_transcription(self, text):
        # Insert premium history item
        item = HistoryItem(text)
        self.dashboard.history_layout.insertWidget(0, item)
        
        # Paste safely
        pyperclip.copy(" " + text)
        keyboard.release('ctrl')
        keyboard.release('space')
        time.sleep(0.05)
        keyboard.send('ctrl+v')
        
        self.signals.state_changed.emit("pasted")
        self._pasted_timer.start(2000)
        self.processing = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    engine = StypeEngine()
    sys.exit(app.exec())
