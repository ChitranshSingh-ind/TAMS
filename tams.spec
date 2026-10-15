# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Bundle database migrations and configuration
datas = [
    ('alembic.ini', '.'),
    ('migrations', 'migrations'),
    ('app/resources', 'app/resources'),
]

# Hidden imports to ensure SQLAlchemy dialect and Alembic operate properly
hiddenimports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'sqlalchemy',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.dialects.sqlite',
    'alembic',
    'alembic.context',
    'sqlite3',
    'packaging',
    'packaging.version',
    'app.database.init_db',
]

# 1. Main TAMS Application Analysis
a_tams = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'email.test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_tams = PYZ(a_tams.pure, a_tams.zipped_data, cipher=block_cipher)

exe_tams = EXE(
    pyz_tams,
    a_tams.scripts,
    [],
    exclude_binaries=True,
    name='TAMS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# 2. CoachingHelper Companion Analysis
a_helper = Analysis(
    ['coaching_helper_main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'email.test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_helper = PYZ(a_helper.pure, a_helper.zipped_data, cipher=block_cipher)

exe_helper = EXE(
    pyz_helper,
    a_helper.scripts,
    [],
    exclude_binaries=True,
    name='CoachingHelper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# 3. Combined Directory Output (onedir distribution)
coll = COLLECT(
    exe_tams,
    a_tams.binaries,
    a_tams.zipfiles,
    a_tams.datas,
    exe_helper,
    a_helper.binaries,
    a_helper.zipfiles,
    a_helper.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TAMS',
)
