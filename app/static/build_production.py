"""Assemble a fail-closed, allowlisted production container build context."""
import argparse
from pathlib import Path
import shutil

ASSETS = ('index.html', 'styles.css', 'app.mjs', 'feed.mjs', 'analytics.mjs', 'favicon.png')
FORBIDDEN = ('localhost', '127.0.0.1', 'local preview', 'local version', 'local server',
             'automatic updates are not connected', 'logs/runs/', 'app/static/README',
             '/Users/', '/Volumes/', '2026-09-29', '29 Sept 2026')

def build(destination):
    root = Path(__file__).resolve().parent
    if destination.exists():
        raise ValueError('Use a new empty build directory')
    # Validate everything before writing an artifact. The data comes only from GCS.
    for name in ASSETS:
        if name.endswith(('.html', '.css', '.mjs')):
            content = (root / name).read_text().lower()
            for marker in FORBIDDEN:
                if marker.lower() in content:
                    raise ValueError(f'Forbidden development content in {name}: {marker}')
    (destination / 'public').mkdir(parents=True)
    for name in ASSETS:
        shutil.copyfile(root / name, destination / 'public' / name)
    for name in ('Dockerfile', 'nginx.conf'):
        shutil.copyfile(root / name, destination / name)
    print('Production artifact:', ', '.join(str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.output)
