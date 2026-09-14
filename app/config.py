from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv('APP_NAME', '圈析智图')
    host: str = os.getenv('HOST', '127.0.0.1')
    port: int = _int('PORT', 8015)
    request_timeout_seconds: int = _int('REQUEST_TIMEOUT_SECONDS', 20)

    baidu_map_ak: str = os.getenv('BAIDU_MAP_AK', '').strip()
    # JSAPI GL 浏览器端 AK：浏览器地图必须在前端加载，因此此 AK 会发送到浏览器。
    # 请在百度地图控制台单独创建浏览器端 AK，并配置 Referer 白名单；不要复用服务端 AK。
    baidu_map_browser_ak: str = os.getenv('BAIDU_MAP_BROWSER_AK', '').strip()
    # 可选：百度地图开放平台“个性化地图”样式 ID，仅用于浏览器底图美化。
    baidu_map_style_id: str = os.getenv('BAIDU_MAP_STYLE_ID', '').strip()
    baidu_api_base: str = os.getenv('BAIDU_API_BASE', 'https://api.map.baidu.com').rstrip('/')
    baidu_concurrency: int = max(1, _int('BAIDU_CONCURRENCY', 1))
    baidu_retry_times: int = max(0, _int('BAIDU_RETRY_TIMES', 2))
    baidu_cache_ttl_seconds: int = max(0, _int('BAIDU_CACHE_TTL_SECONDS', 900))
    baidu_poi_max_pages: int = min(10, max(1, _int('BAIDU_POI_MAX_PAGES', 3)))

    default_threshold_minutes: int = _int('DEFAULT_THRESHOLD_MINUTES', 15)
    default_sample_bearings: int = _int('DEFAULT_SAMPLE_BEARINGS', 16)
    default_poi_radius_meters: int = _int('DEFAULT_POI_RADIUS_METERS', 1800)
    max_sample_bearings: int = _int('MAX_SAMPLE_BEARINGS', 32)
    max_poi_radius_meters: int = _int('MAX_POI_RADIUS_METERS', 3000)
    max_analysis_seconds: int = _int('MAX_ANALYSIS_SECONDS', 120)
    baseline_walk_speed_mps: float = max(0.6, min(2.0, _float('BASELINE_WALK_SPEED_MPS', 1.2)))

    llm_api_base_url: str = os.getenv('LLM_API_BASE_URL', '').rstrip('/')
    llm_api_key: str = os.getenv('LLM_API_KEY', '')
    llm_model: str = os.getenv('LLM_MODEL', '')
    llm_timeout_seconds: int = _int('LLM_TIMEOUT_SECONDS', 30)

    @property
    def real_mode_ready(self) -> bool:
        return bool(self.baidu_map_ak)

    @property
    def browser_map_ready(self) -> bool:
        return bool(self.baidu_map_browser_ak)

    @property
    def llm_ready(self) -> bool:
        return bool(self.llm_api_base_url and self.llm_api_key and self.llm_model)


settings = Settings()
