from app.services.exporter import poi_csv


def test_csv_formula_injection_is_neutralized():
    record = {'result': {'pois': [{
        'category': 'market', 'category_label': '菜市场', 'name': '=2+2', 'address': '+CMD',
        'lng': 121.6, 'lat': 31.2, 'distance_m': 100, 'uid': '@uid'
    }]}}
    data = poi_csv(record).decode('utf-8-sig')
    assert "'=2+2" in data
    assert "'+CMD" in data
    assert "'@uid" in data
