let currentId = null;
let currentResult = null;
let currentViz = 'twin';
let appConfig = {};
let baiduMap = null;
let baiduScriptPromise = null;
let baiduRenderSignature = '';
let orbitTimer = null;
let trafficEnabled = false;
let satelliteEnabled = false;
let presentationMode = false;

const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const CATEGORY_COLORS = {
  medical: '#3b82f6',
  primary_school: '#f59e0b',
  market: '#10b981',
  pharmacy: '#f43f5e',
  supermarket: '#06b6d4',
  elderly: '#8b5cf6',
  default: '#64748b'
};

function toast(msg) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3200);
}

function selectedMode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>'"]/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[c]));
}

function node(name, attrs = {}) {
  const n = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}

function updateModeNotice() {
  const real = selectedMode() === 'real';
  const el = $('runNotice');
  el.className = 'inline-notice ' + (real ? 'ok' : 'warn');
  el.textContent = real
    ? '真实模式：将实际调用百度地图 Web 服务 API，并消耗对应配额。真实 3D 城市底图另需浏览器端 BAIDU_MAP_BROWSER_AK。'
    : '当前为离线模拟：分析数据不会调用真实地图 API。若配置浏览器端 AK，可单独加载真实百度 3D 底图作为视觉参考，但分析结论仍属于模拟。';
}

async function loadConfig() {
  const r = await fetch('/api/config/status');
  appConfig = await r.json();
  const el = $('apiStatus');
  const analysis = appConfig.real_mode_ready ? '分析API已配置' : '分析API未配置';
  const map3d = appConfig.browser_map_ready ? '真实3D地图已配置' : '真实3D地图未配置';
  const llm = appConfig.llm_configured ? '模型解读已配置' : '模型解读未配置';
  el.textContent = `${analysis} · ${map3d} · ${llm}`;
  el.className = 'pill ' + ((appConfig.real_mode_ready || appConfig.browser_map_ready) ? 'ok' : 'muted');
  updateBaiduPlaceholder();
}

async function loadHistory() {
  const r = await fetch('/api/analyses');
  const d = await r.json();
  const box = $('history');
  if (!d.items.length) {
    box.textContent = '暂无记录';
    return;
  }
  box.innerHTML = '';
  for (const item of d.items) {
    const el = document.createElement('div');
    el.className = 'history-item';
    el.innerHTML = `<b>${escapeHtml(item.center_name)}</b><small>#${item.id} · ${item.mode === 'real' ? '真实' : '模拟'} · ${item.health_score ?? '数据不足'}${item.health_score == null ? '' : '分'}</small>`;
    el.onclick = () => openRecord(item.id);
    box.appendChild(el);
  }
}

function resetForm() {
  $('address').value = '';
  $('centerName').value = '【模拟】浦东科创社区样例';
  $('city').value = '上海市';
  $('lng').value = '121.601000';
  $('lat').value = '31.201000';
  $('coordType').value = 'bd09ll';
  $('threshold').value = 15;
  $('bearings').value = 16;
  $('poiRadius').value = 1800;
  document.querySelector('input[name="mode"][value="demo"]').checked = true;
  updateModeNotice();
  $('resultSection').classList.add('hidden');
  currentId = null;
  currentResult = null;
  setVizView('twin');
}

function payload() {
  return {
    mode: selectedMode(),
    center: { lng: Number($('lng').value), lat: Number($('lat').value) },
    center_name: $('centerName').value,
    city: $('city').value,
    coord_type: $('coordType').value,
    threshold_minutes: Number($('threshold').value),
    sample_bearings: Number($('bearings').value),
    poi_radius_meters: Number($('poiRadius').value)
  };
}

async function geocodeAddress() {
  if (selectedMode() !== 'real') {
    toast('地址转坐标仅在真实分析模式使用');
    return;
  }
  const address = $('address').value.trim();
  if (!address) {
    toast('请先输入地址');
    return;
  }
  const btn = $('geocodeBtn');
  btn.disabled = true;
  btn.textContent = '解析中…';
  try {
    const r = await fetch('/api/geocode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address, city: $('city').value })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '地理编码失败');
    $('lng').value = d.result.lng.toFixed(6);
    $('lat').value = d.result.lat.toFixed(6);
    $('coordType').value = 'bd09ll';
    if (!$('centerName').value || $('centerName').value.includes('模拟')) $('centerName').value = address;
    toast(`坐标已更新，置信度：${d.result.confidence ?? '未返回'}`);
  } catch (e) {
    toast('地址解析失败：' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '地址转坐标';
  }
}

async function analyze() {
  const btn = $('analyzeBtn');
  btn.disabled = true;
  btn.textContent = '正在计算…';
  try {
    const r = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload())
    });
    const d = await r.json();
    if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
    currentId = d.id;
    currentResult = d.result;
    renderResult(d.result, d.id);
    await loadHistory();
    toast('体检完成，数字孪生视图已更新');
  } catch (e) {
    toast('分析失败：' + e.message);
    console.error(e);
  } finally {
    btn.disabled = false;
    btn.textContent = '开始体检';
  }
}

async function openRecord(id) {
  const r = await fetch(`/api/analyses/${id}`);
  const d = await r.json();
  if (!r.ok) {
    toast(d.detail || '读取失败');
    return;
  }
  currentId = id;
  currentResult = d.result;
  const saved = d.payload || {};
  const modeInput = document.querySelector(`input[name="mode"][value="${d.result.mode}"]`);
  if (modeInput) modeInput.checked = true;
  $('centerName').value = saved.center_name || d.result.center_name || '';
  $('city').value = saved.city || d.result.city || '上海市';
  $('lng').value = Number(d.result.center_bd09.lng).toFixed(6);
  $('lat').value = Number(d.result.center_bd09.lat).toFixed(6);
  $('coordType').value = 'bd09ll';
  $('threshold').value = saved.threshold_minutes || d.result.threshold_minutes || 15;
  $('bearings').value = saved.sample_bearings || d.result.sample_bearings || 16;
  $('poiRadius').value = saved.poi_radius_meters || d.result.poi_radius_meters || 1800;
  updateModeNotice();
  renderResult(d.result, id);
  window.scrollTo({ top: 520, behavior: 'smooth' });
}

function safeRenderTwin(r) {
  const meta = $('twinMeta');
  try {
    renderTwin(r);
    return true;
  } catch (e) {
    console.error('Digital twin render failed:', e);
    if (meta) meta.textContent = `RENDER ERROR · ${e?.message || 'UNKNOWN'}`;
    return false;
  }
}

function scheduleTwinRender(r) {
  const draw = () => safeRenderTwin(r);
  // First draw immediately, then draw again after layout settles. This avoids
  // zero/old dimensions when a freshly revealed result section is rendered.
  draw();
  requestAnimationFrame(() => requestAnimationFrame(draw));
  setTimeout(draw, 120);
}

function renderResult(r, id) {
  $('resultSection').classList.remove('hidden');
  $('score').textContent = r.health_score ?? '—';
  $('confidence').textContent = r.data_confidence_percent ?? '—';
  $('area').textContent = r.area_km2;
  $('poiCount').textContent = Object.values(r.coverage).reduce((a, c) => a + (Number.isFinite(c.count_in_isochrone) ? c.count_in_isochrone : 0), 0);
  $('blindCount').textContent = r.blind_spots.length;
  $('apiCount').textContent = r.api_stats.request_count ?? 0;
  $('mapSubtitle').textContent = r.mode === 'demo'
    ? '数字孪生视图使用模拟分析数据；真实百度城市地图仅作为可选视觉参考，不会被冒充为真实分析。'
    : '真实模式：可在百度 3D 城市地图上叠加真实等时圈、POI 与盲区结果。';
  $('scoreNote').textContent = r.score_interpretation || '适配评分仅用于本项目规划比较，不代表官方评价。';

  renderCoverage(r.coverage);
  renderBlind(r);
  renderRecs(r.recommendations);
  renderRecSummary(r.recommendations);
  renderComparison(r.reachability_comparison || {});
  renderDiagnostics(r);
  renderTrace(r.api_stats, r.warnings);
  resetAiBrief();
  renderStageSummary(r);
  renderMap(r);
  scheduleTwinRender(r);

  for (const [key, kind] of [['expMd', 'md'], ['expHtml', 'html'], ['expPoi', 'poi.csv'], ['expBlind', 'blind.csv'], ['expJson', 'json'], ['expGeo', 'geojson'], ['expZip', 'zip']]) {
    $(key).href = `/api/analyses/${id}/export/${kind}`;
  }

  const real = $('realMapBox');
  if (r.mode === 'real') {
    real.classList.remove('hidden');
    $('realMapImg').src = `/api/analyses/${id}/static-map.png?t=${Date.now()}`;
  } else {
    real.classList.add('hidden');
    $('realMapImg').removeAttribute('src');
  }
  const preferredViz = (r.mode === 'real' && appConfig.browser_map_ready) ? 'baidu' : currentViz;
  setVizView(preferredViz);
}

function resetAiBrief() {
  const btn = $('aiBriefBtn');
  const notice = $('aiBriefNotice');
  const text = $('aiBriefText');
  if (!btn || !notice || !text) return;
  btn.disabled = !appConfig.llm_configured;
  btn.textContent = appConfig.llm_configured ? '生成解读' : '模型未配置';
  notice.textContent = appConfig.llm_configured
    ? '模型不会自动调用；点击后只发送脱敏后的汇总指标，不发送 AK。'
    : '模型未配置；确定性分析、评分、盲区与导出不受影响。';
  text.textContent = '';
  text.classList.add('hidden');
}

async function generateAiBrief() {
  if (!currentId || !appConfig.llm_configured) return;
  const btn = $('aiBriefBtn');
  const notice = $('aiBriefNotice');
  const text = $('aiBriefText');
  btn.disabled = true;
  btn.textContent = '模型解读中…';
  try {
    const response = await fetch(`/api/analyses/${currentId}/ai-brief`, { method: 'POST' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '模型解读失败');
    text.textContent = data.text;
    text.classList.remove('hidden');
    notice.textContent = `${data.notice} · ${data.model} · ${data.generated_at}`;
    toast('模型规划解读已生成');
  } catch (error) {
    notice.textContent = `模型解读失败：${error.message}`;
    toast('模型解读失败，确定性分析结果不受影响');
  } finally {
    btn.disabled = false;
    btn.textContent = '重新生成';
  }
}

function renderStageSummary(r) {
  const box = $('stageSummary');
  if (!box) return;
  const knownCoverage = Object.values(r.coverage || {}).filter((x) => x.status !== 'unknown');
  const knownCount = knownCoverage.reduce((a, x) => a + (Number.isFinite(x.count_in_isochrone) ? x.count_in_isochrone : 0), 0);
  const d = r.isochrone_diagnostics || {};
  const rows = [
    ['15min 面积', `${r.area_km2 ?? '—'} km²`],
    ['有效设施', `${knownCount} 个`],
    ['盲区点', `${(r.blind_spots || []).length} 个`],
    ['有效方向', `${d.valid_bearings ?? r.sample_bearings ?? '—'}`],
    ['数据置信度', `${r.data_confidence_percent ?? '—'}%`],
    ['分析模式', r.mode === 'real' ? '真实 API' : '离线模拟']
  ];
  box.innerHTML = rows.map(([k,v]) => `<div><span>${escapeHtml(k)}</span><b>${escapeHtml(v)}</b></div>`).join('');
}

function renderCoverage(cov) {
  const box = $('coverageBars');
  box.innerHTML = '';
  for (const c of Object.values(cov)) {
    const row = document.createElement('div');
    row.className = 'bar-row';
    if (c.status === 'unknown') {
      row.innerHTML = `<div class="bar-label">${escapeHtml(c.label)}</div><div class="bar-track unknown"><div class="bar-fill" style="width:100%"></div></div><div class="bar-value">待核验</div>`;
    } else {
      const pct = Math.min(100, Math.round((c.score || 0) / c.weight * 100));
      row.innerHTML = `<div class="bar-label">${escapeHtml(c.label)}</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div class="bar-value">${c.count_in_isochrone}/${c.target}</div>`;
    }
    box.appendChild(row);
  }
}

function renderBlind(r) {
  const box = $('blindTable');
  box.innerHTML = '';
  if (r.blind_spots_status !== 'ok') {
    box.innerHTML = `<div class="notice">${escapeHtml(r.blind_spots_status)}</div>`;
    return;
  }
  if (!r.blind_spots.length) {
    box.innerHTML = '<div class="notice">当前规则下未发现盲区采样点。</div>';
    return;
  }
  r.blind_spots.slice(0, 12).forEach((s, i) => {
    const el = document.createElement('div');
    el.className = 'blind-row';
    el.innerHTML = `<b>#${i + 1} 缺少：${escapeHtml(s.missing_labels.join('、'))}</b><small>坐标 ${s.lng.toFixed(6)}, ${s.lat.toFixed(6)} · 距中心约 ${s.distance_from_center_m} m · 严重度 ${s.severity}</small>`;
    box.appendChild(el);
  });
}

function renderRecs(items) {
  const box = $('recommendations');
  box.innerHTML = '';
  items.forEach((x) => {
    const el = document.createElement('div');
    el.className = 'rec';
    const cls = x.priority === '高' ? 'high' : (x.priority === '核验' ? 'verify' : '');
    el.innerHTML = `<b><span class="priority ${cls}">${escapeHtml(x.priority)}</span>${escapeHtml(x.title)}</b><p>${escapeHtml(x.reason)} ${escapeHtml(x.action)}</p>`;
    box.appendChild(el);
  });
}

function renderRecSummary(items) {
  const box = $('recSummary');
  box.innerHTML = '';
  items.slice(0, 3).forEach((x) => {
    const el = document.createElement('div');
    el.className = 'rec-mini';
    el.innerHTML = `<b>${escapeHtml(x.title)}</b><p>${escapeHtml(x.action)}</p>`;
    box.appendChild(el);
  });
}

function renderComparison(c) {
  const box = $('comparisonCards');
  box.innerHTML = '';
  const rows = [
    ['直线基线半径', c.naive_radius_m == null ? '—' : `${c.naive_radius_m} m`],
    ['直线圆面积', c.naive_circle_area_km2 == null ? '—' : `${c.naive_circle_area_km2} km²`],
    ['等时圈/直线圆', c.isochrone_to_naive_area_ratio ?? '—'],
    ['路径绕行系数', c.median_route_detour_ratio ?? '—'],
    ['耗时惩罚系数', c.median_time_penalty_ratio ?? '—']
  ];
  for (const [k, v] of rows) {
    const e = document.createElement('div');
    e.className = 'mini-card';
    e.innerHTML = `<span>${escapeHtml(k)}</span><b>${escapeHtml(v)}</b>`;
    box.appendChild(e);
  }
  const n = document.createElement('p');
  n.className = 'small muted-text';
  n.textContent = c.note || '';
  box.appendChild(n);
}

function renderDiagnostics(r) {
  const d = r.isochrone_diagnostics || {};
  $('algoDiagnostics').innerHTML = `<div class="diag-grid">
    <div><span>算路有效率</span><b>${Math.round((r.route_sample_success_ratio || 0) * 100)}%</b></div>
    <div><span>有效方向</span><b>${d.valid_bearings ?? '-'}</b></div>
    <div><span>单调修正</span><b>${d.monotonic_corrections ?? 0}</b></div>
    <div><span>边界截断</span><b>${d.truncated_bearings ?? 0}</b></div>
    <div><span>近中心外推</span><b>${d.extrapolated_bearings ?? 0}</b></div>
    <div><span>采样方向数</span><b>${r.sample_bearings ?? '-'}</b></div>
  </div>`;
}

function renderTrace(stats, warnings) {
  $('apiSummary').innerHTML = `HTTP 请求 <b>${stats.request_count ?? 0}</b> · 缓存命中 <b>${stats.cache_hits ?? 0}</b> · 估算配额单元 <b>${stats.quota_units_estimated ?? 0}</b> · API 累计耗时 <b>${stats.total_latency_ms ?? 0} ms</b>`;
  const box = $('apiTrace');
  box.innerHTML = '';
  const calls = stats.calls || [];
  if (!calls.length) box.innerHTML = '<div class="notice">无真实 API 调用；离线模拟工具不计网络请求。</div>';
  calls.forEach((c) => {
    const el = document.createElement('div');
    el.className = 'api-row';
    el.innerHTML = `<b>${escapeHtml(c.service)}</b><span class="${c.ok ? 'ok' : 'bad'}">${c.ok ? 'ok' : 'error'}</span><span>${c.cache_hit ? 'cache' : (c.latency_ms + ' ms')}</span><span>quota ${c.quota_units ?? 0}</span><span>${escapeHtml(c.note || '')}</span>`;
    box.appendChild(el);
  });
  const w = $('warnings');
  w.innerHTML = '';
  if (warnings?.length) {
    const el = document.createElement('div');
    el.className = 'warning-list';
    el.innerHTML = '<b>警告 / 待核验</b><br>' + warnings.map((x) => '• ' + escapeHtml(x)).join('<br>');
    w.appendChild(el);
  }
}

function spatialBounds(r) {
  const pts = [r.center_bd09, ...(r.isochrone || []), ...(r.pois || []), ...(r.blind_spots || []), ...(r.route_samples || [])].filter(Boolean);
  let minLng = Math.min(...pts.map((p) => p.lng));
  let maxLng = Math.max(...pts.map((p) => p.lng));
  let minLat = Math.min(...pts.map((p) => p.lat));
  let maxLat = Math.max(...pts.map((p) => p.lat));
  const padLng = (maxLng - minLng || 0.01) * 0.13;
  const padLat = (maxLat - minLat || 0.01) * 0.13;
  return { minLng: minLng - padLng, maxLng: maxLng + padLng, minLat: minLat - padLat, maxLat: maxLat + padLat };
}

function renderMap(r) {
  const svg = $('mapSvg');
  svg.innerHTML = '';
  const b = spatialBounds(r);
  const W = 800, H = 540;
  const px = (p) => 40 + (p.lng - b.minLng) / (b.maxLng - b.minLng) * (W - 80);
  const py = (p) => H - 40 - (p.lat - b.minLat) / (b.maxLat - b.minLat) * (H - 80);

  for (let i = 0; i < 11; i++) {
    const x = 50 + i * 70;
    svg.appendChild(node('path', { d: `M${x} 10 C${x - 35} 180 ${x + 45} 350 ${x} 530`, stroke: '#cbd5e1', 'stroke-width': i % 3 === 0 ? 5 : 2, fill: 'none', opacity: 0.62 }));
  }
  for (let i = 0; i < 8; i++) {
    const y = 40 + i * 68;
    svg.appendChild(node('path', { d: `M10 ${y} C220 ${y - 30} 520 ${y + 35} 790 ${y}`, stroke: '#d8e1ec', 'stroke-width': i % 3 === 0 ? 5 : 2, fill: 'none', opacity: 0.72 }));
  }

  const threshold = r.threshold_minutes * 60;
  (r.route_samples || []).forEach((s) => {
    const ratio = (s.duration_s || threshold * 2) / threshold;
    const fill = ratio <= 0.6 ? '#34d399' : ratio <= 1 ? '#fbbf24' : '#ef4444';
    svg.appendChild(node('circle', { cx: px(s), cy: py(s), r: 7, fill, opacity: 0.42 }));
  });

  const path = (r.isochrone || []).map((p, i) => (i ? 'L' : 'M') + px(p).toFixed(1) + ' ' + py(p).toFixed(1)).join(' ') + ' Z';
  svg.appendChild(node('path', { d: path, fill: '#60a5fa', 'fill-opacity': 0.22, stroke: '#2563eb', 'stroke-width': 4 }));
  (r.blind_spots || []).forEach((s) => svg.appendChild(node('circle', { cx: px(s), cy: py(s), r: 8, fill: '#7f1d1d', opacity: 0.82, stroke: '#fff', 'stroke-width': 2 })));
  (r.pois || []).forEach((p) => {
    const c = node('circle', { cx: px(p), cy: py(p), r: 6, fill: CATEGORY_COLORS[p.category] || CATEGORY_COLORS.default, stroke: '#fff', 'stroke-width': 2 });
    const title = node('title');
    title.textContent = `${p.category_label}｜${p.name}`;
    c.appendChild(title);
    svg.appendChild(c);
  });
  svg.appendChild(node('circle', { cx: px(r.center_bd09), cy: py(r.center_bd09), r: 11, fill: '#111827', stroke: '#fff', 'stroke-width': 4 }));
}

function seed(n) {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

function rgba(hex, alpha) {
  const h = hex.replace('#', '');
  const bigint = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  const r = (bigint >> 16) & 255, g = (bigint >> 8) & 255, b = bigint & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

function renderTwin(r) {
  const canvas = $('twinCanvas');
  if (!canvas) return;
  const wrap = $('twinWrap');
  const rect = wrap.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = rect.width > 0 ? Math.round(rect.width) : 900;
  const h = rect.height > 0 ? Math.round(rect.height) : 560;
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const sky = ctx.createLinearGradient(0, 0, 0, h);
  sky.addColorStop(0, '#dcecff');
  sky.addColorStop(0.48, '#eaf2fb');
  sky.addColorStop(1, '#d7e3ef');
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, w, h);

  const glow = ctx.createRadialGradient(w * 0.72, h * 0.16, 0, w * 0.72, h * 0.16, w * 0.42);
  glow.addColorStop(0, 'rgba(69,137,255,.26)');
  glow.addColorStop(1, 'rgba(69,137,255,0)');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, w, h);

  const b = spatialBounds(r);
  const project = (p) => {
    const nx = (p.lng - b.minLng) / (b.maxLng - b.minLng);
    const ny = (p.lat - b.minLat) / (b.maxLat - b.minLat);
    return {
      x: w * 0.16 + nx * w * 0.64 - ny * w * 0.12,
      y: h * 0.64 - ny * h * 0.30 + nx * h * 0.08
    };
  };

  const ground = [
    [w * 0.10, h * 0.25], [w * 0.85, h * 0.34], [w * 0.78, h * 0.84], [w * 0.04, h * 0.75]
  ];
  ctx.beginPath();
  ground.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.closePath();
  ctx.fillStyle = '#eef4fa';
  ctx.fill();
  ctx.strokeStyle = '#d0dceb';
  ctx.lineWidth = 2;
  ctx.stroke();

  function road(points, outer = 28, inner = 18) {
    ctx.beginPath();
    points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.strokeStyle = '#cbd7e5'; ctx.lineWidth = outer; ctx.stroke();
    ctx.strokeStyle = '#fbfdff'; ctx.lineWidth = inner; ctx.stroke();
    ctx.setLineDash([12, 11]); ctx.strokeStyle = '#d6deea'; ctx.lineWidth = 1.5; ctx.stroke(); ctx.setLineDash([]);
  }
  road([[w*.12,h*.63],[w*.28,h*.58],[w*.49,h*.59],[w*.69,h*.65],[w*.84,h*.68]],32,22);
  road([[w*.25,h*.40],[w*.36,h*.49],[w*.49,h*.59],[w*.60,h*.70],[w*.68,h*.80]],22,14);
  road([[w*.63,h*.42],[w*.59,h*.53],[w*.54,h*.63],[w*.49,h*.75]],18,11);

  // 用原始扇形采样半径绘制距离参考环，增强“实际距离感”。
  const ringSamples = r.route_samples || [];
  const ringRadii = [...new Set(ringSamples.map((x) => x._radius).filter((x) => Number.isFinite(x)))].sort((a,b2)=>a-b2).slice(0,3);
  ringRadii.forEach((radius, idx) => {
    const pts = ringSamples.filter((x) => x._radius === radius).sort((a,b2)=>(a._bearing||0)-(b2._bearing||0)).map(project);
    if (pts.length < 6) return;
    ctx.beginPath();
    pts.forEach((pt,i)=>i?ctx.lineTo(pt.x,pt.y):ctx.moveTo(pt.x,pt.y));
    ctx.closePath();
    ctx.setLineDash([8,8]);
    ctx.strokeStyle = idx === 0 ? 'rgba(96,165,250,.42)' : idx === 1 ? 'rgba(245,158,11,.30)' : 'rgba(100,116,139,.20)';
    ctx.lineWidth = idx === 0 ? 2 : 1.4;
    ctx.stroke();
    ctx.setLineDash([]);
  });

  const iso = (r.isochrone || []).map(project);
  if (iso.length) {
    ctx.beginPath();
    iso.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
    ctx.closePath();
    ctx.fillStyle = 'rgba(37,99,235,.13)'; ctx.fill();
    ctx.strokeStyle = '#2f6ff1'; ctx.lineWidth = 4; ctx.stroke();
    ctx.strokeStyle = 'rgba(96,165,250,.24)'; ctx.lineWidth = 13; ctx.stroke();
  }

  const samples = (r.route_samples || []).slice(0, 24);
  const buildings = [];
  for (let i = 0; i < samples.length; i += 3) {
    const p = project(samples[i]);
    buildings.push({
      x: p.x + (seed(i + 5) - .5) * 26,
      y: p.y + (seed(i + 15) - .5) * 18,
      width: 9 + seed(i + 25) * 8,
      depth: 13 + seed(i + 35) * 10,
      height: 22 + seed(i + 45) * 38,
      color: '#9fb0c7',
      label: ''
    });
  }
  const pois = [...(r.pois || [])].sort((a,b2)=>(a.distance_m||999999)-(b2.distance_m||999999)).slice(0, 12);
  pois.forEach((poi, i) => {
    const p = project(poi);
    buildings.push({
      x:p.x, y:p.y,
      width:12 + seed(i+80)*8,
      depth:18 + seed(i+90)*10,
      height:38 + (1-Math.min((poi.distance_m||800)/Math.max(r.poi_radius_meters||1800,1),1))*62 + (i%3)*7,
      color:CATEGORY_COLORS[poi.category] || CATEGORY_COLORS.default,
      label:i < 6 ? poi.category_label : ''
    });
  });

  function building(bld) {
    const {x,y,width:ww,depth:dd,height:hh,color} = bld;
    const dx = ww, dy = dd * .35;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x-ww, y-dy); ctx.lineTo(x, y); ctx.lineTo(x+ww, y-dy); ctx.lineTo(x, y-dd*.7); ctx.closePath();
    ctx.fillStyle='rgba(15,23,42,.08)'; ctx.fill();
    ctx.beginPath();
    ctx.moveTo(x-ww,y-dy-hh);ctx.lineTo(x,y-hh);ctx.lineTo(x,y);ctx.lineTo(x-ww,y-dy);ctx.closePath();
    ctx.fillStyle=rgba(color,.72);ctx.fill();
    ctx.beginPath();
    ctx.moveTo(x,y-hh);ctx.lineTo(x+ww,y-dy-hh);ctx.lineTo(x+ww,y-dy);ctx.lineTo(x,y);ctx.closePath();
    ctx.fillStyle=rgba(color,.95);ctx.fill();
    ctx.beginPath();
    ctx.moveTo(x-ww,y-dy-hh);ctx.lineTo(x,y-hh);ctx.lineTo(x+ww,y-dy-hh);ctx.lineTo(x,y-dd*.7-hh);ctx.closePath();
    ctx.fillStyle=rgba(color,.48);ctx.fill();ctx.strokeStyle='rgba(255,255,255,.6)';ctx.lineWidth=1;ctx.stroke();
    if (bld.label) {
      ctx.font='700 11px Microsoft YaHei, sans-serif';ctx.textAlign='center';ctx.fillStyle='#20324d';
      ctx.fillText(bld.label,x,y-hh-dd*.42-6);
    }
    ctx.restore();
  }
  buildings.sort((a,b2)=>a.y-b2.y).forEach(building);

  function tree(x,y,s=1){
    ctx.strokeStyle='#8b5a2b';ctx.lineWidth=2.5;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x,y-12*s);ctx.stroke();
    ctx.fillStyle='#2fb170';ctx.beginPath();ctx.arc(x,y-17*s,8*s,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='#67d392';ctx.beginPath();ctx.arc(x-6*s,y-13*s,6*s,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='#4dc47f';ctx.beginPath();ctx.arc(x+6*s,y-13*s,6*s,0,Math.PI*2);ctx.fill();
  }
  samples.slice(0,18).forEach((s,i)=>{const p=project(s);tree(p.x+(seed(i+110)-.5)*28,p.y+16+seed(i+120)*16,.8+seed(i+130)*.35)});

  const threshold = r.threshold_minutes * 60;
  samples.forEach((s) => {
    const p = project(s); const ratio=(s.duration_s||threshold*2)/threshold;
    ctx.fillStyle=ratio<=.6?'#34d399':ratio<=1?'#fbbf24':'#ef4444';
    ctx.globalAlpha=.85;ctx.beginPath();ctx.arc(p.x,p.y,4.4,0,Math.PI*2);ctx.fill();ctx.globalAlpha=1;
  });

  (r.blind_spots || []).slice(0,6).forEach((s) => {
    const p=project(s);
    ctx.fillStyle='rgba(239,68,68,.15)';ctx.beginPath();ctx.arc(p.x,p.y,19,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='#991b1b';ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.beginPath();ctx.arc(p.x,p.y,8,0,Math.PI*2);ctx.fill();ctx.stroke();
  });

  const center = project(r.center_bd09);
  building({x:center.x,y:center.y+6,width:18,depth:30,height:88,color:'#2563eb',label:'中心'});
  ctx.fillStyle='#111827';ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.beginPath();ctx.arc(center.x,center.y-8,6,0,Math.PI*2);ctx.fill();ctx.stroke();

  $('twinMeta').textContent = `${r.mode === 'real' ? 'REAL ANALYSIS' : 'SIMULATION'} · ${r.pois?.length || 0} POI · ${r.blind_spots?.length || 0} BLIND SPOTS`;
}

function updateBaiduPlaceholder() {
  const placeholder = $('baiduMapPlaceholder');
  const controls = $('baiduControls');
  if (!placeholder || !controls) return;
  placeholder.classList.toggle('hidden', !!appConfig.browser_map_ready);
  controls.classList.toggle('hidden', !appConfig.browser_map_ready);
}

function showBaiduError(message) {
  const placeholder = $('baiduMapPlaceholder');
  const controls = $('baiduControls');
  if (!placeholder) return;
  placeholder.classList.remove('hidden');
  if (controls) controls.classList.add('hidden');
  placeholder.innerHTML = `<div class="map-placeholder-icon">!</div><h3>真实城市地图加载失败</h3><p>${escapeHtml(message)}。请检查浏览器 AK 类型、Referer 白名单、网络和 WebGL 支持后重试。</p>`;
}

function loadBaiduMapApi() {
  if (window.BMapGL) return Promise.resolve(window.BMapGL);
  if (baiduScriptPromise) return baiduScriptPromise;
  if (!appConfig.browser_map_ready || !appConfig.browser_map_ak) return Promise.reject(new Error('BAIDU_MAP_BROWSER_AK 未配置'));
  baiduScriptPromise = new Promise((resolve, reject) => {
    const callbackName = `__lifecircleBMapReady_${Date.now()}`;
    const script = document.createElement('script');
    const cleanup = () => {
      try { delete window[callbackName]; } catch (_) { window[callbackName] = undefined; }
    };
    window[callbackName] = () => {
      if (window.BMapGL) {
        cleanup();
        resolve(window.BMapGL);
      } else {
        cleanup();
        baiduScriptPromise = null;
        reject(new Error('百度 JSAPI GL 回调完成但 BMapGL 未就绪'));
      }
    };
    script.src = `https://api.map.baidu.com/api?v=1.0&type=webgl&ak=${encodeURIComponent(appConfig.browser_map_ak)}&callback=${callbackName}`;
    script.async = true;
    script.onerror = () => {
      cleanup();
      baiduScriptPromise = null;
      reject(new Error('百度 JSAPI GL 脚本加载失败'));
    };
    document.head.appendChild(script);
  });
  return baiduScriptPromise;
}

async function renderBaidu3D(r) {
  updateBaiduPlaceholder();
  if (!appConfig.browser_map_ready) return;
  let BMapGL;
  try {
    BMapGL = await loadBaiduMapApi();
  } catch (error) {
    showBaiduError(error?.message || '百度 JSAPI 初始化失败');
    throw error;
  }
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  if (BMapGL.apiVersion !== undefined) BMapGL.apiVersion = 'gl';
  const container = $('baidu3dMap');
  const signature = [
    r.center_bd09.lng.toFixed(6), r.center_bd09.lat.toFixed(6), r.area_m2,
    (r.pois || []).length, (r.blind_spots || []).length
  ].join('|');
  if (baiduMap && baiduRenderSignature === signature) {
    try { baiduMap.setCenter(new BMapGL.Point(r.center_bd09.lng, r.center_bd09.lat)); } catch (_) {}
    return;
  }
  stopOrbit();
  if (baiduMap) {
    try { baiduMap.destroy(); } catch (_) {}
    baiduMap = null;
  }
  container.innerHTML = '';
  try {
    baiduMap = new BMapGL.Map('baidu3dMap', {
      enableRotate: true, enableTilt: true, enableIconClick: true, enableAutoResize: true
    });
  } catch (error) {
    showBaiduError(error?.message || '地图 WebGL SDK 初始化失败');
    throw error;
  }
  baiduRenderSignature = signature;
  const center = new BMapGL.Point(r.center_bd09.lng, r.center_bd09.lat);
  const maxBoundaryRadius = Math.max(0, ...(r.isochrone || []).map((p) => Number(p.radius_m) || 0));
  const communityZoom = maxBoundaryRadius > 1400 ? 17 : (maxBoundaryRadius > 900 ? 17.5 : 18);
  baiduMap.centerAndZoom(center, communityZoom);
  baiduMap.enableScrollWheelZoom(true);
  try { baiduMap.enableContinuousZoom(); } catch (_) {}
  try {
    if (appConfig.browser_map_style_id) {
      if (baiduMap.setMapStyle) baiduMap.setMapStyle({ styleId: appConfig.browser_map_style_id });
      else if (baiduMap.setMapStyleV2) baiduMap.setMapStyleV2({ styleId: appConfig.browser_map_style_id });
    }
  } catch (e) { console.warn('Map style failed:', e); }
  const applyCamera = () => {
    if (!baiduMap) return;
    const maxTilt = Number(baiduMap.getCurrentMaxTilt?.());
    baiduMap.setTilt(Number.isFinite(maxTilt) ? Math.min(72, Math.max(60, maxTilt)) : 72);
    baiduMap.setHeading(32);
  };
  try { applyCamera(); } catch (_) {}
  try { baiduMap.addEventListener('tilesloaded', applyCamera); } catch (_) {}
  setTimeout(() => { try { applyCamera(); } catch (_) {} }, 800);
  try { baiduMap.addControl(new BMapGL.ScaleControl()); baiduMap.addControl(new BMapGL.ZoomControl()); } catch (_) {}

  const polyPts = (r.isochrone || []).map((p) => new BMapGL.Point(p.lng, p.lat));
  if (polyPts.length >= 3) {
    try {
      baiduMap.addOverlay(new BMapGL.Polygon(polyPts, {
        strokeColor: '#1d4ed8', strokeWeight: 4, strokeOpacity: 0.95,
        fillColor: '#3b82f6', fillOpacity: 0.20
      }));
    } catch (_) {}
  }

  // 距离感参考：500m / 1km 真实地图圆环，不参与等时圈计算。
  for (const [radius, color, dash] of [[500, '#60a5fa', ''], [1000, '#f59e0b', '']]) {
    try {
      baiduMap.addOverlay(new BMapGL.Circle(center, radius, {
        strokeColor: color, strokeWeight: 2, strokeOpacity: 0.70,
        fillColor: color, fillOpacity: 0.018,
        strokeStyle: dash || 'solid'
      }));
    } catch (_) {}
  }

  // 路网测时探针只抽样显示，避免真实地图被点位挤满。
  const samples = (r.route_samples || []).filter((_, i) => i % 4 === 0).slice(0, 20);
  samples.forEach((sample) => {
    const pt = new BMapGL.Point(sample.lng, sample.lat);
    const ratio = (sample.duration_s || r.threshold_minutes * 120) / (r.threshold_minutes * 60);
    const color = ratio <= 0.6 ? '#10b981' : ratio <= 1 ? '#f59e0b' : '#ef4444';
    try {
      if (BMapGL.Marker3D) {
        baiduMap.addOverlay(new BMapGL.Marker3D(pt, 10, { size: 8, fillColor: color, fillOpacity: 0.70 }));
      }
    } catch (_) {}
  });

  const poiList = (r.pois || []).slice(0, 40);
  poiList.forEach((poi, i) => {
    const pt = new BMapGL.Point(poi.lng, poi.lat);
    const color = CATEGORY_COLORS[poi.category] || CATEGORY_COLORS.default;
    let added3d = false;
    try {
      if (BMapGL.Marker3D) {
        const marker3d = new BMapGL.Marker3D(pt, 24 + (i % 5) * 12, {
          size: 18 + (i % 3) * 4,
          shape: typeof BMAP_SHAPE_CIRCLE !== 'undefined' ? BMAP_SHAPE_CIRCLE : 1,
          fillColor: color,
          fillOpacity: 0.88
        });
        baiduMap.addOverlay(marker3d);
        added3d = true;
      }
    } catch (_) {}
    if (!added3d) {
      try { baiduMap.addOverlay(new BMapGL.Marker(pt)); } catch (_) {}
    }
    if (i < 8 && BMapGL.Label) {
      try {
        const label = new BMapGL.Label(`${poi.category_label} · ${poi.name}`, { position: pt, offset: new BMapGL.Size(10, -20) });
        label.setStyle({ color: '#15304f', backgroundColor: 'rgba(255,255,255,.88)', border: '1px solid #d8e4f3', borderRadius: '8px', padding: '4px 7px', fontSize: '11px', boxShadow: '0 5px 14px rgba(17,38,70,.12)' });
        baiduMap.addOverlay(label);
      } catch (_) {}
    }
  });

  (r.blind_spots || []).slice(0, 15).forEach((spot) => {
    const pt = new BMapGL.Point(spot.lng, spot.lat);
    try {
      baiduMap.addOverlay(new BMapGL.Circle(pt, 42 + spot.severity * 22, {
        strokeColor: '#ef4444', strokeWeight: 2, strokeOpacity: 0.85,
        fillColor: '#ef4444', fillOpacity: 0.20
      }));
    } catch (_) {}
  });

  try {
    if (BMapGL.Marker3D) {
      baiduMap.addOverlay(new BMapGL.Marker3D(center, 96, {
        size: 30, shape: typeof BMAP_SHAPE_RECT !== 'undefined' ? BMAP_SHAPE_RECT : 2,
        fillColor: '#111827', fillOpacity: 0.92
      }));
    } else {
      baiduMap.addOverlay(new BMapGL.Marker(center));
    }
  } catch (_) {}
  $('baiduMapPlaceholder')?.classList.add('hidden');
  $('baiduControls')?.classList.remove('hidden');
}

function resetBaiduView() {
  if (!baiduMap || !currentResult) return;
  try {
    const c = new BMapGL.Point(currentResult.center_bd09.lng, currentResult.center_bd09.lat);
    const maxBoundaryRadius = Math.max(0, ...(currentResult.isochrone || []).map((p) => Number(p.radius_m) || 0));
    const zoom = maxBoundaryRadius > 1400 ? 17 : (maxBoundaryRadius > 900 ? 17.5 : 18);
    baiduMap.centerAndZoom(c, zoom);
    baiduMap.setTilt(72); baiduMap.setHeading(32);
  } catch (_) {}
}

function stopOrbit() {
  if (!orbitTimer) return;
  clearInterval(orbitTimer);
  orbitTimer = null;
  const btn = $('mapOrbitBtn');
  if (btn) {
    btn.classList.remove('active');
    btn.textContent = '自动环绕';
  }
}

function toggleOrbit() {
  const btn = $('mapOrbitBtn');
  if (!baiduMap) { toast('请先完成分析并加载真实城市地图'); return; }
  if (orbitTimer) {
    stopOrbit(); return;
  }
  let heading = 28;
  orbitTimer = setInterval(() => {
    heading = (heading + 2) % 360;
    try { baiduMap.setHeading(heading); } catch (_) {}
  }, 240);
  btn.classList.add('active'); btn.textContent = '停止环绕';
}

function toggleTraffic() {
  if (!baiduMap) { toast('请先加载真实城市地图'); return; }
  trafficEnabled = !trafficEnabled;
  try { trafficEnabled ? baiduMap.setTrafficOn() : baiduMap.setTrafficOff(); } catch (_) {}
  $('mapTrafficBtn').classList.toggle('active', trafficEnabled);
}

function toggleSatellite() {
  if (!baiduMap) { toast('请先加载真实城市地图'); return; }
  satelliteEnabled = !satelliteEnabled;
  try {
    if (typeof BMAP_SATELLITE_MAP !== 'undefined' && typeof BMAP_NORMAL_MAP !== 'undefined') {
      baiduMap.setMapType(satelliteEnabled ? BMAP_SATELLITE_MAP : BMAP_NORMAL_MAP);
    }
  } catch (_) {}
  $('mapSatelliteBtn').classList.toggle('active', satelliteEnabled);
  $('mapSatelliteBtn').textContent = satelliteEnabled ? '标准底图' : '卫星底图';
}

function setVizView(view) {
  if (view !== 'baidu') stopOrbit();
  currentViz = view;
  const twin = $('twinWrap');
  const baidu = $('baiduWrap');
  const map = $('mapWrap');
  twin.classList.toggle('hidden', view !== 'twin');
  baidu.classList.toggle('hidden', view !== 'baidu');
  map.classList.toggle('hidden', view !== 'map');
  document.querySelectorAll('.viz-tab').forEach((btn) => btn.classList.toggle('active', btn.dataset.viz === view));
  const cap = $('vizCaption');
  if (view === 'twin') {
    cap.textContent = '数字孪生 3D：基于分析结果生成沉浸式城市表达层，楼体/树木不是实际 BIM 或地籍数据。';
    if (currentResult) requestAnimationFrame(() => renderTwin(currentResult));
  } else if (view === 'baidu') {
    cap.textContent = appConfig.browser_map_ready
      ? '真实城市 3D：百度 JSAPI GL WebGL 真实底图 + 15min 等时圈 + 500m/1km 距离参考 + POI/盲区覆盖物。高缩放与倾斜视角用于体现真实城市距离感。'
      : '真实城市 3D 需要独立 BAIDU_MAP_BROWSER_AK；可选 BAIDU_MAP_STYLE_ID 进一步美化底图。服务端 AK 不会暴露给前端。';
    if (currentResult && appConfig.browser_map_ready) {
      renderBaidu3D(currentResult).catch((e) => toast('3D 地图加载失败：' + e.message));
    }
  } else {
    cap.textContent = '分析热力图：强调等时圈边界、POI 分布、盲区位置与路网耗时采样。';
  }
}

function togglePresentationMode() {
  presentationMode = !presentationMode;
  document.body.classList.toggle('presentation-mode', presentationMode);
  const btn = $('presentationBtn');
  if (btn) btn.textContent = presentationMode ? '退出沉浸演示' : '进入沉浸演示';
  setTimeout(() => {
    if (currentResult && currentViz === 'twin') safeRenderTwin(currentResult);
    if (baiduMap) { try { baiduMap.checkResize?.(); } catch (_) {} }
  }, 120);
}

function bindVizTabs() {
  document.querySelectorAll('.viz-tab').forEach((btn) => btn.addEventListener('click', () => setVizView(btn.dataset.viz)));
}

window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && presentationMode) togglePresentationMode(); });

document.addEventListener('visibilitychange', () => {
  if (document.hidden) stopOrbit();
});

window.addEventListener('resize', () => {
  if (currentResult && currentViz === 'twin') renderTwin(currentResult);
  if (baiduMap && currentViz === 'baidu') {
    try { baiduMap.setCenter(baiduMap.getCenter()); } catch (_) {}
  }
});

document.querySelectorAll('input[name="mode"]').forEach((x) => x.addEventListener('change', updateModeNotice));
$('analyzeBtn').onclick = analyze;
$('newBtn').onclick = resetForm;
$('demoPreset').onclick = resetForm;
$('geocodeBtn').onclick = geocodeAddress;
$('mapOrbitBtn').onclick = toggleOrbit;
$('mapTrafficBtn').onclick = toggleTraffic;
$('mapSatelliteBtn').onclick = toggleSatellite;
$('mapResetBtn').onclick = resetBaiduView;
$('presentationBtn').onclick = togglePresentationMode;
$('aiBriefBtn').onclick = generateAiBrief;
bindVizTabs();
loadConfig().catch(console.error);
loadHistory().catch(console.error);
updateModeNotice();
setVizView('twin');
