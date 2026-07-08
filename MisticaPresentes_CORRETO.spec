# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
ICON_FILE = os.path.abspath(os.path.join('assets', 'mistica_xamanico_moderno.ico'))
ICON_PATH = ICON_FILE if os.path.exists(ICON_FILE) else None

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

def incluir_pasta(origem, destino):
    itens = []
    if not os.path.exists(origem):
        return itens
    ignorar_dirs = {'__pycache__', '.gradle', 'build', 'dist'}
    ignorar_arquivos = {'local.properties'}
    ignorar_ext = {'.pyc', '.pyo'}
    for raiz, dirs, arquivos in os.walk(origem):
        dirs[:] = [d for d in dirs if d not in ignorar_dirs]
        rel = os.path.relpath(raiz, origem)
        alvo = destino if rel == '.' else os.path.join(destino, rel)
        for nome in arquivos:
            if nome in ignorar_arquivos or os.path.splitext(nome)[1].lower() in ignorar_ext:
                continue
            itens.append((os.path.join(raiz, nome), alvo))
    return itens


datas = []
for origem, destino in [
    ('mistica_presentes.py', '.'),
    ('auto_updater.py', '.'),
    ('app_version.py', '.'),
    ('app_runtime_patch.py', '.'),
    ('app_pagamento_misto_patch.py', '.'),
    ('app_sync_pagamento_misto_payload_patch.py', '.'),
    ('app_caixa_fechamento_avancado_patch.py', '.'),
    ('app_backup_inicializacao_patch.py', '.'),
    ('app_frajola_patch.py', '.'),
    ('app_painel_guard_patch.py', '.'),
    ('app_sync_status_patch.py', '.'),
    ('app_scroll_patch.py', '.'),
    ('config.py', '.'),
    ('assets', 'assets'),
]:
    if os.path.isdir(origem):
        datas += incluir_pasta(origem, destino)
    elif os.path.exists(origem):
        datas.append((origem, destino))

for origem, destino in [
    ('database', 'database'),
    ('services', 'services'),
    ('isis', 'isis'),
    ('backend', 'backend'),
    ('painel', 'painel'),
    ('tools', 'tools'),
    ('scripts', 'scripts'),
    ('docs', 'docs'),
]:
    datas += incluir_pasta(origem, destino)

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
    icon=ICON_PATH,
)
