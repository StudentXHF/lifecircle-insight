# 外部 API 与引用来源说明

## 比赛

- 2026 上海开源软件应用创新大赛：https://www.oschina.net/os2026/
- 用户取得的百度地图命题任务书：`docs/赛题任务书_原始.pdf`

## 百度地图开放平台

核心 Web 服务：

- 地理编码：https://lbsyun.baidu.com/
- 坐标转换 Geoconv：https://lbsyun.baidu.com/
- Place API：https://lbsyun.baidu.com/docs/webapi?title=placev2%2Fguide%2Fwebservice-placeapi%2Fcircle
- RouteMatrix：https://lbsyun.baidu.com/docs/webapi?title=routematrix%2Froutchtout
- Walking RouteMatrix：https://lbsyun.baidu.com/docs/webapi?title=routematrix%2Froutchtout-walk
- DirectionLite Walking：https://lbsyun.baidu.com/
- Static Image：https://lbsyun.baidu.com/

本仓库只实现 API 调用代码，不重新分发百度地图数据。真实运行时应遵守百度地图开放平台的最新服务条款、配额和 AK 使用规则。

## Python 依赖

见 `requirements.txt`：FastAPI、Uvicorn、httpx、Pydantic、python-dotenv、pytest。

项目自有代码使用 MIT License。第三方依赖继续遵循各自许可证；详见 `docs/依赖与开源许可说明.md`。
