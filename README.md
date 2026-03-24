# 🎙️ Stype

Website Link : https://akasumitlamba.github.io/Stype/

**AI-Powered Speech-to-Text for Windows** _The speed of thought, typed at the speed of sound._

Stype is a lightweight, offline-first Windows desktop application that uses OpenAI's **Whisper** (via `faster-whisper`) to convert your speech into text instantly. It sits in your system tray, listens for a global hotkey, and pastes your dictated words directly into any active input field—browser, code editor, or Word doc.

---

## ✨ Features

- **Offline AI Engine:** Powered by `faster-whisper` (base.en) for high accuracy without sending your data to the cloud.
- **Dynamic Pill UI:** A sleek, minimalist floating overlay that shows real-time status (Recording, Processing, Pasted).
- **Global Hotkey:** Fully customizable shortcut (default: `Ctrl + Space`) that works across all Windows applications.
- **Smart Automation:** Automatically handles capitalization, punctuation, and simulates a `Ctrl + V` to paste your text.
- **Low Resource Usage:** Optimized for efficiency on CPU-only systems (4GB RAM minimum).
- **Privacy First:** No internet connection required. Your voice stays on your machine.

---

## 🚀 Installation

1. Head over to the [Releases](https://github.com/akasumitlamba/stype/releases) page.
2. Download the latest `Stype_Setup_v1.0.0.exe`.
3. Run the installer.
   - **Note:** Since this is an independent open-source project, Windows may show a "Protected your PC" warning. Click **More Info** > **Run Anyway**.
4. Launch Stype from your Desktop or Start Menu.

---

## 🛠️ How to Use

1. **Launch:** Look for the 🎙️ icon in your System Tray (bottom right).
2. **Dictate:** Press `Ctrl + Space` once. A **Recording** pill will appear at the bottom of your screen.
3. **Finish:** Press `Ctrl + Space` again. The pill will change to **Processing**, and your text will be pasted into your active window.
4. **Customize:** Right-click the tray icon and select **Settings** to change your hotkey or pause the app.

---

## 💻 Tech Stack

- **Language:** Python 3.13
- **GUI Framework:** PySide6 (Qt for Python)
- **AI Engine:** `faster-whisper` (CTranslate2)
- **Audio:** `sounddevice` / `numpy`
- **Automation:** `keyboard`, `pyperclip`
- **Installer:** Inno Setup

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/akasumitlamba/stype/issues).

## 👨‍💻 Author

**akasumitlamba**

- GitHub: [@akasumitlamba](https://github.com/akasumitlamba/)

---

### 📝 Developer Setup (For Local Build)

If you want to build Stype from source:

1. **Clone the repo:**
   ```bash
   git clone [https://github.com/akasumitlamba/stype.git](https://github.com/akasumitlamba/stype.git)
   cd stype
   ```
