"""Real model-worker smoke test. Usage: python tests/smoke_engine.py path/to/test.wav"""

import os
import subprocess
import sys
import time
import wave
from multiprocessing.connection import Listener

import numpy as np


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT, "whisper_model", "faster-whisper-large-v3-turbo")


def read_wav(path):
    with wave.open(path, "rb") as wav:
        channels = wav.getnchannels()
        sample_rate = wav.getframerate()
        width = wav.getsampwidth()
        raw = wav.readframes(wav.getnframes())
    if width != 2:
        raise ValueError("smoke test expects 16-bit PCM WAV")
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if sample_rate != 16_000:
        duration = len(audio) / sample_rate
        audio = np.interp(
            np.linspace(0, duration, round(duration * 16_000), endpoint=False),
            np.linspace(0, duration, len(audio), endpoint=False),
            audio,
        ).astype(np.float32)
    return audio


def main(wav_path, worker_path=None):
    load_started = time.perf_counter()
    authkey = os.urandom(24)
    listener = Listener(("127.0.0.1", 0), authkey=authkey)
    port = listener.address[1]
    command = ([os.path.abspath(worker_path)] if worker_path else [sys.executable, os.path.join(ROOT, "stype_worker.py")]) + [
        str(port),
        authkey.hex(),
        MODEL_PATH,
        "large-v3-turbo",
        "cpu",
        "8",
        os.path.join(ROOT, "whisper_model"),
    ]
    process = subprocess.Popen(command)
    connection = listener.accept()
    listener.close()
    try:
        while True:
            ready = connection.recv()
            if ready[0] == "model_ready":
                break
            if ready[0] not in ("download_progress", "download_retry", "model_loading"):
                raise RuntimeError(f"worker failed: {ready}")
        load_seconds = time.perf_counter() - load_started
        transcription_started = time.perf_counter()
        connection.send((
            "transcribe",
            1,
            read_wav(wav_path),
            {
                "beam_size": 5,
                "vad_filter": True,
                "condition_on_previous_text": False,
                "task": "transcribe",
                "multilingual": True,
                "hotwords": "Stype",
                "language": "en",
                "temperature": 0,
                "repetition_penalty": 1.12,
                "no_repeat_ngram_size": 3,
                "hallucination_silence_threshold": 1.0,
            },
            "Vocabulary: Stype",
        ))
        result = connection.recv()
        if result[0] != "transcription":
            raise RuntimeError(f"transcription failed: {result}")
        print(result[2])
        print(
            f"Model ready in {load_seconds:.2f}s; transcription completed in "
            f"{time.perf_counter() - transcription_started:.2f}s"
        )
    finally:
        try:
            connection.send(("stop",))
        except Exception:
            pass
        connection.close()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: python tests/smoke_engine.py path/to/test.wav [path/to/StypeEngine.exe]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
