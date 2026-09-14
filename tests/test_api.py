import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import BASE_DIR
from app.main import app
from app.storage import clear_db_for_tests


def client():
    clear_db_for_tests()
    return TestClient(app)


def demo_payload():
    return {
        'mode': 'demo', 'center': {'lng': 121.601, 'lat': 31.201}, 'center_name': '模拟社区',
        'city': '上海市', 'coord_type': 'bd09ll', 'threshold_minutes': 15,
        'sample_bearings': 16, 'poi_radius_meters': 1800,
    }


def test_health_and_config_do_not_leak_key():
    c = client()
    assert c.get('/api/health').status_code == 200
    text = c.get('/api/config/status').text
    assert '"baidu_map_ak"' not in text.lower()
    assert 'secret-ak' not in text


def test_demo_end_to_end_history_and_exports():
    c = client()
    r = c.post('/api/analyze', json=demo_payload())
    assert r.status_code == 200, r.text
    analysis_id = r.json()['id']
    assert c.get('/api/analyses').json()['items'][0]['id'] == analysis_id
    detail = c.get(f'/api/analyses/{analysis_id}')
    assert detail.status_code == 200
    for kind in ['md', 'html', 'json', 'geojson', 'poi.csv', 'blind.csv', 'zip']:
        exp = c.get(f'/api/analyses/{analysis_id}/export/{kind}')
        assert exp.status_code == 200, (kind, exp.text[:200])
        assert len(exp.content) > 20


def test_real_mode_requires_key_when_unconfigured():
    c = client()
    payload = demo_payload(); payload['mode'] = 'real'
    r = c.post('/api/analyze', json=payload)
    # Test environment intentionally has no project .env AK.
    if not os.getenv('BAIDU_MAP_AK'):
        assert r.status_code == 400
        assert 'BAIDU_MAP_AK' in r.text


def test_demo_static_map_is_rejected_not_faked():
    c = client(); analysis_id = c.post('/api/analyze', json=demo_payload()).json()['id']
    r = c.get(f'/api/analyses/{analysis_id}/static-map.png')
    assert r.status_code == 400
    assert '离线模拟' in r.text


def test_ai_brief_uses_saved_result_without_changing_analysis(monkeypatch):
    async def fake_brief(result):
        assert result['data_notice'] == 'SIMULATED_OFFLINE_DATA'
        return {
            'text': '以下仅为离线模拟解读。',
            'model': 'test-model',
            'generated_at': '2026-09-14T00:00:00',
            'evidence_mode': 'simulated_offline',
            'notice': '只解释证据。',
        }

    monkeypatch.setattr('app.main.generate_planning_brief', fake_brief)
    settings_type = type(__import__('app.main', fromlist=['settings']).settings)
    monkeypatch.setattr(settings_type, 'llm_ready', property(lambda _: True))
    c = client()
    analysis_id = c.post('/api/analyze', json=demo_payload()).json()['id']
    response = c.post(f'/api/analyses/{analysis_id}/ai-brief')
    assert response.status_code == 200
    assert response.json()['evidence_mode'] == 'simulated_offline'
    assert c.get(f'/api/analyses/{analysis_id}').json()['result']['health_score'] is not None
