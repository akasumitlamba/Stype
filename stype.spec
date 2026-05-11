# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['stype.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('whisper_model/models--Systran--faster-whisper-small.en', 'whisper_model/models--Systran--faster-whisper-small.en'),
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
        # faster-whisper internals
        'huggingface_hub',
        'tokenizers',
        'faster_whisper',
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
pyz = PYZ(a.pure)

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
    contents_directory='.',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,          # UPX disabled here too
    upx_exclude=[],
    name='Stype',
)
