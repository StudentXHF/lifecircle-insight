from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services.baidu import BaiduAPIError, BaiduMapClient


async def main() -> int:
    if not settings.baidu_map_ak:
        print('ERROR: BAIDU_MAP_AK 未配置。请复制 .env.example 为 .env 后填写服务端 AK。')
        return 2
    print('Baidu API minimal check: AK configured (secret not printed).')
    client = BaiduMapClient()
    try:
        geocoded = await client.geocode('上海市浦东新区张江镇人民政府', '上海市')
        print('1/5 geocoding: OK', {k: geocoded.get(k) for k in ('lng', 'lat', 'confidence')})
        center = {'lng': geocoded['lng'], 'lat': geocoded['lat']}
        converted = await client.convert_coordinates([{'lng': 121.4737, 'lat': 31.2304}], 'wgs84')
        print('2/5 coordinate_conversion: OK, points=', len(converted))
        pois = await client.search_nearby('药店', center['lat'], center['lng'], 1000, page_size=5)
        print('3/5 place_search: OK, results=', len(pois))
        dests = [
            {'lng': center['lng'] + 0.004, 'lat': center['lat']},
            {'lng': center['lng'], 'lat': center['lat'] + 0.004},
        ]
        matrix = await client.route_matrix_walking(center, dests)
        print('4/5 route_matrix_walking: OK, routes=', len(matrix))
        target = pois[0] if pois else dests[0]
        route = await client.walking_route(center, target)
        print('5/5 walking_route: OK' if route else '5/5 walking_route: no route returned')
        summary = client.stats.summary()
        print('Summary:', json.dumps({
            'http_requests': summary['request_count'],
            'cache_hits': summary['cache_hits'],
            'quota_units_estimated': summary['quota_units_estimated'],
            'failed_count': summary['failed_count'],
        }, ensure_ascii=False))
        return 0
    except BaiduAPIError as exc:
        print(f'ERROR [{exc.service}]: {exc.safe_message}')
        return 1
    finally:
        await client.aclose()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
