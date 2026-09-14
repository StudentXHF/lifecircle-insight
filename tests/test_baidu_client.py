import asyncio
import json

import httpx

from app.services.baidu import BaiduMapClient


def test_coordinate_convert_and_no_secret_in_stats():
    async def run():
        async def handler(request: httpx.Request):
            assert request.url.params["ak"] == "secret-ak"
            return httpx.Response(200, json={"status": 0, "result": [{"x": 121.6, "y": 31.2}]})
        client = BaiduMapClient("secret-ak", transport=httpx.MockTransport(handler))
        try:
            out = await client.convert_coordinates([{"lng": 121.5, "lat": 31.1}], "gcj02")
            assert out == [{"lng": 121.6, "lat": 31.2}]
            blob = json.dumps(client.stats.summary(), ensure_ascii=False)
            assert "secret-ak" not in blob
        finally:
            await client.aclose()
    asyncio.run(run())


def test_route_matrix_splits_at_50():
    async def run():
        calls = 0
        async def handler(request: httpx.Request):
            nonlocal calls
            calls += 1
            dests = request.url.params["destinations"].split("|")
            return httpx.Response(200, json={"status": 0, "result": [
                {"distance": {"value": 1000}, "duration": {"value": 800}} for _ in dests
            ]})
        client = BaiduMapClient("secret-ak", transport=httpx.MockTransport(handler))
        try:
            dests = [{"lat": 31.2 + i/100000, "lng": 121.6} for i in range(64)]
            out = await client.route_matrix_walking({"lat": 31.2, "lng": 121.6}, dests)
            assert len(out) == 64
            assert calls == 2
        finally:
            await client.aclose()
    asyncio.run(run())


def test_route_matrix_quota_units_count_routes_not_http_batches():
    async def run():
        async def handler(request: httpx.Request):
            dests = request.url.params['destinations'].split('|')
            return httpx.Response(200, json={'status': 0, 'result': [
                {'distance': {'value': 1000}, 'duration': {'value': 800}} for _ in dests
            ]})
        client = BaiduMapClient('secret-ak', transport=httpx.MockTransport(handler))
        try:
            dests = [{'lat': 31.2 + i/100000, 'lng': 121.6} for i in range(64)]
            await client.route_matrix_walking({'lat': 31.2, 'lng': 121.6}, dests)
            stats = client.stats.summary()
            assert stats['request_count'] == 2
            assert stats['quota_units_estimated'] == 64
        finally:
            await client.aclose()
    asyncio.run(run())


def test_api_stats_never_include_authorization_secret():
    async def run():
        async def handler(request: httpx.Request):
            return httpx.Response(200, json={'status': 0, 'result': {'location': {'lat': 31.2, 'lng': 121.6}}})
        client = BaiduMapClient('super-secret-value', transport=httpx.MockTransport(handler))
        try:
            await client.geocode('测试地址', '上海市')
            serialized = json.dumps(client.stats.summary(), ensure_ascii=False)
            assert 'super-secret-value' not in serialized
            assert 'Authorization' not in serialized
        finally:
            await client.aclose()
    asyncio.run(run())
