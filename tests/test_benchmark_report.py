from scripts.run_real_benchmark import report_csv


def test_benchmark_csv_contains_summary_metrics_and_utf8_bom():
    result = {
        'center_name': '社区A',
        'area_km2': 1.25,
        'health_score': 80,
        'data_confidence_percent': 95,
        'blind_spots': [{}, {}],
        'reachability_comparison': {
            'isochrone_to_naive_area_ratio': 0.42,
            'median_route_detour_ratio': 1.3,
            'median_time_penalty_ratio': 1.4,
        },
        'api_stats': {'request_count': 8, 'quota_units_estimated': 70},
        'benchmark_api_stats': {'request_count': 9, 'quota_units_estimated': 71},
        'elapsed_ms': 1234,
        'benchmark_elapsed_ms': 1500,
    }
    text = report_csv([result])
    assert text.startswith('\ufeff')
    assert 'area_km2' in text
    assert '社区A' in text
    assert ',9,0,71,1500' in text
