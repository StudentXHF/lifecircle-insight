from __future__ import annotations

import html
from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'tmp' / 'submission_pdf_html'

DOCS = [
    (
        ROOT / 'submission' / '01_圈析智图_作品介绍文档_正式稿.md',
        '01_作品介绍.html',
        '作品介绍文档',
        '从几何圆到真实步行时间，让社区公共服务体检可计算、可解释、可交付',
        'SUBMISSION BRIEF',
    ),
    (
        ROOT / 'submission' / '02_圈析智图_技术设计报告_正式稿.md',
        '02_技术设计报告.html',
        '技术设计报告',
        '百度地图开放能力 · 路网等时圈 · 设施覆盖 · 服务盲区 · 工程可靠性',
        'TECHNICAL DESIGN',
    ),
    (
        ROOT / 'submission' / '04_答辩核心卖点与Q&A.md',
        '04_答辩Q&A.html',
        '答辩核心卖点与 Q&A',
        '30 秒开场、评分维度答法与 22 个高概率问题',
        'DEFENSE PLAYBOOK',
    ),
]


CSS = r'''
@page { size: A4; margin: 15mm 15mm 17mm; }
* { box-sizing: border-box; }
html { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
body {
  margin: 0; color: #122138; background: #fff;
  font-family: "Microsoft YaHei", "Noto Sans CJK SC", "PingFang SC", sans-serif;
  font-size: 10.2pt; line-height: 1.68;
}
.cover {
  height: 254mm; margin: -15mm -15mm 0; padding: 22mm 20mm 17mm;
  page-break-after: always; overflow: hidden; position: relative;
  color: #f7fbff; background:
    radial-gradient(circle at 82% 19%, rgba(54,214,196,.24), transparent 25%),
    radial-gradient(circle at 18% 80%, rgba(66,132,255,.23), transparent 31%),
    linear-gradient(145deg, #071629 0%, #0b2744 48%, #0b4055 100%);
}
.cover:before, .cover:after { content: ""; position: absolute; border: 1px solid rgba(99,232,208,.28); border-radius: 50%; }
.cover:before { width: 150mm; height: 150mm; right: -55mm; top: 34mm; }
.cover:after { width: 88mm; height: 88mm; right: -12mm; top: 65mm; }
.eyebrow { color: #6ee7d8; font-weight: 800; font-size: 9pt; letter-spacing: 2.3px; }
.brand { margin-top: 5mm; font-weight: 850; font-size: 18pt; letter-spacing: 1px; }
.cover h1 { margin: 32mm 0 5mm; color: #fff; font-size: 31pt; line-height: 1.18; letter-spacing: -1px; max-width: 155mm; }
.subtitle { margin: 0; max-width: 145mm; color: #c8d9e8; font-size: 13pt; line-height: 1.7; }
.route-art { margin: 21mm 0 12mm; width: 100%; height: 55mm; }
.meta { display: flex; flex-wrap: wrap; gap: 3mm; margin-top: 8mm; }
.pill { border: 1px solid rgba(164,227,220,.35); background: rgba(6,25,44,.42); border-radius: 99px; padding: 2.2mm 4mm; color: #d9f6f1; font-size: 8.5pt; }
.honesty { position: absolute; left: 20mm; right: 20mm; bottom: 18mm;
  padding: 4mm 5mm; border-left: 2mm solid #5eead4;
  background: rgba(0,0,0,.18); color: #cfe3ea; font-size: 8.8pt; }
.doc { max-width: 100%; }
h1 { color: #0a3552; font-size: 23pt; line-height: 1.25; margin: 0 0 7mm; }
h2 { color: #0a5263; font-size: 16pt; line-height: 1.35; margin: 8mm 0 3.2mm; padding-bottom: 1.8mm; border-bottom: 1px solid #cfe2e5; break-after: avoid; }
h3 { color: #163b55; font-size: 12.2pt; line-height: 1.4; margin: 5mm 0 1.8mm; break-after: avoid; }
h4 { color: #1e4e68; margin: 4mm 0 1.5mm; break-after: avoid; }
p { margin: 0 0 2.8mm; orphans: 3; widows: 3; }
ul, ol { margin: 1.2mm 0 3.2mm; padding-left: 6mm; }
li { margin: .8mm 0; }
strong { color: #0a4257; }
blockquote { margin: 4mm 0; padding: 3.2mm 4.5mm; border-left: 1.4mm solid #15a897; background: #edf8f6; color: #183d4a; break-inside: avoid; }
blockquote p:last-child { margin-bottom: 0; }
code { font-family: Consolas, monospace; font-size: 8.8pt; background: #eff4f7; border-radius: 3px; padding: .25mm 1mm; }
pre { margin: 3mm 0; padding: 3.5mm; white-space: pre-wrap; word-break: break-word; color: #d9f4ef; background: #0d2638; border-radius: 6px; break-inside: avoid; }
pre code { padding: 0; color: inherit; background: transparent; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0 5mm; font-size: 8.7pt; break-inside: avoid; }
th { padding: 2.4mm 2mm; color: #fff; background: #0d6570; text-align: left; }
td { padding: 2.1mm 2mm; border-bottom: 1px solid #d8e6e9; vertical-align: top; }
tr:nth-child(even) td { background: #f5f9fa; }
hr { border: 0; height: 1px; margin: 7mm 0; background: #dce8ea; }
a { color: #087d83; text-decoration: none; }
.doc > p:first-of-type { font-size: 11pt; }
'''


ART = '''
<svg class="route-art" viewBox="0 0 900 280" aria-hidden="true">
  <g fill="none" stroke="#7fb0bd" stroke-opacity=".18" stroke-width="2">
    <path d="M0 40 L900 40 M0 110 L900 110 M0 180 L900 180 M0 250 L900 250"/>
    <path d="M80 0 L80 280 M260 0 L260 280 M440 0 L440 280 M620 0 L620 280 M800 0 L800 280"/>
  </g>
  <path d="M82 214 C190 196 218 77 352 111 S522 238 644 151 S765 55 852 72" fill="none" stroke="#69ead5" stroke-width="10" stroke-linecap="round"/>
  <path d="M82 214 C190 196 218 77 352 111 S522 238 644 151 S765 55 852 72" fill="none" stroke="#d8fff8" stroke-opacity=".9" stroke-width="2" stroke-dasharray="7 14"/>
  <g fill="#091a2d" stroke="#76f1dc" stroke-width="6">
    <circle cx="82" cy="214" r="12"/><circle cx="352" cy="111" r="12"/>
    <circle cx="644" cy="151" r="12"/><circle cx="852" cy="72" r="12"/>
  </g>
  <path d="M420 42 C474 21 547 38 573 88 C601 142 563 208 500 221
    C431 236 368 187 376 119 C380 84 393 57 420 42Z"
    fill="#43cdb8" fill-opacity=".13" stroke="#8df5e4" stroke-width="3" stroke-dasharray="9 8"/>
</svg>'''


def without_initial_titles(text: str) -> str:
    lines = text.splitlines()
    removed = 0
    out: list[str] = []
    for line in lines:
        if removed < 2 and line.startswith('#'):
            removed += 1
            continue
        if removed < 2 and not line.strip():
            continue
        out.append(line)
    return '\n'.join(out)


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for source, filename, title, subtitle, eyebrow in DOCS:
        raw = source.read_text(encoding='utf-8')
        body = markdown.markdown(
            without_initial_titles(raw),
            extensions=['extra', 'sane_lists'],
            output_format='html5',
        )
        base_uri = source.parent.as_uri().rstrip('/') + '/'
        page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><base href="{base_uri}">
<title>{html.escape(title)}｜圈析智图</title><style>{CSS}</style></head><body>
<section class="cover"><div class="eyebrow">{eyebrow}</div><div class="brand">圈析智图 · LifeCircle Insight</div>
<h1>{html.escape(title)}</h1><p class="subtitle">{html.escape(subtitle)}</p>{ART}
<div class="meta"><span class="pill">2026 上海开源软件应用创新大赛</span><span class="pill">开源 AI 工具赛道</span><span class="pill">v3.0.0-rc3</span><span class="pill">MIT License</span></div>
<div class="honesty">真实性声明：真实社区结论来自 2026-09-14 百度地图 API 实测，并保留 LIVE_BAIDU_MAP_API 结构化证据；离线样例仅用于容灾，不替代真实结果。</div></section>
<main class="doc">{body}</main></body></html>'''
        (OUT / filename).write_text(page, encoding='utf-8')
        print(OUT / filename)


if __name__ == '__main__':
    build()
