from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, settings
from app.schemas import AnalysisRequest, CoordinateConvertRequest, GeocodeRequest
from app.services.analysis import run_analysis
from app.services.baidu import BaiduAPIError, BaiduMapClient
from app.services.exporter import write_export
from app.services.llm import LLMAPIError, generate_planning_brief
from app.storage import get_analysis, init_db, list_analyses, save_analysis

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title='圈析智图', version='3.0.0-rc3', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')


@app.get('/', response_class=HTMLResponse)
async def home() -> HTMLResponse:
    return HTMLResponse((BASE_DIR / 'static' / 'index.html').read_text(encoding='utf-8'))


@app.get('/api/health')
async def health() -> dict:
    return {'ok': True, 'app': settings.app_name, 'version': '3.0.0-rc3'}


@app.get('/api/config/status')
async def config_status() -> dict:
    return {
        'real_mode_ready': settings.real_mode_ready,
        'baidu_key_configured': bool(settings.baidu_map_ak),
        # 浏览器端 JSAPI GL AK 本来就会被浏览器加载，可单独返回；服务端 AK 仍绝不返回。
        'browser_map_ready': settings.browser_map_ready,
        'browser_map_ak': settings.baidu_map_browser_ak if settings.browser_map_ready else '',
        'browser_map_style_id': settings.baidu_map_style_id,
        'llm_configured': settings.llm_ready,
        'default_threshold_minutes': settings.default_threshold_minutes,
        'default_sample_bearings': settings.default_sample_bearings,
        'default_poi_radius_meters': settings.default_poi_radius_meters,
        'poi_max_pages': settings.baidu_poi_max_pages,
        'baseline_walk_speed_mps': settings.baseline_walk_speed_mps,
        'notice': '真实分析使用服务端 BAIDU_MAP_AK；真实城市 3D 视图使用独立浏览器端 BAIDU_MAP_BROWSER_AK，并可选 BAIDU_MAP_STYLE_ID。浏览器端 AK 请配置 Referer 白名单。',
    }


@app.post('/api/geocode')
async def geocode(req: GeocodeRequest) -> dict:
    if not settings.real_mode_ready:
        raise HTTPException(status_code=400, detail='BAIDU_MAP_AK 未配置，无法调用真实地理编码。')
    client = BaiduMapClient()
    try:
        result = await client.geocode(req.address, req.city)
        return {'result': result, 'api_stats': client.stats.summary()}
    except BaiduAPIError as exc:
        raise HTTPException(status_code=502, detail=exc.safe_message) from exc
    finally:
        await client.aclose()


@app.post('/api/coordinates/convert')
async def convert_coordinates(req: CoordinateConvertRequest) -> dict:
    if not settings.real_mode_ready:
        raise HTTPException(status_code=400, detail='BAIDU_MAP_AK 未配置，无法调用真实坐标转换。')
    client = BaiduMapClient()
    try:
        result = await client.convert_coordinates([p.model_dump() for p in req.points], req.source)
        return {'result': result, 'api_stats': client.stats.summary()}
    except BaiduAPIError as exc:
        raise HTTPException(status_code=502, detail=exc.safe_message) from exc
    finally:
        await client.aclose()


@app.post('/api/analyze')
async def analyze(req: AnalysisRequest) -> dict:
    if req.sample_bearings > settings.max_sample_bearings:
        raise HTTPException(status_code=400, detail=f'采样方向数不得超过 {settings.max_sample_bearings}。')
    if req.poi_radius_meters > settings.max_poi_radius_meters:
        raise HTTPException(status_code=400, detail=f'POI 半径不得超过 {settings.max_poi_radius_meters} 米。')
    if req.mode == 'real' and not settings.real_mode_ready:
        raise HTTPException(status_code=400, detail='真实模式不可用：请在 .env 配置 BAIDU_MAP_AK 后重启。')

    payload = req.model_dump()
    try:
        result = await asyncio.wait_for(run_analysis(payload), timeout=settings.max_analysis_seconds)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail=f'分析超过 {settings.max_analysis_seconds} 秒，已安全终止。请降低采样数或检查百度 API。') from exc
    except BaiduAPIError as exc:
        raise HTTPException(status_code=502, detail=f'{exc.service}: {exc.safe_message}') from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'分析失败：{type(exc).__name__}: {str(exc)[:180]}') from exc

    analysis_id = save_analysis(payload, result)
    return {'id': analysis_id, 'result': result}


@app.get('/api/analyses')
async def analyses(limit: int = 20) -> dict:
    return {'items': list_analyses(limit)}


@app.get('/api/analyses/{analysis_id}')
async def analysis_detail(analysis_id: int) -> dict:
    record = get_analysis(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail='分析记录不存在。')
    return record


@app.post('/api/analyses/{analysis_id}/ai-brief')
async def ai_brief(analysis_id: int) -> dict:
    record = get_analysis(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail='分析记录不存在。')
    if not settings.llm_ready:
        raise HTTPException(status_code=400, detail='模型未配置，确定性分析结果仍可正常使用。')
    try:
        return await generate_planning_brief(record['result'])
    except LLMAPIError as exc:
        raise HTTPException(status_code=502, detail=exc.safe_message) from exc


@app.get('/api/analyses/{analysis_id}/static-map.png')
async def static_map(analysis_id: int) -> Response:
    record = get_analysis(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail='分析记录不存在。')
    if record['result']['mode'] != 'real':
        raise HTTPException(status_code=400, detail='离线模拟记录没有真实百度地图静态图。')
    client = BaiduMapClient()
    try:
        image = await client.static_map_bytes(
            center=record['result']['center_bd09'],
            polygon=record['result']['isochrone'],
            pois=record['result']['pois'],
            blind_spots=record['result'].get('blind_spots', []),
        )
        return Response(content=image, media_type='image/png', headers={'Cache-Control': 'private, max-age=300'})
    except BaiduAPIError as exc:
        raise HTTPException(status_code=502, detail=exc.safe_message) from exc
    finally:
        await client.aclose()


@app.get('/api/analyses/{analysis_id}/export/{kind}')
async def export_analysis(analysis_id: int, kind: str) -> FileResponse:
    record = get_analysis(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail='分析记录不存在。')
    if kind not in {'md', 'html', 'json', 'geojson', 'poi.csv', 'blind.csv', 'zip'}:
        raise HTTPException(status_code=400, detail='不支持的导出类型。')
    path = write_export(record, kind)
    return FileResponse(path, filename=path.name)
