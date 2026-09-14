from pathlib import Path

from fastapi.testclient import TestClient

from app.config import BASE_DIR
from app.main import app


def test_v30_visual_stage_is_full_featured():
    html = (BASE_DIR / 'static' / 'index.html').read_text(encoding='utf-8')
    for marker in [
        'visualStage', 'stageSummary', 'presentationBtn',
        'tabTwin', 'tabBaidu', 'tabMap', 'twinCanvas', 'baidu3dMap', 'mapSvg',
        'distance-legend',
    ]:
        assert marker in html
    assert 'v3.0 RC' in html


def test_v30_baidu_webgl_has_distance_and_presentation_controls():
    js = (BASE_DIR / 'static' / 'app.js').read_text(encoding='utf-8')
    assert 'api?v=1.0&type=webgl' in js
    assert '&callback=' in js
    assert 'setTilt(72)' in js
    assert 'setHeading(32)' in js
    assert 'new BMapGL.Circle(center, radius' in js
    assert 'browser_map_style_id' in js
    assert 'togglePresentationMode' in js
    assert 'renderStageSummary' in js
    assert 'baiduMap.destroy()' in js
    assert "document.addEventListener('visibilitychange'" in js
    assert 'showBaiduError' in js


def test_config_status_exposes_only_browser_safe_map_config():
    c = TestClient(app)
    data = c.get('/api/config/status').json()
    assert 'baidu_map_ak' not in data
    assert 'browser_map_ready' in data
    assert 'browser_map_ak' in data
    assert 'browser_map_style_id' in data


def test_rc3_static_assets_are_versioned_together_and_canvas_is_responsive():
    html = (BASE_DIR / 'static' / 'index.html').read_text(encoding='utf-8')
    js = (BASE_DIR / 'static' / 'app.js').read_text(encoding='utf-8')
    assert '/static/styles.css?v=3.0.0-rc3.2' in html
    assert '/static/app.js?v=3.0.0-rc3.2' in html
    assert 'rect.width > 0 ? Math.round(rect.width)' in js
