# 🎙️ Stype

Website Link : https://akasumitlamba.github.io/Stype/

**AI-Powered Speech-to-Text for Windows** _The speed of thought, typed at the speed of sound._

Stype is an offline-first Windows desktop application that uses OpenAI's **Whisper** (via `faster-whisper`) to convert speech into text. Its desktop UI shares the website's warm cream, navy, orange, purple, and yellow visual system, with a compact pill that stays out of the way.

---

## ✨ Features

- **Offline AI Engine:** Powered by `faster-whisper`; audio stays local and is never uploaded for transcription.
- **Native-Language Dictation:** Selected languages are transcribed in their original script; Stype never requests translation.
- **Practical Dashboard:** Website-matched typography, outlined controls, consistent sizing, clear engine status, one-click dictation, settings, and history.
- **Dynamic Pill UI:** A sleek, minimalist floating overlay that shows real-time status (Recording, Processing, Pasted).
- **System Sound Input:** Switch audio capture to Windows playback and use the pill's speaker control to transcribe what is playing locally.
- **Interactive History:** Every transcription is saved in a history list where you can easily copy previous entries with a single click.
- **Explicit Replacements:** Personal dictionary replacements apply deterministically, while vocabulary items only help recognition.
- **Global Hotkey:** A simple `Ctrl + Space` toggle that works across browser, code editor, or Word docs.
- **Privacy First:** The selected open-source model is downloaded once on first launch, then transcription works offline and your voice stays on your machine.

---

## 🚀 Installation (Releases)

1. Head over to the [Releases](https://github.com/akasumitlamba/stype/releases) page.
2. Download the latest `Stype_Setup.exe`.
3. Run the installer.
4. Launch Stype from your Desktop or Start Menu. First launch shows model download percentage and stores the model in `%APPDATA%\Stype\models`; future launches reuse that cache.

Uninstalling Stype removes its downloaded models and the rest of `%APPDATA%\Stype`, including settings, history, and logs, so the speech model does not continue using disk space.

---

## 🛠️ How to Use

1. **Launch:** The **Stype Dashboard** will open, allowing you to choose your AI model accuracy and device (CPU/GPU).
2. **Dictate:** Press `Ctrl + Space` once. A **Listening** pill will appear at the bottom-center of your screen. Enable system sound input when you want the hotkey and speaker pill control to capture Windows playback instead.
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
   python stype.py
   ```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/akasumitlamba/stype/issues).

## 👨‍💻 Author

**akasumitlamba**

- GitHub: [@akasumitlamba](https://github.com/akasumitlamba/)
