from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings
from app.services.cache import get_cached, set_cached


class BaiduAPIError(RuntimeError):
    def __init__(self, service: str, message: str, *, status: int | None = None):
        super().__init__(f'{service}: {message}')
        self.service = service
        self.status = status
        self.safe_message = message[:300]


@dataclass
class APICall:
    service: str
    ok: bool
    latency_ms: int
    cache_hit: bool = False
    note: str = ''
    quota_units: int = 0


@dataclass
class BaiduStats:
    calls: list[APICall] = field(default_factory=list)

    def add(
        self,
        service: str,
        ok: bool,
        latency_ms: int,
        cache_hit: bool = False,
        note: str = '',
        quota_units: int = 0,
    ) -> None:
        self.calls.append(APICall(service, ok, latency_ms, cache_hit, note[:120], max(0, int(quota_units))))

    def summary(self) -> dict[str, Any]:
        return {
            'request_count': len([c for c in self.calls if not c.cache_hit]),
            'cache_hits': len([c for c in self.calls if c.cache_hit]),
            'success_count': len([c for c in self.calls if c.ok]),
            'failed_count': len([c for c in self.calls if not c.ok]),
            'total_latency_ms': sum(c.latency_ms for c in self.calls if not c.cache_hit),
            'quota_units_estimated': sum(c.quota_units for c in self.calls if not c.cache_hit),
            'calls': [c.__dict__ for c in self.calls],
        }


class BaiduMapClient:
    """Dependency-light wrapper around Baidu Maps Web Service APIs.

    Secrets are appended only to outgoing requests. Cache keys deliberately omit AK.
    Successful GET responses may be cached in a small local SQLite cache so repeated
    analyses do not waste QPS/quota on identical requests.
    """

    def __init__(self, ak: str | None = None, *, transport: httpx.AsyncBaseTransport | None = None):
        self.ak = (ak if ak is not None else settings.baidu_map_ak).strip()
        self.base = settings.baidu_api_base
        self.timeout = httpx.Timeout(settings.request_timeout_seconds)
        self._client = httpx.AsyncClient(timeout=self.timeout, transport=transport, follow_redirects=False)
        self._semaphore = asyncio.Semaphore(settings.baidu_concurrency)
        self._memory_cache: dict[str, tuple[float, Any]] = {}
        self.stats = BaiduStats()
        self._allow_persistent_cache = transport is None

    async def aclose(self) -> None:
        await self._client.aclose()

    def _assert_key(self) -> None:
        if not self.ak:
            raise BaiduAPIError('configuration', 'BAIDU_MAP_AK 未配置；真实模式不可用。')

    def _cache_key(self, path: str, params: dict[str, Any]) -> str:
        safe = {k: v for k, v in params.items() if k != 'ak'}
        raw = path + '?' + json.dumps(safe, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    async def _json_get(
        self,
        service: str,
        path: str,
        params: dict[str, Any],
        *,
        use_cache: bool = True,
        quota_units: int = 1,
    ) -> dict[str, Any]:
        self._assert_key()
        params = dict(params)
        params['ak'] = self.ak
        key = self._cache_key(path, params)
        now = time.time()

        if use_cache and key in self._memory_cache:
            expires, payload = self._memory_cache[key]
            if expires > now:
                self.stats.add(service, True, 0, cache_hit=True, note='memory-cache', quota_units=0)
                return payload
            self._memory_cache.pop(key, None)

        if use_cache and self._allow_persistent_cache and settings.baidu_cache_ttl_seconds > 0:
            payload = get_cached(key)
            if payload is not None:
                self._memory_cache[key] = (now + settings.baidu_cache_ttl_seconds, payload)
                self.stats.add(service, True, 0, cache_hit=True, note='sqlite-cache', quota_units=0)
                return payload

        for attempt in range(settings.baidu_retry_times + 1):
            started = time.perf_counter()
            try:
                async with self._semaphore:
                    resp = await self._client.get(self.base + path, params=params)
                elapsed = int((time.perf_counter() - started) * 1000)
                if resp.status_code != 200:
                    self.stats.add(service, False, elapsed, note=f'HTTP {resp.status_code}', quota_units=quota_units)
                    raise BaiduAPIError(service, f'HTTP {resp.status_code}', status=resp.status_code)
                try:
                    data = resp.json()
                except Exception as exc:  # pragma: no cover - defensive
                    self.stats.add(service, False, elapsed, note='invalid-json', quota_units=quota_units)
                    raise BaiduAPIError(service, '返回内容不是合法 JSON。') from exc
                status = data.get('status')
                if status not in (None, 0, '0'):
                    message = str(data.get('message') or data.get('msg') or f'Baidu status={status}')
                    self.stats.add(service, False, elapsed, note=f'status={status}', quota_units=quota_units)
                    if attempt < settings.baidu_retry_times and str(status) in {'1', '302', '401', '402'}:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    raise BaiduAPIError(service, message, status=int(status) if str(status).isdigit() else None)
                self.stats.add(service, True, elapsed, note=f'attempt={attempt + 1}', quota_units=quota_units)
                if use_cache and settings.baidu_cache_ttl_seconds > 0:
                    expires = now + settings.baidu_cache_ttl_seconds
                    self._memory_cache[key] = (expires, data)
                    if self._allow_persistent_cache:
                        set_cached(key, data, settings.baidu_cache_ttl_seconds)
                return data
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                elapsed = int((time.perf_counter() - started) * 1000)
                self.stats.add(service, False, elapsed, note=type(exc).__name__, quota_units=quota_units)
                if attempt < settings.baidu_retry_times:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                raise BaiduAPIError(service, f'网络请求失败：{type(exc).__name__}') from exc
            except BaiduAPIError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                if attempt >= settings.baidu_retry_times:
                    raise BaiduAPIError(service, f'请求失败：{type(exc).__name__}') from exc
                await asyncio.sleep(0.5 * (2**attempt))
        raise BaiduAPIError(service, '请求失败：重试次数已耗尽。')

    async def geocode(self, address: str, city: str = '') -> dict[str, Any]:
        params = {'address': address, 'output': 'json'}
        if city:
            params['city'] = city
        data = await self._json_get('geocoding', '/geocoding/v3/', params)
        result = data.get('result') or {}
        loc = result.get('location') or {}
        if 'lat' not in loc or 'lng' not in loc:
            raise BaiduAPIError('geocoding', '未返回有效坐标。')
        return {
            'lat': float(loc['lat']),
            'lng': float(loc['lng']),
            'precise': result.get('precise'),
            'confidence': result.get('confidence'),
            'comprehension': result.get('comprehension'),
        }

    async def convert_coordinates(self, points: list[dict], source: str) -> list[dict]:
        model = 1 if source == 'gcj02' else 2
        coords = ';'.join(f"{p['lng']:.7f},{p['lat']:.7f}" for p in points)
        data = await self._json_get(
            'coordinate_conversion', '/geoconv/v2/', {'coords': coords, 'model': model, 'output': 'json'}
        )
        result = data.get('result') or []
        if len(result) != len(points):
            raise BaiduAPIError('coordinate_conversion', '坐标转换结果数量与输入不一致。')
        return [{'lng': float(p['x']), 'lat': float(p['y'])} for p in result]

    async def search_nearby(
        self, query: str, lat: float, lng: float, radius: int, *, page_size: int = 20
    ) -> list[dict]:
        page_size = min(20, max(1, page_size))
        results: list[dict] = []
        seen: set[tuple] = set()
        for page_num in range(settings.baidu_poi_max_pages):
            params = {
                'query': query,
                'location': f'{lat:.7f},{lng:.7f}',
                'radius': int(radius),
                'radius_limit': 'true',
                'output': 'json',
                'scope': 2,
                'page_size': page_size,
                'page_num': page_num,
            }
            data = await self._json_get('place_search', '/place/v2/search', params)
            raw_items = data.get('results') or []
            for item in raw_items:
                loc = item.get('location') or {}
                if 'lat' not in loc or 'lng' not in loc:
                    continue
                detail = item.get('detail_info') or {}
                row = {
                    'uid': item.get('uid'),
                    'name': item.get('name') or '未命名POI',
                    'address': item.get('address') or '',
                    'lat': float(loc['lat']),
                    'lng': float(loc['lng']),
                    'distance_m': detail.get('distance'),
                    'detail_tag': detail.get('tag') or '',
                }
                uid = str(row.get('uid') or '').strip()
                identity = (
                    ('uid', uid)
                    if uid
                    else ('fallback', ' '.join(row['name'].split()).casefold(), round(row['lat'], 6), round(row['lng'], 6))
                )
                if identity not in seen:
                    seen.add(identity)
                    results.append(row)
            if len(raw_items) < page_size:
                break
            total = data.get('total')
            if isinstance(total, int) and len(results) >= total:
                break
        return results

    async def route_matrix_walking(self, origin: dict, destinations: list[dict]) -> list[dict]:
        if not destinations:
            return []
        output: list[dict] = []
        for start in range(0, len(destinations), 50):
            batch = destinations[start:start + 50]
            params = {
                'output': 'json',
                'origins': f"{origin['lat']:.7f},{origin['lng']:.7f}",
                'destinations': '|'.join(f"{p['lat']:.7f},{p['lng']:.7f}" for p in batch),
                'coord_type': 'bd09ll',
            }
            data = await self._json_get(
                'route_matrix_walking', '/routematrix/v2/walking', params, use_cache=True, quota_units=len(batch)
            )
            rows = data.get('result') or []
            if len(rows) != len(batch):
                raise BaiduAPIError('route_matrix_walking', '批量算路返回数量与输入不一致。')
            for dest, row in zip(batch, rows):
                distance = ((row.get('distance') or {}).get('value'))
                duration = ((row.get('duration') or {}).get('value'))
                output.append({
                    'lat': dest['lat'], 'lng': dest['lng'],
                    'distance_m': float(distance or 0),
                    'duration_s': float(duration or 0),
                })
        return output

    async def walking_route(self, origin: dict, destination: dict) -> dict[str, Any] | None:
        data = await self._json_get('walking_route', '/directionlite/v1/walking', {
            'origin': f"{origin['lat']:.7f},{origin['lng']:.7f}",
            'destination': f"{destination['lat']:.7f},{destination['lng']:.7f}",
        })
        routes = ((data.get('result') or {}).get('routes')) or []
        if not routes:
            return None
        route = routes[0]
        return {
            'distance_m': route.get('distance'),
            'duration_s': route.get('duration'),
            'steps_count': len(route.get('steps') or []),
        }

    async def static_map_bytes(
        self, *, center: dict, polygon: list[dict], pois: list[dict], blind_spots: list[dict] | None = None,
        width: int = 900, height: int = 560
    ) -> bytes:
        self._assert_key()
        params: dict[str, Any] = {
            'ak': self.ak,
            'center': f"{center['lng']:.7f},{center['lat']:.7f}",
            'width': min(1024, max(200, width)),
            'height': min(1024, max(200, height)),
            'zoom': 15,
            'scale': 1,
        }
        if polygon:
            poly = polygon[::max(1, len(polygon)//20)]
            if poly[0] != poly[-1]:
                poly = poly + [poly[0]]
            params['paths'] = ';'.join(f"{p['lng']:.6f},{p['lat']:.6f}" for p in poly)
            params['pathStyles'] = '0x2563EB,4,0.9,0x93C5FD'
        marker_points = list(pois[:15])
        marker_points.extend((blind_spots or [])[:5])
        if marker_points:
            params['markers'] = '|'.join(f"{p['lng']:.6f},{p['lat']:.6f}" for p in marker_points)
            params['markerStyles'] = 's,A,0xEF4444'
        started = time.perf_counter()
        try:
            async with self._semaphore:
                resp = await self._client.get(self.base + '/staticimage/v2', params=params)
            elapsed = int((time.perf_counter() - started) * 1000)
            if resp.status_code != 200:
                self.stats.add('static_map', False, elapsed, note=f'HTTP {resp.status_code}', quota_units=1)
                raise BaiduAPIError('static_map', f'HTTP {resp.status_code}', status=resp.status_code)
            ctype = resp.headers.get('content-type', '')
            if 'image' not in ctype and not resp.content.startswith(b'\x89PNG'):
                self.stats.add('static_map', False, elapsed, note='not-image', quota_units=1)
                raise BaiduAPIError('static_map', '静态地图服务未返回图片。')
            self.stats.add('static_map', True, elapsed, quota_units=1)
            return resp.content
        except httpx.HTTPError as exc:
            raise BaiduAPIError('static_map', f'网络请求失败：{type(exc).__name__}') from exc
