# 百度地图 API 权限与真实联调指南

## 1. AK 类型

项目后端调用 Web 服务 API，应配置**服务端 AK**。不要把服务端 AK 写入浏览器 JavaScript。

如果未来增加百度 JSAPI 交互地图，需要单独按百度平台要求配置浏览器类型 AK / Referer 白名单，不建议与服务端 AK 混用。

## 2. 当前代码真实调用

- 地理编码：`/geocoding/v3/`
- 坐标转换：`/geoconv/v2/`
- Place 圆形检索：`/place/v2/search`
- 步行批量算路：`/routematrix/v2/walking`
- 步行路线规划：`/directionlite/v1/walking`
- 静态图：`/staticimage/v2`

## 3. 最小权限检查

`.env`：

```env
BAIDU_MAP_AK=真实服务端AK
```

执行：

```bash
python scripts/check_baidu_api.py
```

脚本不打印 AK，只输出各服务成功/失败和安全统计。

## 4. 常见失败排查

### status 非 0

记录服务名、状态和安全摘要。不要把 AK 复制到聊天/Issue。

### QPS / 配额

先降低并发：

```env
BAIDU_CONCURRENCY=1
```

然后减少反复完整分析，利用缓存。RouteMatrix 配额按路线组合而不是 HTTP 批次数理解。

### Place 结果太少

检查：

- query 词是否合适；
- `radius_limit=true` 是否符合预期；
- `BAIDU_POI_MAX_PAGES`；
- 中心点是否正确；
- 服务权限/配额。

### RouteMatrix 边界异常

看“算法质量诊断”：

- 有效样本率
- 单调纠正数
- 截断方向
- 外推方向

不要只看最终多边形。

## 5. 正式实测建议

1. `check_baidu_api.py`。
2. 网页真实跑一个社区。
3. 下载 JSON + GeoJSON，人工检查 2～3 个 POI 和若干采样路线。
4. 调整参数后固定最终参数。
5. `run_real_benchmark.py` 跑两个社区。
6. 保存截图、报告、API 统计、真实耗时。
