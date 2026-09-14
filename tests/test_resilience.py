import asyncio

import httpx

from app.services.analysis import _blind_spots, _build_isochrone, _coverage_and_score, _dedupe_pois
from app.services.baidu import BaiduMapClient
from app.utils.geo import destination_point


def test_poi_pagination_collects_multiple_pages(monkeypatch):
    async def run():
        calls = []
        async def handler(request: httpx.Request):
            page = int(request.url.params['page_num'])
            calls.append(page)
            if page == 0:
                items = [
                    {'uid': f'u{i}', 'name': f'P{i}', 'address': '', 'location': {'lat': 31.2, 'lng': 121.6+i/10000}, 'detail_info': {}}
                    for i in range(20)
                ]
                return httpx.Response(200, json={'status': 0, 'total': 21, 'results': items})
            return httpx.Response(200, json={'status': 0, 'total': 21, 'results': [
                {'uid': 'u20', 'name': 'P20', 'address': '', 'location': {'lat': 31.2, 'lng': 121.7}, 'detail_info': {}}
            ]})
        client = BaiduMapClient('secret-ak', transport=httpx.MockTransport(handler))
        try:
            out = await client.search_nearby('药店', 31.2, 121.6, 1800)
            assert len(out) == 21
            assert calls == [0, 1]
        finally:
            await client.aclose()
    asyncio.run(run())


def test_unknown_category_is_not_scored_as_zero():
    poly = [
        {'lat': 31.19, 'lng': 121.59}, {'lat': 31.19, 'lng': 121.61},
        {'lat': 31.21, 'lng': 121.61}, {'lat': 31.21, 'lng': 121.59},
    ]
    coverage, score, known_weight = _coverage_and_score([], poly, {'medical'})
    assert coverage['medical']['status'] == 'unknown'
    assert coverage['medical']['score'] is None
    assert known_weight == 80
    assert score == 0.0


def test_blind_spot_does_not_claim_missing_if_required_category_unknown():
    center = {'lat': 31.2, 'lng': 121.6}
    poly = [
        {'lat': 31.19, 'lng': 121.59}, {'lat': 31.19, 'lng': 121.61},
        {'lat': 31.21, 'lng': 121.61}, {'lat': 31.21, 'lng': 121.59},
    ]
    spots, status = _blind_spots(center, [], poly, {'pharmacy'})
    assert spots == []
    assert '药店' in status


def test_non_monotonic_route_time_is_corrected_for_interpolation():
    center = {'lat': 31.2, 'lng': 121.6}
    radii = [500, 900, 1300, 1700]
    samples = []
    for bearing in (0, 180):
        for radius, duration in zip(radii, (400, 800, 700, 1500)):
            samples.append({
                'lat': 31.2, 'lng': 121.6, 'duration_s': duration,
                '_radius': radius, '_bearing': bearing,
                '_origin_lat': center['lat'], '_origin_lng': center['lng'],
            })
    polygon, warnings, diag = _build_isochrone(samples, 900, 2, radii)
    assert len(polygon) == 2
    assert diag['monotonic_corrections'] == 2
    assert any('单调' in w for w in warnings)


def test_poi_dedupe_prefers_uid_then_falls_back_to_name_and_position():
    pois = [
        {'category': 'pharmacy', 'uid': 'same', 'name': '甲药店', 'lat': 31.2, 'lng': 121.6},
        {'category': 'pharmacy', 'uid': 'same', 'name': '甲药店新名称', 'lat': 31.21, 'lng': 121.61},
        {'category': 'market', 'uid': '', 'name': '  便民  市场 ', 'lat': 31.2, 'lng': 121.6},
        {'category': 'market', 'uid': None, 'name': '便民 市场', 'lat': 31.2000001, 'lng': 121.6000001},
    ]
    assert len(_dedupe_pois(pois)) == 2


def test_blind_spot_one_kilometer_boundary_is_inclusive():
    center = {'lat': 31.2, 'lng': 121.6}
    polygon = [
        {'lat': 31.1995, 'lng': 121.5995}, {'lat': 31.1995, 'lng': 121.6005},
        {'lat': 31.2005, 'lng': 121.6005}, {'lat': 31.2005, 'lng': 121.5995},
    ]

    def pois_at_market_distance(distance_m):
        market_lat, market_lng = destination_point(center['lat'], center['lng'], distance_m, 0)
        return [
            {'category': 'market', 'lat': market_lat, 'lng': market_lng},
            {'category': 'pharmacy', **center},
            {'category': 'primary_school', **center},
        ]

    for covered_distance in (999, 1000):
        spots, status = _blind_spots(center, pois_at_market_distance(covered_distance), polygon, set())
        assert status == 'ok'
        assert spots == []

    spots, status = _blind_spots(center, pois_at_market_distance(1001), polygon, set())
    assert status == 'ok'
    assert len(spots) == 1
    assert spots[0]['missing'] == ['market']


def test_blind_spot_one_kilometre_boundary_is_inclusive(monkeypatch):
    center = {'lat': 31.2, 'lng': 121.6}
    polygon = [
        {'lat': 31.19, 'lng': 121.59}, {'lat': 31.19, 'lng': 121.61},
        {'lat': 31.21, 'lng': 121.61}, {'lat': 31.21, 'lng': 121.59},
    ]
    monkeypatch.setattr('app.services.analysis.make_grid', lambda *_args, **_kwargs: [center])

    def pois_at(distance_m):
        from app.utils.geo import destination_point
        lat, lng = destination_point(center['lat'], center['lng'], distance_m, 90)
        return [
            {'category': key, 'lat': lat, 'lng': lng}
            for key in ('market', 'pharmacy', 'primary_school')
        ]

    for distance in (999, 1000):
        spots, status = _blind_spots(center, pois_at(distance), polygon, set())
        assert status == 'ok'
        assert spots == []
    spots, status = _blind_spots(center, pois_at(1001), polygon, set())
    assert status == 'ok'
    assert len(spots) == 1
    assert spots[0]['severity'] == 3
