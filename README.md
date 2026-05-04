# 🎙️ Stype

Website Link : https://akasumitlamba.github.io/Stype/

**AI-Powered Speech-to-Text for Windows** _The speed of thought, typed at the speed of sound._

Stype is a lightweight, offline-first Windows desktop application that uses OpenAI's **Whisper** (via `faster-whisper`) to convert your speech into text instantly. It features a premium, modern dashboard and a minimalist floating pill overlay that works across all Windows applications.

---

## ✨ Features

- **Offline AI Engine:** Powered by `faster-whisper` for high accuracy without sending your data to the cloud.
- **Premium Dashboard:** A modern UI with mesh gradients and a glassmorphism design for managing settings and history.
- **Dynamic Pill UI:** A sleek, minimalist floating overlay that shows real-time status (Recording, Processing, Pasted).
- **Interactive History:** Every transcription is saved in a history list where you can easily copy previous entries with a single click.
- **Smart Replacements:** A built-in context algorithm that automatically fixes common homophone errors (e.g., "out words" -> "outwards").
- **Global Hotkey:** A simple `Ctrl + Space` toggle that works across browser, code editor, or Word docs.
- **Privacy First:** No internet connection required. Your voice stays on your machine.

---

## 🚀 Installation (Releases)

1. Head over to the [Releases](https://github.com/akasumitlamba/stype/releases) page.
2. Download the latest `Stype_Setup_vX.X.X.exe`.
3. Run the installer.
4. Launch Stype from your Desktop or Start Menu.

---

## 🛠️ How to Use

1. **Launch:** The **Stype Dashboard** will open, allowing you to choose your AI model accuracy and device (CPU/GPU).
2. **Dictate:** Press `Ctrl + Space` once. A **Listening** pill will appear at the bottom-center of your screen.
3. **Finish:** Press `Ctrl + Space` again. The pill will change to **Processing**, and your text will be pasted into your active window.
4. **History:** Open the Dashboard to see your recent transcriptions and copy them back to your clipboard if needed.

---

## 💻 Tech Stack

- **Language:** Python 3.13
- **GUI Framework:** PyQt6
- **AI Engine:** `faster-whisper` (CTranslate2)
- **Audio:** `sounddevice` / `numpy`
- **Automation:** `keyboard`, `pyperclip`

---

## 📝 Developer Setup

If you want to run Stype from source:

1. **Clone the repo:**
   ```bash
   git clone https://github.com/akasumitlamba/stype.git
   cd stype
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the App:**
   ```bash
   python ispeak_gui.py
   ```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/akasumitlamba/stype/issues).

## 👨‍💻 Author

**akasumitlamba**

- GitHub: [@akasumitlamba](https://github.com/akasumitlamba/)
