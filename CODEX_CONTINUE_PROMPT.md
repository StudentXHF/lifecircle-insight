# 给 Codex 的本地真实联调、真实数据补齐与最终提交提示词

你现在接手的是一个已经进入**最终提交候选阶段**的竞赛项目，不是从零项目。

项目：**圈析智图（LifeCircle Insight）——基于百度地图开放能力的 15 分钟生活圈智能体检与规划助手**  
赛事：2026 上海开源软件应用创新大赛  
赛道：开源 AI 工具赛道  
命题：百度地图“15 分钟生活圈”任务书

当前工作区就是项目根目录。

## 总目标

不要重写架构，不要再做无边界功能扩张。

你的任务是把当前 v3.0 RC 项目从“主体工程完成”推进到：

1. 真实百度 API 全链路通过；
2. 真实城市 3D 地图稳定；
3. 两个上海真实社区 A/B 实测完成；
4. 文档中的 `[待真实实测]` 全部用真实结果替换；
5. 正式 PDF 重新生成并检查；
6. 公开仓库干净、CI 绿色；
7. 演示视频录制素材准备齐全；
8. 最终发布包不含密钥、运行数据库、缓存和测试垃圾。

只有遇到账号授权、AK 权限、Git 远端授权、真实身份信息或视频上传这种必须由用户参与的事项时再询问。

---

## 一、先完整阅读

至少阅读：

- `README.md`
- `FINAL_HANDOFF_SUMMARY.md`
- `docs/赛题任务书_原始.pdf`
- `docs/官方赛题与规则核验.md`
- `docs/项目说明书.md`
- `docs/架构与关键算法说明.md`
- `docs/评分点逐项对照表.md`
- `docs/赛题-实现追踪矩阵.md`
- `docs/3D可视化与地图配置.md`
- `docs/百度地图API权限与实测指南.md`
- `docs/实际测试记录.md`
- `docs/已知限制与后续工作.md`
- `submission/01_圈析智图_作品介绍文档_正式稿_待实测补数.md`
- `submission/02_圈析智图_技术设计报告_正式稿_待实测补数.md`
- `submission/03_演示视频讲解稿_4分钟正式版.md`
- `submission/04_答辩核心卖点与Q&A.md`
- `submission/05_最终提交与答辩执行清单.md`
- `app/`
- `static/`
- `tests/`
- `scripts/`

如果 README 与磁盘代码不一致，以磁盘真实代码和测试结果为准，并修正文档。

---

## 二、当前已实现，不要重做

1. FastAPI + SQLite + 原生 HTML/CSS/JS。
2. 离线模拟完整闭环。
3. 地理编码 / 坐标转换 / Place / RouteMatrix Walking / DirectionLite / Static Image。
4. Place 多页检索、去重、unknown 语义。
5. 默认 16 方向 × 4 半径，RouteMatrix 自动批量拆分。
6. RouteMatrix 有效样本质量门槛。
7. 非单调耗时保守包络 + 900 秒径向插值。
8. 15min 等时圈。
9. 六类设施覆盖。
10. 1 km 菜市场 / 药店 / 小学服务盲区。
11. 路网 vs 直线圆诊断。
12. 数据置信度与算法质量诊断。
13. 内存 + SQLite TTL 缓存、并发、重试、timeout。
14. Markdown / HTML / CSV / JSON / GeoJSON / ZIP 导出。
15. Docker / start.bat / CI / MIT / 开源治理文件。
16. `scripts/check_baidu_api.py`。
17. `scripts/run_real_benchmark.py`。
18. 三层可视化：真实城市 3D、数字孪生表达、分析热力图。
19. 沉浸演示模式。
20. 500m / 1km 距离参考层。
21. submission 下已准备正式稿框架、视频稿和答辩 Q&A。

不要为了“更 AI”让大模型参与地图事实判断。

---

## 三、密钥规则

`.env` 可能存在：

```env
BAIDU_MAP_AK=
BAIDU_MAP_BROWSER_AK=
BAIDU_MAP_STYLE_ID=
```

### BAIDU_MAP_AK

服务端 Web Service AK。

绝对不能：

- 打印完整值；
- 写入日志；
- 返回前端；
- 写入提交文档；
- 提交 Git。

### BAIDU_MAP_BROWSER_AK

浏览器 JSAPI 4.0 使用，本来就会发送到浏览器。

必须：

- 与服务端 AK 分开；
- 使用浏览器应用类型；
- 配置 Referer 白名单；
- 不复制到服务端 API 逻辑中。

### BAIDU_MAP_STYLE_ID

可选百度个性化地图样式 ID。用于答辩视觉，不是服务端密钥。

---

## 四、第一阶段：工程预检

开始前：

```bash
git status
```

不要覆盖用户未提交改动。

使用项目 `.venv`，不要全局 pip install，不要污染 Anaconda base。

运行：

```bash
python scripts/verify.py
```

当前自动化测试基线应至少为仓库记录值。若失败，先修回全绿。

再运行：

```bash
python scripts/release_preflight.py
```

不要在有真实 `.env` 的工作目录强行做 strict 发布检查；真正发布时应制作干净副本 / release zip。

---

## 五、第二阶段：低成本真实百度 API Smoke Test

运行：

```bash
python scripts/check_baidu_api.py
```

实际验证：

- geocoding
- geoconv（如脚本覆盖）
- Place
- RouteMatrix Walking
- DirectionLite Walking

记录：

- 成功 / 失败；
- HTTP/API 状态；
- 脱敏错误；
- 实际耗时。

如当前百度 API 响应字段与代码不兼容：

1. 最小修改适配；
2. 新增回归测试；
3. 不用硬编码成功结果。

---

## 六、第三阶段：真实城市 3D 联调

重点验证 `BAIDU_MAP_BROWSER_AK`。

当前目标是百度 JSAPI 4.0 WebGL，不要求改成 JSAPI Three。

验证：

1. 真实底图能够加载；
2. zoom 18 左右时城市空间清晰；
3. tilt / heading 正常；
4. 自动环绕正常；
5. 500m / 1km 距离参考圈正常；
6. 15min 等时圈叠加正确；
7. POI 标记不过度遮挡；
8. 盲区圈正常；
9. 路网探针抽样正常；
10. 卫星 / 标准底图切换正常；
11. 实时路况按钮正常或安全降级；
12. 沉浸演示模式正常；
13. `BAIDU_MAP_STYLE_ID` 有值时个性化地图正常；没有值时不影响使用。

注意：

- 建筑三维表现取决于百度地图目标区域覆盖和缩放级别；
- 不得把数字孪生 Canvas 楼体冒充真实建筑；
- 如果某浏览器不支持 Marker3D，允许安全降级；
- 不要因为 3D 视觉问题破坏核心分析。

如果真实底图建筑效果不理想，先尝试：

- 更合适的上海中心点；
- zoom / tilt / heading；
- 百度个性化地图样式；

不要立刻引入 Node / Three.js 新构建链。

---

## 七、第四阶段：真实完整分析

用一个上海真实社区：

1. 地址转坐标；
2. 真实模式；
3. 开始体检；
4. 检查 RouteMatrix；
5. 检查 Place 六类召回；
6. 检查等时圈；
7. 检查盲区；
8. 检查 DirectionLite；
9. 检查静态地图；
10. 检查真实 3D 地图叠加；
11. 检查 API 统计；
12. 检查第二次运行缓存命中；
13. 下载 MD / HTML / CSV / JSON / GeoJSON / ZIP，并逐个打开。

随机人工抽查至少：

- 3 个 POI；
- 2 条步行路线 / 采样；
- 2 个盲区点。

如百度地图可见信息与 API 返回明显不一致，记录为待核验，不要擅自“修数据”。

---

## 八、第五阶段：两社区 A/B Benchmark

运行：

```bash
python scripts/run_real_benchmark.py
```

如果默认地址不适合最终展示，可以选择两个具有明显差异、且真实 3D 底图表现较好的上海社区，但必须把地址写入报告。

最终需要：

- `docs/真实对比测试报告_自动生成.md`
- `docs/真实对比测试报告_自动生成.json`
- 两社区截图
- 测试日期
- 中心坐标
- 参数
- 等时圈面积
- 绕行系数
- 设施覆盖
- 盲区
- HTTP / 配额单元
- 总耗时

做出 1-2 条**有真实数据支持**的对比结论，不要为了故事性强行解释。

---

## 九、第六阶段：正式文档替换与 PDF

主要源稿：

- `submission/01_圈析智图_作品介绍文档_正式稿_待实测补数.md`
- `submission/02_圈析智图_技术设计报告_正式稿_待实测补数.md`

要求：

1. 替换全部 `[待真实实测]`；
2. 加入真实 A/B 表；
3. 加入 2-4 张真实截图；
4. 填团队 / 学校；
5. 填公开仓库 URL；
6. 填真实视频 URL；
7. 重新生成正式 PDF；
8. 渲染 PDF 检查中文、表格、分页、图片；
9. PDF 文件名去掉“待实测 / 草稿”。

不得编造：

- 用户数；
- 获奖概率；
- 合作单位；
- 商用情况；
- 性能成绩；
- 社区真实结论。

---

## 十、第七阶段：演示视频

使用：

- `submission/03_演示视频讲解稿_4分钟正式版.md`
- `submission/04_答辩核心卖点与Q&A.md`

录制时：

- 60 秒内必须出现真实城市 3D 和 15min 等时圈；
- 3D 只做视觉钩子，必须马上切回算法证据；
- 拍到 500m / 1km 距离参考；
- 拍到盲区；
- 拍到质量诊断；
- 拍到 API / 配额 / 缓存；
- 拍到结构化导出；
- 拍到真实 A/B；
- 拍到开源仓库与 CI；
- 不拍密钥。

视频必须上传到公开可播放地址，不要拿项目首页当视频链接。

---

## 十一、第八阶段：公开仓库和发行包

用户授权 Git 远端后：

- 推 GitHub / Gitee；
- `.env` 不入库；
- `data/lifecircle.db` 不入库；
- `.pytest_cache` 不入库；
- 运行时 `exports/` 不入库；
- CI 绿色；
- 建议 tag：`v1.0.0-contest`。

生成公开发行包：

```bash
python scripts/make_release_zip.py --out 圈析智图_v1.0.0_contest_release.zip
```

然后在干净解压目录运行：

```bash
python scripts/release_preflight.py --strict
python scripts/verify.py
```

---

## 十二、评分优先级

命题任务书：

- 功能正确性与覆盖率 40%
- API 深度调用与工程优化 30%
- 产品交互与用户体验 15%
- 开源工程规范 15%

所以真实联调稳定以后，优先级应为：

**真实证据 > 文档与视频 > 开源可复现 > 小幅 UI 微调 > 新功能。**

不要无限追加低价值功能。

---

## 十三、最终报告给用户

完成后必须报告：

A. 真实百度 API 哪些接口实际通过。  
B. 浏览器真实城市 3D 是否通过，使用什么 zoom / tilt / style。  
C. 两个真实社区、测试日期和参数。  
D. 两社区核心对比表。  
E. 真实 API 请求 / 配额 / 总耗时。  
F. 发现和修复的兼容问题。  
G. 自动化测试通过数。  
H. 正式 PDF 路径。  
I. Git 仓库 / CI 状态。  
J. 演示视频状态。  
K. 最终 release ZIP 路径。  
L. 用户还必须亲自完成的事项。  
M. 最短提交 checklist。

不要只说“完成了”，必须给证据。
