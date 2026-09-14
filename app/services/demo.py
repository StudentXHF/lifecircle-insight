from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.utils.geo import destination_point, haversine_m


@dataclass
class DemoStats:
    calls: list[dict] = field(default_factory=list)

    def add(self, service: str, note: str = 'SIMULATED') -> None:
        self.calls.append({'service': service, 'ok': True, 'latency_ms': 0, 'cache_hit': False, 'note': note})

    def summary(self) -> dict[str, Any]:
        return {
            'request_count': 0,
            'cache_hits': 0,
            'success_count': len(self.calls),
            'failed_count': 0,
            'total_latency_ms': 0,
            'quota_units_estimated': 0,
            'calls': self.calls,
            'simulated': True,
        }


class DemoMapProvider:
    """Deterministic offline provider. Every result is synthetic and explicitly marked."""

    def __init__(self, center: dict):
        self.center = center
        self.stats = DemoStats()
        self._poi_catalog = self._make_pois()

    async def aclose(self) -> None:
        return None

    def _offset(self, distance: float, bearing: float, name: str, category: str, idx: int) -> dict:
        lat, lng = destination_point(self.center['lat'], self.center['lng'], distance, bearing)
        return {
            'uid': f'demo-{category}-{idx}', 'name': f'【模拟】{name}', 'address': '模拟地址，仅用于离线演示',
            'lat': lat, 'lng': lng, 'distance_m': round(distance), 'detail_tag': 'SIMULATED', 'category': category,
        }

    def _make_pois(self) -> dict[str, list[dict]]:
        return {
            'medical': [self._offset(420, 35, '社区卫生服务站A', 'medical', 1), self._offset(720, 215, '综合门诊B', 'medical', 2)],
            'primary_school': [self._offset(650, 105, '社区小学A', 'primary_school', 1)],
            'market': [self._offset(520, 285, '便民菜市场A', 'market', 1)],
            'pharmacy': [self._offset(360, 150, '便民药房A', 'pharmacy', 1), self._offset(650, 330, '社区药房B', 'pharmacy', 2), self._offset(820, 45, '社区药房C', 'pharmacy', 3)],
            'supermarket': [self._offset(300, 60, '生活超市A', 'supermarket', 1), self._offset(620, 245, '生鲜超市B', 'supermarket', 2), self._offset(850, 350, '生活超市C', 'supermarket', 3)],
            'elderly': [],
        }

    async def route_matrix_walking(self, origin: dict, destinations: list[dict]) -> list[dict]:
        self.stats.add('route_matrix_walking')
        rows = []
        for d in destinations:
            straight = haversine_m(origin['lat'], origin['lng'], d['lat'], d['lng'])
            # Deterministic road-network penalty: eastern side has a simulated river/large intersection barrier.
            angle = math.atan2(d['lng'] - origin['lng'], d['lat'] - origin['lat'])
            penalty = 1.12 + 0.20 * max(0.0, math.sin(angle)) + 0.12 * abs(math.cos(angle * 2))
            route_dist = straight * penalty
            duration = route_dist / 1.18 + 35  # ~4.25 km/h + crossing delay
            rows.append({'lat': d['lat'], 'lng': d['lng'], 'distance_m': route_dist, 'duration_s': duration})
        return rows

    async def search_nearby(self, query: str, lat: float, lng: float, radius: int, *, page_size: int = 20) -> list[dict]:
        self.stats.add('place_search')
        key = query.split('|', 1)[0]
        return [dict(p) for p in self._poi_catalog.get(key, []) if haversine_m(lat, lng, p['lat'], p['lng']) <= radius]

    async def walking_route(self, origin: dict, destination: dict) -> dict[str, Any] | None:
        self.stats.add('walking_route')
        straight = haversine_m(origin['lat'], origin['lng'], destination['lat'], destination['lng'])
        route_dist = straight * 1.25
        return {'distance_m': round(route_dist), 'duration_s': round(route_dist / 1.18 + 35), 'steps_count': 6, 'simulated': True}
