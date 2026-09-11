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

# Ensure the app icon is included. PyInstaller's PyQt6 hooks collect the Qt
# libraries and platform plugins required by the imported modules.
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

# The managed build runtime exposes Poppler/libheif DLL directories globally.
# Never package their ICU or Windows API-set shims: they shadow the compatible
# Windows system libraries and make PyQt6 fail with WinError 127 at startup.
system_runtime_names = {'icu.dll', 'icuuc.dll', 'ucrtbase.dll'}
a.binaries[:] = [
    entry for entry in a.binaries
    if Path(entry[0]).name.lower() not in system_runtime_names
    and not Path(entry[0]).name.lower().startswith('icudt')
    and not Path(entry[0]).name.lower().startswith('api-ms-win-')
]

# _ssl must use the OpenSSL build shipped with this Python runtime, never a
# same-named Poppler copy that happened to be visible while resolving DLLs.
python_dll_dir = Path(sys.base_prefix) / 'DLLs'
python_runtime_dlls = {
    name: python_dll_dir / name
    for name in ('libssl-3-x64.dll', 'libcrypto-3-x64.dll')
}
a.binaries[:] = [
    (entry[0], str(python_runtime_dlls[Path(entry[0]).name.lower()]), entry[2])
    if Path(entry[0]).name.lower() in python_runtime_dlls
       and python_runtime_dlls[Path(entry[0]).name.lower()].is_file()
    else entry
    for entry in a.binaries
]

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
