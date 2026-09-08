# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

from pathlib import Path
import shutil

block_cipher = None
project_root = Path(SPECPATH)
audio_binaries = []
for name in ('ffmpeg.exe', 'ffprobe.exe', 'fpcalc.exe'):
    local_binary = project_root / 'bin' / name
    resolved = str(local_binary) if local_binary.is_file() else shutil.which(name)
    if not resolved:
        raise RuntimeError(f'Missing build dependency: {name}. Place it in bin/ or PATH.')
    audio_binaries.append((resolved, 'bin'))

# Ensure bin directory (fpcalc, ffmpeg, ffprobe) and app_icon are included in the package
datas = [
    ('app_icon.png', '.') if os.path.exists('app_icon.png') else ('app_icon.ico', '.'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtMultimedia',
    'PyQt6.QtMultimediaWidgets',
    'qtawesome',
    'pygame',
    'pygame.mixer',
    'mutagen',
    'mutagen.mp3',
    'mutagen.flac',
    'mutagen.oggvorbis',
    'mutagen.mp4',
    'mutagen.wave',
    'numpy',
    'scipy',
    'rich',
    'psutil',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=audio_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'torchaudio',
        'tensorflow', 'tensorboard', 'keras',
        'cv2', 'PIL', 'Pillow',
        'pandas', 'scipy.spatial.transform',
        'matplotlib', 'tkinter', 'test', 'unittest',
        'PyQt5', 'PySide2', 'PySide6',
        'IPython', 'jupyter', 'notebook',
        'sklearn', 'scikit-learn',
        'yt_dlp', 'grpc', 'h5py'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AudioDuplicateDetector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No terminal window popup for standard users
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico' if os.path.exists('app_icon.ico') else None,
)
