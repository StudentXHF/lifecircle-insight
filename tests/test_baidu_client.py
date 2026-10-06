import asyncio
import json
import time

import httpx

from app.services import baidu
from app.services.baidu import BaiduMapClient


def test_service_requests_are_paced_across_clients(monkeypatch):
    async def run():
        monkeypatch.setitem(baidu._MIN_REQUEST_GAP_SECONDS, 'place_search', 0.02)
        baidu._NEXT_REQUEST_AT.pop('place_search', None)
        starts = []

        async def reserve():
            await baidu._wait_for_service_slot('place_search')
            starts.append(time.monotonic())

        await asyncio.gather(*(reserve() for _ in range(3)))
        assert len(starts) == 3
        assert all(b - a >= 0.015 for a, b in zip(starts, starts[1:]))

    asyncio.run(run())


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


def test_route_matrix_respects_personal_account_route_limit():
    async def run():
        calls = 0
        batch_sizes = []
        async def handler(request: httpx.Request):
            nonlocal calls
            calls += 1
            dests = request.url.params["destinations"].split("|")
            batch_sizes.append(len(dests))
            return httpx.Response(200, json={"status": 0, "result": [
                {"distance": {"value": 1000}, "duration": {"value": 800}} for _ in dests
            ]})
        client = BaiduMapClient("secret-ak", transport=httpx.MockTransport(handler))
        try:
            dests = [{"lat": 31.2 + i/100000, "lng": 121.6} for i in range(64)]
            out = await client.route_matrix_walking({"lat": 31.2, "lng": 121.6}, dests)
            assert len(out) == 64
            assert calls == 32
            assert max(batch_sizes) == 2
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
            assert stats['request_count'] == 32
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
