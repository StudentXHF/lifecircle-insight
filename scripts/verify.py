from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMANDS = [
    [sys.executable, 'scripts/style_check.py'],
    [sys.executable, '-m', 'compileall', '-q', 'app'],
    [sys.executable, '-m', 'pytest', '-q'],
]

for cmd in COMMANDS:
    print('>', ' '.join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)
print('VERIFY_OK')
