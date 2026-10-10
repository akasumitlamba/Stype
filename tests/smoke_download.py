"""Verify that a packaged StypeEngine can download and load a Hub model."""

import os
import subprocess
import sys
import tempfile
import shutil
from multiprocessing.connection import Listener


def main(worker_path):
    cache_root = tempfile.mkdtemp(prefix="stype-packaged-download-smoke-")
    authkey = os.urandom(24)
    listener = Listener(("127.0.0.1", 0), authkey=authkey)
    command = ([sys.executable, worker_path] if worker_path.lower().endswith(".py") else [worker_path])
    process = subprocess.Popen(
        command + [
            str(listener.address[1]),
            authkey.hex(),
            "",
            "tiny.en",
            "cpu",
            "4",
            cache_root,
        ]
    )
    connection = listener.accept()
    listener.close()
    try:
        progress = []
        while True:
            message = connection.recv()
            if message[0] == "download_progress":
                progress.append(message[2])
            elif message[0] == "model_loading":
                continue
            elif message[0] == "model_ready":
                break
            else:
                raise RuntimeError(f"download smoke test failed: {message}")
        if not progress or progress[-1] != 100 or progress != sorted(progress):
            raise RuntimeError(f"invalid download progress: {progress}")
        if not any(0 < value < 100 for value in progress):
            raise RuntimeError(f"download did not report intermediate progress: {progress}")
        print(f"Downloaded model is ready after {len(progress)} progress updates")
    finally:
        try:
            connection.send(("stop",))
        except Exception:
            pass
        connection.close()
        process.wait(timeout=10)
        shutil.rmtree(cache_root, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python tests/smoke_download.py path/to/StypeEngine.exe")
    main(os.path.abspath(sys.argv[1]))
