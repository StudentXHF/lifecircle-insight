from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import BASE_DIR, settings
from app.services.analysis import run_analysis
from app.services.baidu import BaiduMapClient


async def run_case(case: dict) -> dict:
    started = time.perf_counter()
    client = BaiduMapClient()
    try:
        loc = await client.geocode(case['address'], case.get('city', '上海市'))
        geocode_stats = client.stats.summary()
    finally:
        await client.aclose()
    payload = {
        'mode': 'real',
        'center': {'lng': loc['lng'], 'lat': loc['lat']},
        'center_name': case['name'],
        'city': case.get('city', '上海市'),
        'coord_type': 'bd09ll',
        'threshold_minutes': int(case.get('threshold_minutes', 15)),
        'sample_bearings': int(case.get('sample_bearings', 16)),
        'poi_radius_meters': int(case.get('poi_radius_meters', 1800)),
    }
    result = await run_analysis(payload)
    analysis_stats = result['api_stats']
    result['benchmark_api_stats'] = {
        key: geocode_stats.get(key, 0) + analysis_stats.get(key, 0)
        for key in (
            'request_count', 'cache_hits', 'success_count', 'failed_count',
            'total_latency_ms', 'quota_units_estimated',
        )
    }
    result['benchmark_api_stats']['calls'] = geocode_stats.get('calls', []) + analysis_stats.get('calls', [])
    result['benchmark_elapsed_ms'] = int((time.perf_counter() - started) * 1000)
    return result


def _benchmark_stats(result: dict) -> dict:
    return result.get('benchmark_api_stats') or result['api_stats']


def report_markdown(results: list[dict], source_cases: list[dict]) -> str:
    lines = [
        '# 圈析智图｜真实社区对比测试报告', '',
        f'- 生成时间：{datetime.now().isoformat(timespec="seconds")}',
        '- 数据来源：百度地图 Web 服务 API 实时/缓存结果',
        '- 注意：本报告由脚本真实执行后生成，不能用离线模拟数据替代。', '',
        '## 对比总表', '',
        '| 样例 | 等时圈面积 km² | 体检分 | 数据置信度 | 盲区点 | HTTP请求 | 配额单元估算 | 耗时 ms |',
        '|---|---:|---:|---:|---:|---:|---:|---:|'
    ]
    for r in results:
        stats = _benchmark_stats(r)
        lines.append(
            f"| {r['center_name']} | {r['area_km2']} | {r.get('health_score','数据不足')} | "
            f"{r.get('data_confidence_percent','-')}% | {len(r['blind_spots'])} | "
            f"{stats.get('request_count',0)} | {stats.get('quota_units_estimated',0)} | "
            f"{r.get('benchmark_elapsed_ms', r['elapsed_ms'])} |"
        )
    lines += ['', '## 方法一致性', '',
              '两个样例采用相同的步行阈值、扇形采样、POI 分类、盲区规则与评分规则，差异主要来自真实路网和设施分布。', '']
    for case, r in zip(source_cases, results):
        cmp = r.get('reachability_comparison') or {}
        lines += [
            f"## {r['center_name']}", '',
            f"- 输入地址：{case['address']}",
            f"- 百度 BD09 坐标：{r['center_bd09']['lng']:.6f}, {r['center_bd09']['lat']:.6f}",
            f"- 等时圈面积：{r['area_km2']} km²",
            f"- 等时圈/直线圆面积比：{cmp.get('isochrone_to_naive_area_ratio','-')}",
            f"- 路径绕行系数中位数：{cmp.get('median_route_detour_ratio','-')}",
            f"- 体检分：{r.get('health_score','数据不足')}",
            f"- 数据置信度：{r.get('data_confidence_percent','-')}%",
            f"- 盲区采样点：{len(r['blind_spots'])}", '',
            '### 设施覆盖', ''
        ]
        for c in r['coverage'].values():
            if c.get('status') == 'unknown':
                lines.append(f"- {c['label']}：未知（API 检索失败，未按缺失处理）")
            else:
                lines.append(f"- {c['label']}：圈内 {c['count_in_isochrone']} / 检索 {c['count_total']} / 目标 {c['target']}")
        if r['warnings']:
            lines += ['', '### 待核验 / 警告', ''] + [f'- {x}' for x in r['warnings']]
        lines.append('')
    lines += [
        '## 结论边界', '',
        '本项目的等时圈是“离散 API 测时 + 径向插值”的近似结果，不等同于获取底层路网后进行全量图搜索。',
        '盲区结果用于规划筛查，不替代人口、用地、政策和现场踏勘。',
    ]
    return '\n'.join(lines)


def report_csv(results: list[dict]) -> str:
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow([
        'case', 'area_km2', 'health_score', 'data_confidence_percent',
        'isochrone_to_naive_area_ratio', 'median_route_detour_ratio',
        'median_time_penalty_ratio', 'blind_spot_count', 'http_request_count',
        'cache_hits', 'quota_units_estimated', 'elapsed_ms',
    ])
    for result in results:
        stats = _benchmark_stats(result)
        comparison = result.get('reachability_comparison') or {}
        writer.writerow([
            result['center_name'], result['area_km2'], result.get('health_score'),
            result.get('data_confidence_percent'), comparison.get('isochrone_to_naive_area_ratio'),
            comparison.get('median_route_detour_ratio'), comparison.get('median_time_penalty_ratio'),
            len(result.get('blind_spots', [])), stats.get('request_count', 0),
            stats.get('cache_hits', 0), stats.get('quota_units_estimated', 0),
            result.get('benchmark_elapsed_ms', result.get('elapsed_ms')),
        ])
    return '\ufeff' + out.getvalue()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', default=str(BASE_DIR / 'scripts' / 'benchmark_cases.example.json'))
    parser.add_argument('--out', default=str(BASE_DIR / 'docs' / '真实对比测试报告_自动生成.md'))
    args = parser.parse_args()
    if not settings.baidu_map_ak:
        print('BAIDU_MAP_AK 未配置，不能生成真实对比报告。')
        return 2
    cases = json.loads(Path(args.cases).read_text(encoding='utf-8'))
    if not isinstance(cases, list) or len(cases) < 2:
        print('benchmark cases 至少需要 2 个样例。')
        return 2
    results = []
    for case in cases:
        print('Running:', case['name'])
        results.append(await run_case(case))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_markdown(results, cases), encoding='utf-8')
    raw = out.with_suffix('.json')
    raw.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    summary_csv = out.with_suffix('.csv')
    summary_csv.write_text(report_csv(results), encoding='utf-8')
    print('Written:', out)
    print('Raw:', raw)
    print('CSV:', summary_csv)
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
