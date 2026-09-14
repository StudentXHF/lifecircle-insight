from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {'.venv', '__pycache__', '.pytest_cache', '.git', 'data', 'exports', 'tmp'}
EXCLUDE_NAMES = {
    '.env',
    '圈析智图_v3.0_RC_准提交材料包_真实实测后补齐.zip',
}
EXCLUDE_SUFFIXES = {'.pyc', '.pyo'}


def include(p: Path) -> bool:
    rel = p.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if p.name in EXCLUDE_NAMES or p.suffix in EXCLUDE_SUFFIXES:
        return False
    return p.is_file()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT.parent / '圈析智图_release.zip'))
    ap.add_argument('--root-name', default='lifecircle_ai_project')
    args = ap.parse_args()
    out = Path(args.out).resolve()
    files = [p for p in ROOT.rglob('*') if include(p) and p.resolve() != out]
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(files, key=lambda x: str(x.relative_to(ROOT))):
            z.write(p, Path(args.root_name) / p.relative_to(ROOT))
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f'zip integrity failed: {bad}')
    print(f'RELEASE_ZIP_OK files={len(files)} bytes={out.stat().st_size} path={out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
