from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [ROOT / 'app', ROOT / 'tests', ROOT / 'scripts']
errors = []
for base in TARGETS:
    for path in base.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        for no, line in enumerate(text.splitlines(), 1):
            if line.endswith((' ', '\t')):
                errors.append(f'{path.relative_to(ROOT)}:{no}: trailing whitespace')
            if '\t' in line:
                errors.append(f'{path.relative_to(ROOT)}:{no}: tab character')
            if len(line) > 180:
                errors.append(f'{path.relative_to(ROOT)}:{no}: line longer than 180 chars')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print('style_check: OK')
