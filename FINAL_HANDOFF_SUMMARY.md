# 圈析智图 v3.0.0-rc3｜正式提交前交付总览

## 当前定位

本版本已完成真实百度 API 联调、真实社区 A/B、真实 WebGL 地图、模型解读与正式材料生成，是进入身份信息填写、仓库上传和视频录制阶段的**正式提交准备版**。

## 已完成

- 完整 FastAPI + SQLite + 原生 HTML/CSS/JavaScript 工程。
- 离线模拟 / 真实百度 API 双模式严格区分。
- 百度 Web API：地理编码、坐标转换、Place 多页 POI、RouteMatrix Walking、DirectionLite Walking、Static Image。
- 16 方向 x 4 半径默认扇形采样；RouteMatrix 批量拆分；900 秒阈值插值。
- 非单调耗时保守包络、有效样本率、截断/外推等算法诊断。
- 六类设施覆盖、`unknown != 0`、1 km 菜市场/药店/小学服务盲区。
- 直线圆与真实路网差异量化。
- 并发、重试、timeout、内存 + SQLite TTL API 缓存。
- HTTP 请求数与路线配额单元分开统计。
- 历史分析与 Markdown / HTML / CSV / JSON / GeoJSON / ZIP 导出。
- **v3.0 城市空间可视化中枢**：
  - 真实城市 3D：百度 JSAPI GL WebGL，倾斜/旋转、500m/1km 距离圈、等时圈、POI、盲区、探针、路况、卫星、自动环绕、可选 Style ID；
  - 数字孪生表达：无浏览器 AK 时可离线演示；
  - 分析热力图：用于解释算法证据；
  - 全宽主舞台 + 沉浸演示模式，改善旧版视图拥挤问题。
- 浏览器 `BAIDU_MAP_BROWSER_AK` 与服务端 `BAIDU_MAP_AK` 完全分离。
- Windows/Linux 启动、Docker、GitHub Actions、MIT、治理文件。
- 真实 API smoke test 脚本、两社区真实 benchmark 脚本、发布前密钥检查。
- 当前自动化测试：**35 passed**；style_check / JavaScript syntax 均通过。
- 已在 Windows 本机实际验证 `start.bat`、首页/健康检查/配置、离线分析、历史记录和 7 类导出；浏览器桌面、移动端、沉浸模式与无浏览器 AK 占位均已走查，控制台 0 error / 0 warning。
- 真实 API 最小检查五项全部成功；免费账户并发已收紧为 1。
- 真实 A/B：张江镇街道级样例 42.7 分、4 个盲区；徐家汇街道级样例 100 分、0 个盲区，均为 100% 数据置信度。
- 真实张江镇 WebGL 地图完成浏览器走查并保存截图；七类真实结果导出均已校验。
- 可选 Qwen3.6-35B-A3B 模型连接成功；AI 只解读后端筛选过的证据，不读取 AK、POI 名称或坐标，不改变算法结果。
- 正式材料：作品介绍、技术设计报告、4 分钟视频稿、答辩 Q&A、最终执行清单及 PDF。

## 真实性边界

1. 本交付已使用参赛者配置完成一次真实联调；公开发布包排除 `.env`、运行数据库与密钥，真实证据以 `LIVE_BAIDU_MAP_API` 标识和结构化报告留存。
2. Canvas 数字孪生中的楼体、树木、道路属于增强表达层，不冒充 BIM / 地籍 / 实景重建。
3. 真实城市 3D 的建筑精细程度取决于百度地图目标区域数据覆盖、缩放和浏览器 GPU。
4. Style ID 为空不影响功能，只表示使用百度默认底图样式。

## 参赛者 / Codex 最后阶段任务

1. 填写团队 / 学校 / 联系方式。
2. 上传 GitHub/Gitee，确认 CI、README、MIT 和无密钥泄露。
3. 按 `submission/03_*` 录制约 4 分钟真实演示视频并上传可公开播放链接。
4. 将仓库与视频 URL 写入正式材料，按 `submission/05_*` 做最后提交核对。
5. 现场若重复实跑，保持 `BAIDU_CONCURRENCY=1`；无需为 Style ID 专门付费或阻塞提交。

## 给 Codex

打开当前项目根目录，新建对话并执行：

```text
CODEX_CONTINUE_PROMPT.md
```

Codex 的职责应是**真实 AK 联调、真实 A/B、证据替换、最终发布检查**，而不是重构已经完成的主体。
