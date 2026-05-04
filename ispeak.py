import keyboard
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import pyperclip # Run 'pip install pyperclip' in your cmd
import pyautogui
import threading
import os

# Create a folder for the model so it stays there forever
model_path = "./whisper_model"

print("Loading Engine... (Fast local boot)")
# 'local_files_only=False' the first time, then change to 'True' after it works once
model = WhisperModel("small.en", device="cpu", compute_type="int8", 
                     cpu_threads=4, download_root=model_path)

print("READY! CTRL+SPACE to talk.")

recording = False
audio_frames = []

def process_and_type():
    global audio_frames, recording
    recording = False
    if not audio_frames: return

    print("Transcribing...")
    audio_data = np.concatenate(audio_frames, axis=0).flatten()
    audio_frames = []

    segments, _ = model.transcribe(audio_data, beam_size=1, vad_filter=True)
    result_text = "".join([s.text for s in segments]).strip()

    if result_text:
        print(f"Result: {result_text}")
        # CLIPBOARD FIX: Copy and Paste instead of typing
        pyperclip.copy(" " + result_text)
        pyautogui.hotkey('ctrl', 'v') 

def toggle():
    global recording
    if not recording:
        recording = True
        print("Listening...")
    else:
        print("Processing...")
        threading.Thread(target=process_and_type).start()

keyboard.add_hotkey('ctrl+space', toggle)

with sd.InputStream(samplerate=16000, channels=1, callback=lambda i, f, t, s: audio_frames.append(i.copy()) if recording else None):
    keyboard.wait()