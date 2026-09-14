from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE_PARTS = {'.venv', '__pycache__', '.pytest_cache', '.git', 'exports', 'data', 'tmp'}
TEXT_SUFFIXES = {'.py', '.md', '.txt', '.json', '.yml', '.yaml', '.toml', '.ini', '.cfg', '.example', '.js', '.css', '.html', '.bat', '.sh'}
REQUIRED = [
    'README.md', 'LICENSE', '.env.example', 'requirements.txt', 'start.bat', 'Dockerfile',
    '.github/workflows/ci.yml', 'docs/赛题任务书_原始.pdf', 'docs/评分点逐项对照表.md',
    'submission/01_圈析智图_作品介绍文档_正式稿.pdf',
    'submission/02_圈析智图_技术设计报告_正式稿.pdf',
]
# Looks for common secret assignments with a non-placeholder value. The pattern is intentionally conservative.
SECRET_PATTERNS = [
    re.compile(r'(?i)(BAIDU_MAP_AK|BAIDU_MAP_BROWSER_AK|API_KEY|SECRET|TOKEN)[ \\t]*[=:][ \\t]*["\']?([A-Za-z0-9_\-]{16,})'),
]
SAFE_VALUES = {'yourkey', 'your_key', 'placeholder', 'changeme', 'example'}


def iter_text_files():
    for p in ROOT.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in IGNORE_PARTS for part in rel.parts):
            continue
        if p.name == '.env':
            continue
        if p.suffix.lower() in TEXT_SUFFIXES or p.name in {'.gitignore'}:
            yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true', help='Fail if local .env or runtime DB exists.')
    args = ap.parse_args()
    problems: list[str] = []
    warnings: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            problems.append(f'missing required file: {rel}')
    if (ROOT / '.env').exists():
        msg = 'local .env exists: never include it in a release ZIP/Git commit'
        (problems if args.strict else warnings).append(msg)
    runtime = list((ROOT / 'data').glob('*.db')) + list((ROOT / 'data').glob('*.sqlite*'))
    if runtime:
        msg = 'runtime database/cache exists under data/: ' + ', '.join(p.name for p in runtime)
        (problems if args.strict else warnings).append(msg)
    for p in iter_text_files():
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        for pat in SECRET_PATTERNS:
            for m in pat.finditer(text):
                value = m.group(2)
                low = value.lower()
                if low in SAFE_VALUES or 'xxxx' in low or '这里填写' in text[max(0,m.start()-30):m.end()+30]:
                    continue
                # .env.example intentionally has empty values; long values elsewhere deserve manual review.
                problems.append(f'possible secret in {p.relative_to(ROOT)}: {m.group(1)}=<redacted>')
                break
    for w in warnings:
        print('WARN:', w)
    if problems:
        for x in problems:
            print('ERROR:', x)
        return 1
    print('RELEASE_PREFLIGHT_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
