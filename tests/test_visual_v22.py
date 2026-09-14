from pathlib import Path

from app.config import BASE_DIR
from fastapi.testclient import TestClient
from app.main import app


def test_visual_shell_contains_three_views():
    html = (BASE_DIR / 'static' / 'index.html').read_text(encoding='utf-8')
    for marker in ['tabTwin', 'tabBaidu', 'tabMap', 'twinCanvas', 'baidu3dMap', 'mapSvg']:
        assert marker in html
    assert 'BAIDU_MAP_BROWSER_AK' in html


def test_frontend_contains_baidu_jsapi4_loader_and_canvas_renderer():
    js = (BASE_DIR / 'static' / 'app.js').read_text(encoding='utf-8')
    assert 'api?v=1.0&type=webgl' in js
    assert '&callback=' in js
    assert 'renderTwin' in js
    assert 'renderBaidu3D' in js
    assert 'setTilt(72)' in js
    assert 'setHeading(32)' in js
    assert 'Marker3D' in js


def test_config_status_never_exposes_server_ak_field():
    c = TestClient(app)
    data = c.get('/api/config/status').json()
    assert 'baidu_map_ak' not in data
    assert 'browser_map_ready' in data
    # 浏览器端 AK 为 JSAPI 正常所需公开配置；服务端 BAIDU_MAP_AK 仍不得返回。
    assert 'browser_map_ak' in data
