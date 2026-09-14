from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx

from app.config import settings


class LLMAPIError(RuntimeError):
    def __init__(self, safe_message: str):
        super().__init__(safe_message)
        self.safe_message = safe_message


def _chat_completions_url(base_url: str) -> str:
    clean = base_url.rstrip('/')
    if clean.endswith('/chat/completions'):
        return clean
    return clean + '/chat/completions'


def _evidence_payload(result: dict[str, Any]) -> dict[str, Any]:
    coverage: list[dict[str, Any]] = []
    for item in result.get('coverage', {}).values():
        coverage.append(
            {
                'label': item.get('label'),
                'status': item.get('status'),
                'count_in_isochrone': item.get('count_in_isochrone'),
                'target': item.get('target'),
            }
        )
    comparison = result.get('reachability_comparison') or {}
    diagnostics = result.get('isochrone_diagnostics') or {}
    return {
        'data_mode': 'real_baidu_api' if result.get('mode') == 'real' else 'simulated_offline',
        'center_name': result.get('center_name'),
        'city': result.get('city'),
        'threshold_minutes': result.get('threshold_minutes'),
        'area_km2': result.get('area_km2'),
        'health_score': result.get('health_score'),
        'data_confidence_percent': result.get('data_confidence_percent'),
        'coverage': coverage,
        'blind_spots_status': result.get('blind_spots_status'),
        'blind_spot_count': len(result.get('blind_spots') or []),
        'blind_spot_missing_categories': sorted(
            {
                label
                for spot in result.get('blind_spots') or []
                for label in spot.get('missing_labels') or []
            }
        ),
        'reachability_comparison': {
            key: comparison.get(key)
            for key in (
                'isochrone_to_naive_area_ratio',
                'median_route_detour_ratio',
                'median_time_penalty_ratio',
            )
        },
        'quality': {
            'route_sample_success_ratio': result.get('route_sample_success_ratio'),
            'valid_bearings': diagnostics.get('valid_bearings'),
            'truncated_bearings': diagnostics.get('truncated_bearings'),
            'extrapolated_bearings': diagnostics.get('extrapolated_bearings'),
        },
        'deterministic_recommendations': [
            {
                'priority': item.get('priority'),
                'title': item.get('title'),
                'reason': item.get('reason'),
                'action': item.get('action'),
            }
            for item in result.get('recommendations') or []
        ],
        'warnings': (result.get('warnings') or [])[:12],
    }


def _extract_content(payload: dict[str, Any]) -> str:
    try:
        choice = payload['choices'][0]
        message = choice['message']
        content = message['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMAPIError('模型响应缺少 choices[0].message.content。') from exc
    if isinstance(content, list):
        content = ''.join(
            str(item.get('text', ''))
            for item in content
            if isinstance(item, dict) and item.get('type') in {'text', 'output_text'}
        )
    if not isinstance(content, str) or not content.strip():
        reasoning = message.get('reasoning_content', '') if isinstance(message, dict) else ''
        reasoning_length = len(reasoning) if isinstance(reasoning, str) else 0
        finish_reason = choice.get('finish_reason', 'unknown') if isinstance(choice, dict) else 'unknown'
        raise LLMAPIError(
            f'模型返回空正文（finish_reason={finish_reason}, reasoning_chars={reasoning_length}）。'
        )
    return content.strip()[:8000]


async def generate_planning_brief(result: dict[str, Any]) -> dict[str, Any]:
    if not settings.llm_ready:
        raise LLMAPIError('模型未配置完整。')
    evidence = _evidence_payload(result)
    system = (
        '你是城市公共服务规划报告编辑。只能解释用户提供的结构化证据，不得补充地点事实、'
        '人口、道路原因、设施名称或因果判断。不得修改评分、等时圈、POI、盲区和置信度。'
        '若 data_mode=simulated_offline，开头必须明确“以下仅为离线模拟解读，不代表真实社区结论”。'
        '若字段 unknown 或有 warnings，必须明确待核验。用中文输出，控制在 350～600 字，依次给出：'
        '总体判断、三项证据、行动优先级、核验边界。不要输出 Markdown 表格。'
    )
    body = {
        'model': settings.llm_model,
        'messages': [
            {'role': 'system', 'content': system},
            {
                'role': 'user',
                'content': '请基于以下 JSON 生成规划解读：\n' + json.dumps(evidence, ensure_ascii=False),
            },
        ],
        'temperature': 0.2,
        'max_tokens': 1600,
        'stream': False,
        'chat_template_kwargs': {'enable_thinking': False},
    }
    headers = {
        'Authorization': f'Bearer {settings.llm_api_key}',
        'Content-Type': 'application/json',
    }
    timeout = httpx.Timeout(max(5, settings.llm_timeout_seconds))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                _chat_completions_url(settings.llm_api_base_url),
                headers=headers,
                json=body,
            )
    except httpx.TimeoutException as exc:
        raise LLMAPIError('模型请求超时；确定性分析结果不受影响。') from exc
    except httpx.HTTPError as exc:
        raise LLMAPIError('模型服务网络连接失败；确定性分析结果不受影响。') from exc
    if response.status_code >= 400:
        raise LLMAPIError(f'模型服务返回 HTTP {response.status_code}；请检查地址、密钥和模型名。')
    try:
        payload = response.json()
    except ValueError as exc:
        raise LLMAPIError('模型服务未返回有效 JSON。') from exc
    return {
        'text': _extract_content(payload),
        'model': settings.llm_model,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'evidence_mode': evidence['data_mode'],
        'notice': '模型只负责解释已有指标，不参与地图事实、评分、等时圈或盲区计算。',
    }
