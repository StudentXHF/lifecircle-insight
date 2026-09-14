# 圈析智图（LifeCircle Insight）

> **2026 上海开源软件应用创新大赛｜开源 AI 工具赛道｜百度地图命题** 参赛工程 v3.0.0-rc3（正式提交准备版）
>
> 基于百度地图开放能力的“15 分钟生活圈”智能体检与规划助手。

## 1. 一句话说明

输入上海任意社区/街道中心点，系统不再用“直线半径画圆”代替步行可达性，而是调用百度地图步行路网能力，对周边分散采样点批量测时，构造近似 15 分钟步行等时圈；随后检索医疗、小学、菜市场、药店、超市和养老设施，识别关键服务覆盖与“1 km 服务盲区”，给出可解释规划建议，并导出可验收成果。

## 2. 对照赛题的核心实现

- **坐标能力**：WGS84 / GCJ02 → 百度 BD09LL（geoconv）。
- **POI 检索**：百度 Place 圆形检索，支持多页拉取、去重；单类别失败时标记“未知”，不会误判为“0 个设施”。
- **批量步行算路**：RouteMatrix Walking；默认 16 方向 × 4 半径 = 64 条路线，自动按 50 条上限拆批。
- **等时圈**：扇形采样 + API 实测步行时间 + 保守单调包络 + 径向插值，生成近似 15 分钟连通边界。
- **路网差异诊断**：同时输出直线步行基线、面积比、路径绕行系数、时间惩罚系数，直观说明“直线圆”和路网可达性的差异。
- **盲区识别**：在等时圈内网格采样，检查每个点周边 1 km 是否缺少菜市场、药店或小学；若关键类别 API 数据未知，则停止输出“缺失”结论。
- **代表性路径**：DirectionLite Walking 生成一条代表性真实步行路线指标。
- **可视化**：数字孪生 3D 城市沙盘、分析热力图、百度 JSAPI GL WebGL 真实城市地图（可选）、等时圈、POI、盲区、覆盖条形图、路网差异与算法质量诊断；真实分析模式仍可代理百度静态地图快照。
- **工程优化**：有界并发、指数退避重试、内存 + SQLite TTL 缓存、API 配额单元估算、严格 AK 脱敏。
- **成果导出**：Markdown、独立 HTML、CSV、JSON、GeoJSON、ZIP。
- **AI 规划解读**：可选调用 OpenAI 兼容模型，仅对已生成的结构化证据做自然语言归纳；不参与地图事实、体检分、盲区或等时圈计算。

## 3. 两种模式严格区分

### A. 离线模拟模式（无需 AK）

用于演示 UI、算法链路、异常逻辑和导出。POI 与路网耗时来自仓库内明确标注的模拟数据；页面、报告和文件都标明 `SIMULATED_OFFLINE_DATA`。**不得把离线结果用于真实社区结论。**

### B. 真实百度 API 模式

复制：

```text
.env.example -> .env
```

至少填写：

```env
BAIDU_MAP_AK=您的服务端AK
```

如果希望启用“真实城市地图”页签的 WebGL 3D 底图，再单独创建百度地图**浏览器端** AK：

```env
BAIDU_MAP_BROWSER_AK=您的浏览器端AK
```

`BAIDU_MAP_AK` 是服务端 AK，绝不会返回前端。`BAIDU_MAP_BROWSER_AK` 属于 JSAPI 正常需要在浏览器加载的公开型 AK，因此必须与服务端 AK 分开创建，并在百度地图控制台配置 Referer 白名单。

## 4. Windows 最短启动

要求 Python 3.11+。解压后双击：

```text
start.bat
```

首次启动会在项目目录创建 `.venv`。浏览器访问：

```text
http://127.0.0.1:8015
```

手动方式：

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8015
```


## 4.1 三种可视化视图

分析完成后，主视图可切换：

1. **数字孪生 3D**：纯前端 Canvas 生成的沉浸式城市表达层，显示等时圈、道路、楼体、树木、POI 与盲区。楼体/树木是分析表达，不声称等同真实 BIM 或地籍建筑。
2. **真实城市 3D**：配置 `BAIDU_MAP_BROWSER_AK` 后加载百度 JSAPI GL WebGL 底图，以高缩放、倾斜与旋转体现城市空间距离感，叠加 15min 等时圈、500m/1km 参考圈、POI、盲区和抽样路网探针；支持自动环绕、实时路况、卫星/标准底图切换。可选 `BAIDU_MAP_STYLE_ID` 应用个性化底图风格。
3. **分析热力图**：保留确定性分析图，用于解释路网耗时采样、等时圈、POI 与盲区。

结果页新增 **沉浸演示模式**：一键把空间可视化主舞台放大到全屏，更适合录制演示视频和现场答辩。

即使没有浏览器 AK，数字孪生 3D 与分析热力图仍可离线使用；真实城市地图会明确显示配置提示，不会伪造真实底图。

## 5. 建议的真实联调顺序

配置 AK 后，不要直接长时间反复跑完整分析，先执行：

```bat
.venv\Scripts\python.exe scripts\check_baidu_api.py
```

它会低成本验证地理编码、Place、RouteMatrix Walking 和 DirectionLite Walking，不打印 AK。

核心服务正常后，再运行网页真实模式。需要生成两社区真实对比时执行：

```bat
.venv\Scripts\python.exe scripts\run_real_benchmark.py
```

脚本会地理编码两个上海样例地址并实际分析，生成：

```text
docs/真实对比测试报告_自动生成.md
docs/真实对比测试报告_自动生成.json
```

该文件只有在真实 AK 成功调用后才会产生，避免用模拟数据“填满报告”。本交付已于 2026-09-14 完成一次真实联调和两社区对比；免费账户建议保持 `BAIDU_CONCURRENCY=1`，不要连续重复运行完整 Benchmark。

可选模型连接检查：

```bat
.venv\Scripts\python.exe scripts\check_llm_api.py
```

模型密钥只由后端读取。前端必须由用户手动点击“生成 AI 规划解读”，系统不会因打开历史记录而自动消耗模型额度。

## 6. 一键工程验收

Windows：

```text
verify.bat
```

跨平台：

```bash
python scripts/verify.py
```

内部依次执行代码风格检查、`compileall` 和 pytest。

当前 v3.0.0-rc3 在 Windows / Python 3.13.7 的自动化测试结果为 **35 passed**；`start.bat`、真实/离线 HTTP 主链路、真实 WebGL 地图、模型解读与全部七种导出均已实际验收。完整记录见 `docs/实际测试记录.md`。

## 7. Docker

```bash
cp .env.example .env
# 填 BAIDU_MAP_AK
docker compose up --build
```

访问 `http://127.0.0.1:8015`。

## 8. 主要配置

```env
HOST=127.0.0.1
PORT=8015
REQUEST_TIMEOUT_SECONDS=20
BAIDU_MAP_AK=
BAIDU_MAP_BROWSER_AK=
# 可选：百度“个性化地图”Style ID，用于真实城市 3D 底图美化
BAIDU_MAP_STYLE_ID=
BAIDU_CONCURRENCY=1
BAIDU_RETRY_TIMES=2
BAIDU_CACHE_TTL_SECONDS=900
BAIDU_POI_MAX_PAGES=3
DEFAULT_SAMPLE_BEARINGS=16
DEFAULT_POI_RADIUS_METERS=1800
MAX_ANALYSIS_SECONDS=120
BASELINE_WALK_SPEED_MPS=1.2
```

`BASELINE_WALK_SPEED_MPS` 只用于“直线步行基线”对比，不用于替代百度路网算路，也不是官方公共服务标准。

## 9. 项目结构

```text
app/                         FastAPI 后端
  services/analysis.py       分析编排、等时圈、覆盖、盲区、建议
  services/baidu.py          百度 Web API 客户端、重试、分页、统计
  services/cache.py          SQLite TTL API 缓存
  services/exporter.py       MD/HTML/CSV/JSON/GeoJSON/ZIP
static/                      原生 HTML/CSS/JS 工作台；Canvas 数字孪生 + 百度 JSAPI GL 可选真实城市地图
sample_data/                 明确标注的离线模拟数据
tests/                       自动化测试
scripts/check_baidu_api.py   最小真实 API 权限检查
scripts/check_llm_api.py     最小模型兼容性检查
scripts/run_real_benchmark.py 两社区真实对比脚本
scripts/verify.py            一键验收
.github/                     CI、Issue、PR 模板
docs/                        设计、评分追踪、测试、提交清单
submission/                  准提交作品文档、视频与邮件材料
```

## 10. 算法诚信边界

1. 等时圈为“分散点 API 测时 + 径向插值”的近似可达区域，不声称获取了百度底层路网拓扑。
2. POI API 缺失或失败不等于现实中“没有设施”；未知类别明确标为未知。
3. 盲区是规划筛查结果，不替代人口、用地、政策和现场踏勘。
4. “体检分”是本项目可解释的内部诊断指标，不是比赛官方评分或政府评价分。
5. 离线模拟绝不包装成真实百度地图数据。

## 11. 开源工程

- MIT License
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `GOVERNANCE.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `CITATION.cff`
- GitHub Actions
- Issue / Pull Request 模板

## 12. 提交前真正剩余的工作

主体源码、真实百度 API、真实 WebGL 地图、两社区 A/B、模型解读、测试、导出、安全检查和正式 PDF 均已准备。提交前仍需参赛者本人完成：

1. 填写团队、学校/单位、负责人和联系方式。
2. 上传实际 GitHub/Gitee 仓库，确认 CI 通过且 `.env`、运行数据库未提交。
3. 按讲解稿录制并上传真实演示视频，填写可公开播放链接。
4. 在正式提交前按当日官网/报名确认邮件复核材料字段和截止时间。
5. 若现场再次实跑真实模式，保持 `BAIDU_CONCURRENCY=1`，避免免费账户并发预警。

如果后续交给 Codex 做本机真实 AK 联调、真实 A/B 和最终提交替换，直接使用 `CODEX_CONTINUE_PROMPT.md`。

正式提交资料优先查看 `submission/01_*` 至 `submission/05_*`。

## 13. 发布前密钥/打包自检

普通本地检查（允许本地存在 `.env` / 运行数据库，仅提示）：

```bash
python scripts/release_preflight.py
```

制作公开提交 ZIP 前，在一个不含 `.env` 和运行数据库的干净副本执行：

```bash
python scripts/release_preflight.py --strict
python scripts/make_release_zip.py --out 圈析智图_release.zip
```

`make_release_zip.py` 默认排除 `.env`、`.venv`、`data/` 运行数据库、`exports/` 临时导出、缓存和 Python 字节码，减少误把密钥或本地运行垃圾提交出去的风险。
