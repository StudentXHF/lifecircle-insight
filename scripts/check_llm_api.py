from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services.llm import LLMAPIError, generate_planning_brief


SMOKE_RESULT = {
    'mode': 'demo',
    'center_name': '模型连通性检查样例',
    'city': '上海市',
    'threshold_minutes': 15,
    'area_km2': 1.0,
    'health_score': 80,
    'data_confidence_percent': 100,
    'coverage': {},
    'blind_spots_status': 'ok',
    'blind_spots': [],
    'reachability_comparison': {},
    'isochrone_diagnostics': {},
    'route_sample_success_ratio': 1.0,
    'recommendations': [],
    'warnings': [],
}


async def main() -> int:
    if not settings.llm_ready:
        print('LLM 配置不完整；请检查 LLM_API_BASE_URL / LLM_API_KEY / LLM_MODEL。')
        return 2
    try:
        result = await generate_planning_brief(SMOKE_RESULT)
    except LLMAPIError as exc:
        print('LLM_CHECK_FAILED:', exc.safe_message)
        return 1
    print(
        'LLM_CHECK_OK',
        f'model={result["model"]}',
        f'chars={len(result["text"])}',
        f'evidence_mode={result["evidence_mode"]}',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
