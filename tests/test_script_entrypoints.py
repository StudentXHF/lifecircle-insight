import os
import subprocess
import sys

from app.config import BASE_DIR


def run_script(relative_path):
    env = os.environ.copy()
    env['BAIDU_MAP_AK'] = ''
    return subprocess.run(
        [sys.executable, str(BASE_DIR / relative_path)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
        timeout=15,
    )


def test_baidu_smoke_script_runs_from_documented_entrypoint_without_key():
    result = run_script('scripts/check_baidu_api.py')
    assert result.returncode == 2
    assert 'BAIDU_MAP_AK' in result.stdout
    assert 'ModuleNotFoundError' not in result.stderr


def test_benchmark_script_runs_from_documented_entrypoint_without_key():
    result = run_script('scripts/run_real_benchmark.py')
    assert result.returncode == 2
    assert 'BAIDU_MAP_AK' in result.stdout
    assert 'ModuleNotFoundError' not in result.stderr
