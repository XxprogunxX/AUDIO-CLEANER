"""Verify actual PyInstaller archive entries instead of byte substrings."""
import argparse
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader


def check_archive(path):
    archive = CArchiveReader(str(path))
    entries = {name.replace(chr(92), '/').lower() for name in archive.toc}
    required = {f'bin/{name}.exe' for name in ('ffmpeg', 'ffprobe', 'fpcalc')} | {
        'pyqt6/qtwidgets.pyd',
        'pyqt6/qt6/bin/qt6widgets.dll',
        'pyqt6/qt6/plugins/platforms/qwindows.dll',
    }
    missing = required - entries
    databases = {name for name in entries if name.endswith(('.db', '.sqlite', '.sqlite3'))}
    contaminated_dlls = {
        name for name in entries
        if Path(name).name in {'icu.dll', 'icuuc.dll', 'ucrtbase.dll'}
        or Path(name).name.startswith('icudt')
        or Path(name).name.startswith('api-ms-win-')
    }
    if missing or databases or contaminated_dlls:
        raise RuntimeError(
            f'Invalid package: missing={sorted(missing)}, databases={sorted(databases)}, '
            f'foreign_system_dlls={sorted(contaminated_dlls)}'
        )
    print('Verified: GUI/audio binaries bundled; no user databases or foreign system DLLs.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path,
                        default=Path(__file__).resolve().parents[1]/'dist'/'AudioDuplicateDetector.exe')
    check_archive(parser.parse_args().path)
