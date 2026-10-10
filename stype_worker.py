"""Crash-isolated faster-whisper worker used by Stype."""

import os
import sys
import io
import shutil
import time
import threading
from multiprocessing.connection import Client


MODEL_REPOSITORIES = {
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "small.en": "Systran/faster-whisper-small.en",
    "tiny.en": "Systran/faster-whisper-tiny.en",
}
MODEL_FILES = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]


def download_model(model_id, download_root, connection):
    """Download one model sequentially and report aggregate byte progress."""
    from huggingface_hub import hf_hub_download, snapshot_download
    from tqdm.auto import tqdm

    class SilentTqdm(tqdm):
        def __init__(self, *args, **kwargs):
            kwargs["disable"] = True
            super().__init__(*args, **kwargs)

    repo_id = MODEL_REPOSITORIES.get(model_id, model_id)
    os.makedirs(download_root, exist_ok=True)
    files = snapshot_download(
        repo_id,
        cache_dir=download_root,
        allow_patterns=MODEL_FILES,
        dry_run=True,
        tqdm_class=SilentTqdm,
    )
    total = max(1, sum(item.file_size for item in files))
    completed = sum(item.file_size for item in files if item.is_cached)
    required = total - completed
    free = shutil.disk_usage(download_root).free
    if free < required + 512 * 1024 * 1024:
        raise RuntimeError(
            f"Not enough free storage for the speech model. "
            f"Need {(required + 512 * 1024 * 1024) / (1024 ** 3):.1f} GB available."
        )
    last_percent = -1
    report_lock = threading.Lock()

    def report(done):
        nonlocal last_percent
        with report_lock:
            percent = min(100, int(done * 100 / total))
            if percent != last_percent:
                last_percent = percent
                connection.send(("download_progress", model_id, percent, done, total))

    report(completed)
    revision = files[0].commit_hash if files else None
    for item in files:
        if not item.is_cached:
            file_base = completed

            class DownloadTqdm(tqdm):
                def __init__(self, *args, **kwargs):
                    kwargs.pop("name", None)
                    kwargs["disable"] = False
                    kwargs["file"] = io.StringIO()
                    super().__init__(*args, **kwargs)

                def update(self, amount=1):
                    result = super().update(amount)
                    report(min(file_base + int(self.n), file_base + item.file_size))
                    return result

            hf_hub_download(
                repo_id,
                item.filename,
                revision=revision,
                cache_dir=download_root,
                tqdm_class=DownloadTqdm,
            )
        completed += 0 if item.is_cached else item.file_size
        report(completed)

    model_dir = snapshot_download(
        repo_id,
        revision=revision,
        cache_dir=download_root,
        allow_patterns=MODEL_FILES,
        local_files_only=True,
        tqdm_class=SilentTqdm,
    )
    report(total)
    return model_dir


def main():
    if len(sys.argv) != 8:
        raise SystemExit("invalid Stype engine arguments")
    port = int(sys.argv[1])
    authkey = bytes.fromhex(sys.argv[2])
    model_path = sys.argv[3] or None
    model_id = sys.argv[4]
    device = sys.argv[5]
    cpu_threads = int(sys.argv[6])
    download_root = sys.argv[7]
    connection = Client(("127.0.0.1", port), authkey=authkey)
    try:
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        sys.modules["torch"] = None
        from faster_whisper import WhisperModel

        resolved_model = model_path
        if not resolved_model:
            last_error = None
            for attempt in range(1, 4):
                try:
                    resolved_model = download_model(model_id, download_root, connection)
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt == 3 or "Not enough free storage" in str(exc):
                        raise
                    connection.send(("download_retry", model_id, attempt, str(exc)))
                    time.sleep(attempt * 2)
            if not resolved_model:
                raise RuntimeError(str(last_error or "Model download failed"))
        connection.send(("model_loading", model_id))
        try:
            model = WhisperModel(
                resolved_model,
                device=device,
                compute_type="float16" if device == "cuda" else "int8",
                cpu_threads=cpu_threads,
                num_workers=1,
            )
        except Exception:
            if device != "cuda":
                raise
            connection.send(("device_fallback", model_id, "cpu"))
            model = WhisperModel(
                resolved_model,
                device="cpu",
                compute_type="int8",
                cpu_threads=cpu_threads,
                num_workers=1,
            )
        connection.send(("model_ready", model_id, ""))
        while True:
            command = connection.recv()
            if command[0] == "stop":
                break
            if command[0] == "transcribe":
                _, process_id, audio, kwargs, prompt = command
                try:
                    segments, _ = model.transcribe(audio, **kwargs)
                    raw_text = "".join(segment.text for segment in segments).strip()
                    connection.send(("transcription", process_id, raw_text, prompt, kwargs.get("language")))
                except Exception as exc:
                    connection.send(("transcription_error", process_id, str(exc)))
    except BaseException as exc:
        try:
            connection.send(("model_error", model_id, str(exc)))
        except Exception:
            pass
    finally:
        connection.close()


if __name__ == "__main__":
    main()
