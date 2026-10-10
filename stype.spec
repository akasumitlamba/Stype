# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

faster_whisper_data = collect_data_files('faster_whisper')

a = Analysis(
    ['stype.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
    ],
    hiddenimports=[
        # Audio backends
        'sounddevice',
        'soundcard',
        'soundcard.mediafoundation',
        # Numpy & numerics
        'numpy',
        'numpy.core._multiarray_umath',
        # ctypes (needed by keyboard library on Windows)
        '_ctypes',
        'ctypes',
        'ctypes.util',
        'ctypes.wintypes',
        # Windows clipboard fallback
        'win32clipboard',
        'win32con',
        # PyQt6 internals
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Keep excludes lean — don't exclude anything faster_whisper might need
    excludes=['tensorflow', 'torch', 'scipy', 'pandas', 'matplotlib', 'tkinter', 'unittest'],
    noarchive=False,
    optimize=0,
)

# The Codex workspace runtime adds Poppler/libheif folders to PATH. PyInstaller
# must not collect those unrelated DLLs (notably icuuc.dll), which collide with
# Qt at startup in the frozen app.
a.binaries = [
    entry for entry in a.binaries
    if '\\.cache\\codex-runtimes\\' not in entry[1].lower()
]

worker = Analysis(
    ['stype_worker.py'],
    pathex=[],
    binaries=[],
    datas=faster_whisper_data,
    hiddenimports=[
        'faster_whisper',
        'huggingface_hub',
        'tokenizers',
        'onnxruntime',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'tensorflow', 'torch', 'scipy', 'pandas', 'matplotlib', 'tkinter', 'unittest', 'pytest'],
    noarchive=False,
    optimize=0,
)
worker.binaries = [
    entry for entry in worker.binaries
    if '\\.cache\\codex-runtimes\\' not in entry[1].lower()
]
pyz = PYZ(a.pure)
worker_pyz = PYZ(worker.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Stype',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX disabled: known to corrupt PyQt6/ONNX DLLs on Windows
    console=False,      # Windowed app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
    contents_directory='_internal',
)
worker_exe = EXE(
    worker_pyz,
    worker.scripts,
    [],
    exclude_binaries=True,
    name='StypeEngine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
    contents_directory='_internal',
)
coll = COLLECT(
    exe,
    worker_exe,
    a.binaries,
    a.datas,
    worker.binaries,
    worker.datas,
    strip=False,
    upx=False,          # UPX disabled here too
    upx_exclude=[],
    name='Stype',
)
