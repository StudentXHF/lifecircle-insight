import asyncio

from app.services.analysis import run_analysis


def test_demo_analysis_complete():
    payload = {
        "mode": "demo", "center": {"lng": 121.601, "lat": 31.201}, "center_name": "模拟样例",
        "city": "上海市", "coord_type": "bd09ll", "threshold_minutes": 15,
        "sample_bearings": 16, "poi_radius_meters": 1800,
    }
    result = asyncio.run(run_analysis(payload))
    assert result["mode"] == "demo"
    assert result["data_notice"] == "SIMULATED_OFFLINE_DATA"
    assert len(result["isochrone"]) == 16
    assert result["area_m2"] > 100000
    assert 0 <= result["health_score"] <= 100
    assert result["pois"]
    assert result["api_stats"]["request_count"] == 0
    assert result["api_stats"]["simulated"] is True
    assert any("模拟" in w for w in result["warnings"])
