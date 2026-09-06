"""Run all tests with isolated application state and no real music library."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from core.binary_resolver import check_binaries
    missing = [name for name, (available, _) in check_binaries().items() if not available]
    if missing:
        print('Missing test dependencies: ' + ', '.join(missing), file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix='audioclean-validation-') as state:
        env = dict(os.environ, APPDATA=state, QT_QPA_PLATFORM='offscreen', SDL_AUDIODRIVER='dummy',
                   PYTHONDONTWRITEBYTECODE='1')
        bin_dirs = {str(Path(path).parent) for _, path in check_binaries().values()}
        env['PATH'] = os.pathsep.join(sorted(bin_dirs)) + os.pathsep + env.get('PATH', '')
        return subprocess.call([sys.executable, '-B', '-m', 'pytest', 'tests', '-q'], cwd=root, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
