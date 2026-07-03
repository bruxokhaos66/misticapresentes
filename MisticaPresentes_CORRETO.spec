# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = []
for pacote in [
    'customtkinter',
    'database',
    'services',
    'isis',
    'backend',
    'PIL',
    'ddgs',
    'httpx',
    'speech_recognition',
    'pyttsx3',
    'uvicorn',
    'fastapi',
]:
    try:
        hiddenimports += collect_submodules(pacote)
    except Exception:
        pass

datas = [
    ('mistica_presentes.py', '.'),
    ('app_runtime_patch.py', '.'),
    ('app_frajola_patch.py', '.'),
    ('app_sync_status_patch.py', '.'),
    ('app_scroll_patch.py', '.'),
    ('config.py', '.'),
    ('database', 'database'),
    ('services', 'services'),
    ('isis', 'isis'),
    ('backend', 'backend'),
    ('painel', 'painel'),
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MisticaPresentes_CORRETO',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
