from __future__ import annotations

import csv
import html
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import BASE_DIR

EXPORT_DIR = BASE_DIR / 'exports'
EXPORT_DIR.mkdir(exist_ok=True)


def _safe_cell(value: Any) -> str:
    text = '' if value is None else str(value)
    if text.startswith(('=', '+', '-', '@', '\t', '\r')):
        text = "'" + text
    return text


def _basename(record: dict[str, Any]) -> str:
    raw = record['result'].get('center_name', 'analysis')
    allowed = '-_一二三四五六七八九十上海浦东社区圈析智图'
    safe = ''.join(ch if ch.isalnum() or ch in allowed else '_' for ch in raw)[:36]
    return f"圈析智图_{record['id']}_{safe or 'analysis'}"


def _score_text(value: Any) -> str:
    return '数据不足' if value is None else f'{value} / 100'


def markdown_report(record: dict[str, Any]) -> str:
    r = record['result']
    mode = '真实百度地图 API' if r['mode'] == 'real' else '离线模拟（非真实城市数据）'
    cmp = r.get('reachability_comparison') or {}
    lines = [
        '# 圈析智图｜15分钟生活圈体检报告',
        '',
        f"- 分析编号：{record['id']}",
        f"- 模式：{mode}",
        (
            f"- 中心点：{r['center_name']}（{r['center_bd09']['lng']:.6f}, "
            f"{r['center_bd09']['lat']:.6f}，BD09）"
        ),
        f"- 城市：{r['city']}",
        f"- 步行阈值：{r['threshold_minutes']} 分钟",
        f"- 近似等时圈面积：{r['area_km2']} km²",
        f"- 综合体检分：{_score_text(r.get('health_score'))}",
        f"- 数据置信度：{r.get('data_confidence_percent', '未计算')}%",
        '',
        '## 真实路网 vs 直线基线',
        '',
        f"- 直线基线速度：{cmp.get('baseline_walk_speed_mps', '-')} m/s（仅用于方法对比）",
        f"- 直线基线半径：{cmp.get('naive_radius_m', '-')} m",
        f"- 直线圆面积：{cmp.get('naive_circle_area_km2', '-')} km²",
        f"- 等时圈/直线圆面积比：{cmp.get('isochrone_to_naive_area_ratio', '-')} ",
        f"- 路径绕行系数中位数：{cmp.get('median_route_detour_ratio', '-')} ",
        f"- 实际耗时/直线估时中位数：{cmp.get('median_time_penalty_ratio', '-')} ",
        '',
        '## 设施覆盖',
        '',
        '| 类别 | 状态 | 等时圈内 | 检索总数 | 目标 | 得分 |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for c in r['coverage'].values():
        if c.get('status') == 'unknown':
            lines.append(f"| {c['label']} | 未知 | - | - | {c['target']} | - |")
        else:
            lines.append(
                f"| {c['label']} | 已核验 | {c['count_in_isochrone']} | "
                f"{c['count_total']} | {c['target']} | {c['score']} |"
            )

    lines += ['', '## 服务盲区', '', r['blind_spot_definition'], '']
    if r.get('blind_spots_status') != 'ok':
        lines.append(f"> 本次盲区结果未输出：{r.get('blind_spots_status')}")
    elif r['blind_spots']:
        for i, spot in enumerate(r['blind_spots'][:10], 1):
            missing = '、'.join(spot['missing_labels'])
            lines.append(
                f"{i}. ({spot['lng']:.6f}, {spot['lat']:.6f})：缺少 {missing}；"
                f"距中心约 {spot['distance_from_center_m']} m。"
            )
    else:
        lines.append('未发现满足当前规则的盲区采样点。')

    lines += ['', '## 规划建议', '']
    for rec in r['recommendations']:
        lines.append(
            f"- **[{rec['priority']}] {rec['title']}**：{rec['reason']} {rec['action']}"
        )

    lines += ['', '## 方法与限制', '']
    lines.append(f"- 等时圈：{r['algorithm']['isochrone']}")
    lines.append(f"- POI：{r['algorithm']['poi']}")
    lines.append(f"- 盲区：{r['algorithm']['blind_spots']}")
    lines.append(f"- 限制：{r['algorithm']['caveat']}")
    if r['warnings']:
        lines += ['', '## 警告 / 待核验', ''] + [f"- {w}" for w in r['warnings']]

    stats = r['api_stats']
    lines += [
        '',
        '## API 调用统计',
        '',
        f"- 实际 HTTP 请求：{stats.get('request_count', 0)}",
        f"- 本地缓存命中：{stats.get('cache_hits', 0)}",
        f"- 估算计费/配额单元：{stats.get('quota_units_estimated', 0)}",
        f"- 分析总耗时：{r['elapsed_ms']} ms",
        '',
    ]
    if r['mode'] == 'demo':
        lines.append('> 本报告为离线模拟演示，不得作为真实社区规划结论。')
    return '\n'.join(lines)


def poi_csv(record: dict[str, Any]) -> bytes:
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(
        [
            'category',
            'category_label',
            'name',
            'address',
            'lng_bd09',
            'lat_bd09',
            'distance_m',
            'uid',
        ]
    )
    for poi in record['result']['pois']:
        writer.writerow(
            [
                _safe_cell(poi.get(k))
                for k in [
                    'category',
                    'category_label',
                    'name',
                    'address',
                    'lng',
                    'lat',
                    'distance_m',
                    'uid',
                ]
            ]
        )
    return ('\ufeff' + out.getvalue()).encode('utf-8')


def blind_csv(record: dict[str, Any]) -> bytes:
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(
        [
            'lng_bd09',
            'lat_bd09',
            'missing_labels',
            'severity',
            'distance_from_center_m',
        ]
    )
    for spot in record['result']['blind_spots']:
        writer.writerow(
            [
                _safe_cell(spot['lng']),
                _safe_cell(spot['lat']),
                _safe_cell('/'.join(spot['missing_labels'])),
                spot['severity'],
                spot['distance_from_center_m'],
            ]
        )
    return ('\ufeff' + out.getvalue()).encode('utf-8')


def geojson_payload(record: dict[str, Any]) -> dict[str, Any]:
    r = record['result']
    features: list[dict[str, Any]] = []
    if r.get('isochrone'):
        ring = [[p['lng'], p['lat']] for p in r['isochrone']]
        if ring and ring[0] != ring[-1]:
            ring.append(ring[0])
        features.append(
            {
                'type': 'Feature',
                'geometry': {'type': 'Polygon', 'coordinates': [ring]},
                'properties': {
                    'kind': 'isochrone',
                    'threshold_minutes': r['threshold_minutes'],
                    'center_name': r['center_name'],
                },
            }
        )
    for poi in r.get('pois', []):
        features.append(
            {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [poi['lng'], poi['lat']],
                },
                'properties': {
                    'kind': 'poi',
                    'name': poi['name'],
                    'category': poi['category'],
                    'category_label': poi['category_label'],
                    'address': poi.get('address', ''),
                },
            }
        )
    for spot in r.get('blind_spots', []):
        features.append(
            {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [spot['lng'], spot['lat']],
                },
                'properties': {
                    'kind': 'blind_spot',
                    'missing_labels': spot['missing_labels'],
                    'severity': spot['severity'],
                },
            }
        )
    return {
        'type': 'FeatureCollection',
        'name': 'LifeCircle Insight',
        'features': features,
    }


def html_report(record: dict[str, Any]) -> str:
    r = record['result']
    rows: list[str] = []
    for c in r['coverage'].values():
        if c.get('status') == 'unknown':
            rows.append(
                '<tr>'
                f"<td>{html.escape(c['label'])}</td>"
                '<td>未知</td><td>-</td><td>-</td>'
                f"<td>{c['target']}</td>"
                '</tr>'
            )
        else:
            rows.append(
                '<tr>'
                f"<td>{html.escape(c['label'])}</td>"
                '<td>已核验</td>'
                f"<td>{c['count_in_isochrone']}</td>"
                f"<td>{c['count_total']}</td>"
                f"<td>{c['target']}</td>"
                '</tr>'
            )

    recs = ''.join(
        '<li>'
        f"<b>[{html.escape(x['priority'])}] {html.escape(x['title'])}</b>："
        f"{html.escape(x['reason'])} {html.escape(x['action'])}"
        '</li>'
        for x in r['recommendations']
    )
    warns = (
        ''.join(f"<li>{html.escape(x)}</li>" for x in r.get('warnings', []))
        or '<li>无</li>'
    )
    mode = '真实百度地图 API' if r['mode'] == 'real' else '离线模拟'
    demo_note = ''
    if r['mode'] == 'demo':
        demo_note = (
            '<p class="note">本报告为离线模拟演示，不得作为真实社区规划结论。</p>'
        )

    css = '''
body{font-family:"Microsoft YaHei",sans-serif;max-width:980px;margin:36px auto;
padding:0 20px;color:#152238;line-height:1.7}
h1{color:#123b7a}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.k{padding:14px;border:1px solid #dce5f1;border-radius:12px}.k b{font-size:25px}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #dce5f1;
padding:8px;text-align:left}th{background:#f4f7fb}.note{background:#fff7db;padding:12px;
border-radius:10px}@media(max-width:700px){.kpis{grid-template-columns:1fr 1fr}}
'''.strip()

    body = f'''
<h1>圈析智图｜15分钟生活圈体检报告</h1>
<p>中心点：{html.escape(r['center_name'])}｜城市：{html.escape(r['city'])}｜模式：{mode}</p>
<div class="kpis">
  <div class="k">体检分<br><b>{html.escape(_score_text(r.get('health_score')))}</b></div>
  <div class="k">数据置信度<br><b>{r.get('data_confidence_percent', '-')}%</b></div>
  <div class="k">等时圈面积<br><b>{r['area_km2']}</b> km²</div>
  <div class="k">盲区采样点<br><b>{len(r['blind_spots'])}</b></div>
</div>
<h2>设施覆盖</h2>
<table>
  <thead><tr><th>类别</th><th>数据状态</th><th>圈内</th><th>检索总数</th><th>目标</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>
<h2>规划建议</h2><ul>{recs}</ul>
<h2>方法与边界</h2>
<p>{html.escape(r['algorithm']['isochrone'])}</p>
<p>{html.escape(r['algorithm']['caveat'])}</p>
<h2>警告 / 待核验</h2><ul>{warns}</ul>
{demo_note}
'''.strip()

    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>圈析智图体检报告</title>'
        f'<style>{css}</style></head><body>{body}</body></html>'
    )


def write_export(record: dict[str, Any], kind: str) -> Path:
    base = _basename(record)
    if kind == 'md':
        path = EXPORT_DIR / f'{base}_体检报告.md'
        path.write_text(markdown_report(record), encoding='utf-8')
    elif kind == 'html':
        path = EXPORT_DIR / f'{base}_体检报告.html'
        path.write_text(html_report(record), encoding='utf-8')
    elif kind == 'json':
        path = EXPORT_DIR / f'{base}_结构化结果.json'
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    elif kind == 'geojson':
        path = EXPORT_DIR / f'{base}_空间结果.geojson'
        path.write_text(
            json.dumps(geojson_payload(record), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    elif kind == 'poi.csv':
        path = EXPORT_DIR / f'{base}_POI清单.csv'
        path.write_bytes(poi_csv(record))
    elif kind == 'blind.csv':
        path = EXPORT_DIR / f'{base}_服务盲区.csv'
        path.write_bytes(blind_csv(record))
    elif kind == 'zip':
        path = EXPORT_DIR / f'{base}_交付包.zip'
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('体检报告.md', markdown_report(record))
            z.writestr('体检报告.html', html_report(record))
            z.writestr(
                '结构化结果.json',
                json.dumps(record, ensure_ascii=False, indent=2),
            )
            z.writestr(
                '空间结果.geojson',
                json.dumps(geojson_payload(record), ensure_ascii=False, indent=2),
            )
            z.writestr('POI清单.csv', poi_csv(record))
            z.writestr('服务盲区.csv', blind_csv(record))
            z.writestr(
                'README.txt',
                (
                    '圈析智图分析交付包\n'
                    f"生成时间：{datetime.now().isoformat(timespec='seconds')}\n"
                    f"模式：{record['result']['mode']}\n"
                    '坐标系：BD09LL\n'
                ),
            )
    else:
        raise ValueError('unsupported export kind')
    return path
