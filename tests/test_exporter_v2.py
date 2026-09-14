import json

from app.services.exporter import geojson_payload, html_report


def sample_record():
    return {
        'id': 1,
        'result': {
            'mode': 'demo', 'center_name': '样例', 'city': '上海市',
            'center_bd09': {'lng': 121.6, 'lat': 31.2}, 'threshold_minutes': 15,
            'area_km2': 1.2, 'health_score': 88, 'data_confidence_percent': 100,
            'isochrone': [
                {'lng': 121.59, 'lat': 31.19}, {'lng': 121.61, 'lat': 31.19},
                {'lng': 121.61, 'lat': 31.21}, {'lng': 121.59, 'lat': 31.21},
            ],
            'pois': [{'lng': 121.6, 'lat': 31.2, 'name': 'P', 'category': 'market', 'category_label': '菜市场', 'address': ''}],
            'blind_spots': [], 'blind_spots_status': 'ok',
            'coverage': {'market': {'label': '菜市场', 'status': 'known', 'count_in_isochrone': 1, 'count_total': 1, 'target': 1, 'score': 15, 'weight': 15}},
            'recommendations': [], 'warnings': [],
            'algorithm': {'isochrone': 'x', 'poi': 'y', 'blind_spots': 'z', 'caveat': 'c'},
        }
    }


def test_geojson_contains_polygon_and_poi():
    data = geojson_payload(sample_record())
    assert data['type'] == 'FeatureCollection'
    assert {f['properties']['kind'] for f in data['features']} == {'isochrone', 'poi'}
    assert data['features'][0]['geometry']['coordinates'][0][0] == data['features'][0]['geometry']['coordinates'][0][-1]


def test_html_report_is_standalone_utf8_friendly():
    text = html_report(sample_record())
    assert '<!doctype html>' in text.lower()
    assert '圈析智图' in text
    assert '样例' in text
