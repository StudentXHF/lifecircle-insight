from __future__ import annotations

import asyncio
import math
import statistics
import time
from typing import Any

from app.config import settings
from app.services.baidu import BaiduAPIError, BaiduMapClient
from app.services.demo import DemoMapProvider
from app.utils.geo import destination_point, haversine_m, make_grid, point_in_polygon, polygon_area_m2

FACILITY_CATALOG = {
    'medical': {'label': '基础医疗', 'query': '医院$社区卫生服务中心$诊所', 'target': 2, 'weight': 20},
    'primary_school': {'label': '小学', 'query': '小学', 'target': 1, 'weight': 20},
    'market': {'label': '菜市场', 'query': '菜市场$农贸市场', 'target': 2, 'weight': 15},
    'pharmacy': {'label': '药店', 'query': '药店', 'target': 3, 'weight': 15},
    'supermarket': {'label': '购物/超市', 'query': '超市', 'target': 3, 'weight': 15},
    'elderly': {'label': '养老服务', 'query': '养老院$养老服务', 'target': 1, 'weight': 15},
}
REQUIRED_BLIND_KEYS = ('market', 'pharmacy', 'primary_school')
BLIND_RADIUS_METERS = 1000.0


def _poi_identity(poi: dict) -> tuple:
    """Use a stable UID when available, otherwise fall back to name + position."""
    category = poi.get('category') or ''
    uid = str(poi.get('uid') or '').strip()
    if uid:
        return category, 'uid', uid
    name = ' '.join(str(poi.get('name') or '').split()).casefold()
    return category, 'fallback', name, round(float(poi['lat']), 6), round(float(poi['lng']), 6)


def _dedupe_pois(pois: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    output: list[dict] = []
    for poi in pois:
        identity = _poi_identity(poi)
        if identity in seen:
            continue
        seen.add(identity)
        output.append(poi)
    return output


def _radial_destinations(center: dict, bearings: int, radii: list[int]) -> list[dict]:
    out = []
    for bi in range(bearings):
        bearing = 360.0 * bi / bearings
        for radius in radii:
            lat, lng = destination_point(center['lat'], center['lng'], radius, bearing)
            out.append({'lat': lat, 'lng': lng, '_bearing': bearing, '_radius': radius})
    return out


def _monotonic_rows(rows: list[dict]) -> tuple[list[dict], int]:
    """Return rows with a non-decreasing duration envelope.

    RouteMatrix travel times can occasionally be locally non-monotonic because two farther
    points may enter a different road corridor. Radial interpolation assumes monotonicity,
    so we apply a conservative cumulative-maximum envelope and expose the correction count.
    """
    corrected: list[dict] = []
    last_duration = 0.0
    changes = 0
    for row in sorted(rows, key=lambda r: r['_radius']):
        copy = dict(row)
        duration = float(copy.get('duration_s') or 0)
        if duration > 0 and duration < last_duration:
            duration = last_duration
            changes += 1
        if duration > 0:
            last_duration = duration
        copy['_duration_for_interp'] = duration
        corrected.append(copy)
    return corrected, changes


def _build_isochrone(
    samples: list[dict], threshold_s: int, bearings: int, radii: list[int]
) -> tuple[list[dict], list[str], dict[str, Any]]:
    polygon: list[dict] = []
    warnings: list[str] = []
    per_bearing = len(radii)
    monotonic_corrections = 0
    truncated_bearings = 0
    extrapolated_bearings = 0

    for bi in range(bearings):
        rows = samples[bi * per_bearing:(bi + 1) * per_bearing]
        rows = [r for r in rows if r.get('duration_s', 0) > 0]
        if not rows:
            continue
        rows, changes = _monotonic_rows(rows)
        monotonic_corrections += changes
        lower = None
        upper = None
        for row in rows:
            duration = row['_duration_for_interp']
            if duration <= threshold_s:
                lower = row
            elif upper is None:
                upper = row

        if lower and upper:
            dt = max(1.0, upper['_duration_for_interp'] - lower['_duration_for_interp'])
            ratio = max(0.0, min(1.0, (threshold_s - lower['_duration_for_interp']) / dt))
            radius = lower['_radius'] + ratio * (upper['_radius'] - lower['_radius'])
        elif lower:
            radius = float(lower['_radius'])
            if lower['_radius'] == radii[-1]:
                truncated_bearings += 1
        else:
            first = rows[0]
            radius = max(120.0, first['_radius'] * threshold_s / max(first['_duration_for_interp'], 1))
            extrapolated_bearings += 1

        lat, lng = destination_point(
            rows[0]['_origin_lat'], rows[0]['_origin_lng'], radius, rows[0]['_bearing']
        )
        polygon.append({
            'lat': lat, 'lng': lng, 'bearing': rows[0]['_bearing'], 'radius_m': round(radius, 1)
        })

    if monotonic_corrections:
        warnings.append(
            f'检测到 {monotonic_corrections} 个径向样本存在局部耗时逆序；已使用保守单调包络参与等时圈插值。'
        )
    if truncated_bearings:
        warnings.append(
            f'{truncated_bearings} 个方向在最大采样半径 {radii[-1]} m 仍未超过时间阈值；等时圈在这些方向可能被截断。'
        )
    if extrapolated_bearings:
        warnings.append(
            f'{extrapolated_bearings} 个方向首个采样点已超过时间阈值；边界使用近中心比例外推，建议提高采样分辨率复核。'
        )

    diagnostics = {
        'monotonic_corrections': monotonic_corrections,
        'truncated_bearings': truncated_bearings,
        'extrapolated_bearings': extrapolated_bearings,
        'valid_bearings': len(polygon),
    }
    return polygon, warnings, diagnostics


def _coverage_and_score(
    pois: list[dict], polygon: list[dict], unavailable_categories: set[str]
) -> tuple[dict, float | None, int]:
    coverage: dict[str, Any] = {}
    known_score = 0.0
    known_weight = 0
    for key, spec in FACILITY_CATALOG.items():
        if key in unavailable_categories:
            coverage[key] = {
                'label': spec['label'], 'count_total': None, 'count_in_isochrone': None,
                'target': spec['target'], 'weight': spec['weight'], 'score': None, 'status': 'unknown',
            }
            continue
        all_items = [p for p in pois if p['category'] == key]
        inside = [p for p in all_items if point_in_polygon(p['lat'], p['lng'], polygon)]
        ratio = min(1.0, len(inside) / spec['target']) if spec['target'] else 1.0
        score = ratio * spec['weight']
        known_score += score
        known_weight += spec['weight']
        coverage[key] = {
            'label': spec['label'], 'count_total': len(all_items), 'count_in_isochrone': len(inside),
            'target': spec['target'], 'weight': spec['weight'], 'score': round(score, 1), 'status': 'known',
        }
    if known_weight == 0:
        return coverage, None, 0
    normalized_score = round(known_score / known_weight * 100, 1)
    return coverage, normalized_score, known_weight


def _blind_spots(
    center: dict, pois: list[dict], polygon: list[dict], unavailable_categories: set[str]
) -> tuple[list[dict], str]:
    unavailable_required = [k for k in REQUIRED_BLIND_KEYS if k in unavailable_categories]
    if unavailable_required:
        labels = '、'.join(FACILITY_CATALOG[k]['label'] for k in unavailable_required)
        return [], f'关键类别数据不完整（{labels}检索失败），本次不输出“无设施”盲区，避免把“未知”误判为“缺失”。'

    grid = make_grid(center['lat'], center['lng'], 1000, spacing_m=300)
    by_cat = {key: [p for p in pois if p['category'] == key] for key in REQUIRED_BLIND_KEYS}
    spots = []
    for g in grid:
        if polygon and not point_in_polygon(g['lat'], g['lng'], polygon):
            continue
        missing = []
        nearest = {}
        for key in REQUIRED_BLIND_KEYS:
            distances = [haversine_m(g['lat'], g['lng'], p['lat'], p['lng']) for p in by_cat[key]]
            best = min(distances) if distances else math.inf
            nearest[key] = None if math.isinf(best) else round(best)
            # The task wording is "within 1 km": an exactly 1000 m facility
            # therefore counts as covered.  A tiny tolerance avoids floating
            # point noise around the geodesic boundary.
            if best > BLIND_RADIUS_METERS + 1e-6:
                missing.append(key)
        if missing:
            spots.append({
                'lat': g['lat'], 'lng': g['lng'], 'missing': missing,
                'missing_labels': [FACILITY_CATALOG[k]['label'] for k in missing],
                'severity': len(missing), 'nearest_m': nearest,
                'distance_from_center_m': round(haversine_m(center['lat'], center['lng'], g['lat'], g['lng'])),
            })
    spots.sort(key=lambda s: (-s['severity'], -s['distance_from_center_m']))
    return spots[:18], 'ok'


def _recommendations(coverage: dict, blind_spots: list[dict], blind_status: str) -> list[dict]:
    recs = []
    for c in coverage.values():
        if c.get('status') == 'unknown':
            recs.append({
                'priority': '核验',
                'title': f"补充{c['label']}数据核验",
                'reason': '本次 API 检索未获得可靠结果，不能据此判断设施缺失。',
                'action': '检查百度 Place API 权限/配额后重试，或结合公开规划资料与实地核验。',
            })
            continue
        if c['count_in_isochrone'] < c['target']:
            gap = c['target'] - c['count_in_isochrone']
            recs.append({
                'priority': '高' if c['count_in_isochrone'] == 0 else '中',
                'title': f"补齐{c['label']}服务",
                'reason': f"15分钟等时圈内仅 {c['count_in_isochrone']} 个，建议目标不少于 {c['target']} 个。",
                'action': f"优先在盲区侧新增/引入约 {gap} 个{c['label']}服务点，并用步行算路复核可达性。",
            })
    if blind_status == 'ok' and blind_spots:
        severe = [s for s in blind_spots if s['severity'] >= 2]
        recs.append({
            'priority': '高' if severe else '中',
            'title': '优先治理多设施叠加盲区',
            'reason': f"识别到 {len(blind_spots)} 个采样盲区点，其中 {len(severe)} 个同时缺少两类及以上关键设施。",
            'action': '将叠加盲区作为选址候选区域，结合道路穿越障碍、公共空间和人口数据进一步实地核验。',
        })
    if not recs:
        recs.append({
            'priority': '低', 'title': '保持覆盖并做动态监测',
            'reason': '当前样例的已知基础服务覆盖达到设定目标。',
            'action': '按季度复算等时圈与POI变化，关注施工和道路改造造成的可达性变化。',
        })
    return recs


def _reachability_metrics(center: dict, matrix: list[dict], threshold_s: int, area_m2: float) -> dict[str, Any]:
    naive_radius_m = threshold_s * settings.baseline_walk_speed_mps
    naive_area_m2 = math.pi * naive_radius_m**2
    detours = []
    time_penalties = []
    for row in matrix:
        straight = haversine_m(center['lat'], center['lng'], row['lat'], row['lng'])
        route_dist = float(row.get('distance_m') or 0)
        duration = float(row.get('duration_s') or 0)
        if straight > 20 and route_dist > 0:
            detours.append(route_dist / straight)
        naive_time = straight / settings.baseline_walk_speed_mps if straight > 0 else 0
        if naive_time > 0 and duration > 0:
            time_penalties.append(duration / naive_time)
    return {
        'baseline_walk_speed_mps': settings.baseline_walk_speed_mps,
        'naive_radius_m': round(naive_radius_m),
        'naive_circle_area_km2': round(naive_area_m2 / 1_000_000, 3),
        'isochrone_to_naive_area_ratio': round(area_m2 / naive_area_m2, 3) if naive_area_m2 else None,
        'median_route_detour_ratio': round(statistics.median(detours), 3) if detours else None,
        'median_time_penalty_ratio': round(statistics.median(time_penalties), 3) if time_penalties else None,
        'note': '直线基线仅用于说明“直线半径”与真实路网测时的差异，不属于官方公共服务评价标准。',
    }


async def run_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    mode = payload['mode']
    raw_center = dict(payload['center'])
    center = dict(raw_center)
    provider: Any
    warnings: list[str] = []

    if mode == 'real':
        provider = BaiduMapClient()
        coord_type = payload.get('coord_type', 'bd09ll')
        if coord_type != 'bd09ll':
            converted = await provider.convert_coordinates([center], coord_type)
            center = converted[0]
    else:
        provider = DemoMapProvider(center)
        warnings.append('当前为离线模拟模式：POI、路网耗时和诊断结果均为明确标注的模拟数据，不代表真实城市情况。')

    try:
        bearings = int(payload['sample_bearings'])
        threshold_s = int(payload['threshold_minutes']) * 60
        radii = [500, 900, 1300, 1700]
        destinations = _radial_destinations(center, bearings, radii)
        matrix = await provider.route_matrix_walking(center, destinations)
        if len(matrix) != len(destinations):
            raise BaiduAPIError('route_matrix_walking', '算路样本数量与采样点不一致。')
        for source, row in zip(destinations, matrix):
            row['_bearing'] = source['_bearing']
            row['_radius'] = source['_radius']
            row['_origin_lat'] = center['lat']
            row['_origin_lng'] = center['lng']
            row['reachable'] = bool(row.get('duration_s', 0) and row['duration_s'] <= threshold_s)
        valid_route_samples = len([r for r in matrix if r.get('duration_s', 0) > 0])
        route_sample_success_ratio = valid_route_samples / len(matrix) if matrix else 0
        if route_sample_success_ratio < 0.8:
            raise BaiduAPIError('isochrone', f'有效算路样本比例仅 {route_sample_success_ratio:.0%}，不足以可靠生成等时圈。')

        polygon, iso_warnings, iso_diagnostics = _build_isochrone(matrix, threshold_s, bearings, radii)
        warnings.extend(iso_warnings)
        if len(polygon) < max(8, bearings // 2):
            raise BaiduAPIError('isochrone', '有效算路方向不足，无法生成稳定等时圈。')

        async def fetch_cat(key: str, spec: dict) -> tuple[str, list[dict]]:
            query = f"{key}|{spec['query']}" if mode == 'demo' else spec['query']
            items = await provider.search_nearby(query, center['lat'], center['lng'], payload['poi_radius_meters'])
            for p in items:
                p['category'] = key
                p['category_label'] = spec['label']
                if p.get('distance_m') in (None, ''):
                    p['distance_m'] = round(haversine_m(center['lat'], center['lng'], p['lat'], p['lng']))
            return key, items

        groups = await asyncio.gather(*(fetch_cat(k, s) for k, s in FACILITY_CATALOG.items()), return_exceptions=True)
        pois: list[dict] = []
        unavailable_categories: set[str] = set()
        category_errors: dict[str, str] = {}
        for (key, spec), group in zip(FACILITY_CATALOG.items(), groups):
            if isinstance(group, Exception):
                unavailable_categories.add(key)
                category_errors[key] = str(group)[:160]
                warnings.append(f"{spec['label']} POI 检索失败：{str(group)[:120]}。该类别将标记为“未知”，不会误判为“缺失”。")
                continue
            _, items = group
            pois.extend(items)

        pois = _dedupe_pois(pois)

        coverage, score, known_weight = _coverage_and_score(pois, polygon, unavailable_categories)
        blind, blind_status = _blind_spots(center, pois, polygon, unavailable_categories)
        if blind_status != 'ok':
            warnings.append(blind_status)

        score_after_blind = score
        if score is not None and blind_status == 'ok':
            score_after_blind = max(0.0, round(score - min(20, len(blind) * 1.2), 1))
        data_confidence = round(
            100 * (0.55 * route_sample_success_ratio + 0.45 * (known_weight / 100)), 1
        )
        recommendations = _recommendations(coverage, blind, blind_status)

        representative_route = None
        inside_pois = [p for p in pois if point_in_polygon(p['lat'], p['lng'], polygon)]
        if inside_pois:
            nearest = min(
                inside_pois,
                key=lambda p: p.get('distance_m') if isinstance(p.get('distance_m'), (int, float)) else 10**9,
            )
            try:
                route = await provider.walking_route(center, nearest)
                if route:
                    representative_route = {'to': nearest['name'], 'category': nearest['category_label'], **route}
            except Exception as exc:
                warnings.append(f"代表性步行路径规划失败，主分析仍保留：{str(exc)[:100]}")

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        area_m2 = polygon_area_m2(polygon)
        stats = provider.stats.summary()
        reachability = _reachability_metrics(center, matrix, threshold_s, area_m2)

        return {
            'mode': mode,
            'data_notice': 'SIMULATED_OFFLINE_DATA' if mode == 'demo' else 'LIVE_BAIDU_MAP_API',
            'center_input': raw_center,
            'center_bd09': center,
            'center_name': payload['center_name'],
            'city': payload['city'],
            'coord_type_input': payload.get('coord_type', 'bd09ll'),
            'threshold_minutes': payload['threshold_minutes'],
            'sample_bearings': bearings,
            'sample_radii_m': radii,
            'poi_radius_meters': payload['poi_radius_meters'],
            'isochrone': polygon,
            'isochrone_diagnostics': iso_diagnostics,
            'route_samples': matrix,
            'route_sample_success_ratio': round(route_sample_success_ratio, 3),
            'area_m2': round(area_m2),
            'area_km2': round(area_m2 / 1_000_000, 3),
            'reachability_comparison': reachability,
            'pois': pois,
            'coverage': coverage,
            'coverage_score_before_blind_penalty': score,
            'health_score': score_after_blind,
            'score_interpretation': '基于已成功获取的设施类别归一化计算；未知类别不按0分处理。',
            'data_confidence_percent': data_confidence,
            'unavailable_categories': sorted(unavailable_categories),
            'category_errors': category_errors,
            'blind_spots': blind,
            'blind_spots_status': blind_status,
            'blind_spot_definition': '采样点周边1公里内，菜市场/药店/小学任一关键类别缺失；关键类别数据未知时不输出缺失结论。仅用于规划筛查，需结合人口与实地条件复核。',
            'recommendations': recommendations,
            'representative_route': representative_route,
            'api_stats': stats,
            'warnings': warnings,
            'algorithm': {
                'isochrone': f'{bearings}方向×4半径扇形采样；使用百度步行批量算路耗时，以保守单调包络+径向线性插值形成近似{payload["threshold_minutes"]}分钟可达边界。',
                'poi': f'按设施类别调用百度 Place 圆形检索，每类最多翻页 {settings.baidu_poi_max_pages} 页；去重后用点在多边形内判断统计等时圈覆盖。',
                'blind_spots': '对1公里范围网格采样，检查菜市场/药店/小学的1公里邻近覆盖；关键类别检索失败时停止输出“无设施”结论。',
                'caveat': '等时圈为API测时采样插值近似，不等同于底层路网全量洪泛；符合题目鼓励的无底层路网条件下空间插值/扇形采样思路。',
            },
            'elapsed_ms': elapsed_ms,
        }
    finally:
        await provider.aclose()
