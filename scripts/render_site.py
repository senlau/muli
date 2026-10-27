"""Render the static 目力 index. Tabs and entries use CSS :target; app.js only filters, focuses, and opens the lightbox."""

from __future__ import annotations

import html
from datetime import datetime

from mdutil import inline, plain

STREAMS = [
    {
        "key": "photographer",
        "folder": "photographer",
        "hash": "photographer",
        "label": "每日摄影师",
        "short": "摄影师",
        "kicker": "按作者",
        "index": "01",
        "blurb": "同一位作者的语言、系列，和可以跟去的入口。学的是审美，聚类单位是人。",
    },
    {
        "key": "aesthetic",
        "folder": "aesthetic",
        "hash": "aesthetic",
        "label": "每日审美一课",
        "short": "审美",
        "kicker": "按风格",
        "index": "02",
        "blurb": "风格和类型的判断词。看什么是好，不写成站位清单，也不把 28mm 技法收进来。",
    },
    {
        "key": "28mm",
        "folder": "28mm",
        "hash": "28mm",
        "label": "28mm 专题",
        "short": "28mm",
        "kicker": "按焦段",
        "index": "03",
        "blurb": "固定焦段的出门练习：走近、机位、换位。这是手法课，单独成卷。",
    },
]

SKIP_TAGS = {"审美一课", "28mm", "FG", "MG", "BG"}
SITE = "https://senlau.github.io/muli/"
REPO = "https://github.com/senlau/muli"


def esc(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def entry_dom_id(entry: dict) -> str:
    return f'{entry["stream"]}-{entry["date"]}'


def tag_class(tag: str) -> str:
    if tag == "大师":
        return "tag tag-blue"
    if tag in ("新锐", "非惊喜"):
        return "tag tag-teal"
    if tag == "当代" or (tag.startswith("第") and tag.endswith("课")):
        return "tag tag-purple"
    if tag == "审美培养":
        return "tag tag-blue"
    return "tag"


def card_tags(entry: dict) -> list[str]:
    out: list[str] = []
    category = (entry.get("category") or "").strip()
    if category:
        out.append(category)
    for tag in entry.get("tags") or []:
        if tag in out or tag in SKIP_TAGS:
            continue
        out.append(tag)
        break
    return out[:2]


def hook_text(entry: dict) -> str:
    subtitle = plain(entry.get("subtitle") or "")
    summary = plain(entry.get("summary") or "")
    if entry["stream"] == "photographer" and len(subtitle) >= 24:
        return subtitle
    return summary or subtitle


def sorted_entries(entries: list[dict], stream: str) -> list[dict]:
    return sorted(
        [entry for entry in entries if entry["stream"] == stream],
        key=lambda entry: entry["date"],
        reverse=True,
    )


def img_tag(image: dict, lazy: bool = True, decorative: bool = False) -> str:
    alt = "" if decorative else (image.get("alt") or plain(image.get("caption") or ""))
    loading = "lazy" if lazy else "eager"
    extra = ""
    if not lazy:
        extra += ' fetchpriority="high"'
    width = image.get("w")
    height = image.get("h")
    size = ""
    if width and height:
        size = f' width="{int(width)}" height="{int(height)}"'
    return (
        f'<img src="{esc(image["src"])}" alt="{esc(alt)}"'
        f'{size} loading="{loading}" decoding="async"{extra}>'
    )


def mosaic(images: list[dict]) -> str:
    shown = images[:5]
    if not shown:
        return '<div class="mosaic n-1" aria-hidden="true"><span class="frame"></span></div>'
    count = len(shown)
    frames = "".join(
        f'<span class="frame">{img_tag(image, decorative=True)}</span>' for image in shown
    )
    return f'<div class="mosaic n-{count}" aria-hidden="true">{frames}</div>'


def tags_html(tags: list[str]) -> str:
    return "".join(f'<span class="{tag_class(tag)}">{esc(tag)}</span>' for tag in tags)


def render_card(entry: dict) -> str:
    dom_id = entry_dom_id(entry)
    label = f'{entry["date"]} {plain(entry["title"])}'
    return f"""
<a class="card" href="#{esc(dom_id)}" data-cat="{esc(entry.get("category") or "")}" aria-label="{esc(label)}">
  <div class="card-top">
    <time class="date" datetime="{esc(entry["date"])}">{esc(entry["date"])}</time>
    <span class="tags">{tags_html(card_tags(entry))}</span>
  </div>
  <h3>{esc(entry["title"])}</h3>
  <p class="hook">{esc(hook_text(entry))}</p>
  {mosaic(entry.get("images") or [])}
  <span class="card-more">看这一则</span>
</a>""".strip()


def render_filters(entries: list[dict]) -> str:
    seen: list[str] = []
    for entry in entries:
        category = (entry.get("category") or "").strip()
        if category and category not in seen:
            seen.append(category)
    if len(seen) < 2:
        return ""
    buttons = ['<button type="button" data-filter="*" aria-pressed="true">全部</button>']
    buttons.extend(
        f'<button type="button" data-filter="{esc(category)}" aria-pressed="false">{esc(category)}</button>'
        for category in seen
    )
    return f'<div class="filters" role="group" aria-label="按标签筛选">{"".join(buttons)}</div>'


def render_panel(stream: dict, entries: list[dict]) -> str:
    group = sorted_entries(entries, stream["hash"])
    if group:
        latest = group[0]
        latest_html = f'<div class="latest"><b>{esc(latest["date"])}</b> · {esc(plain(latest["title"]))}</div>'
    else:
        latest_html = '<div class="latest">还没有条目</div>'
    return f"""
<a class="panel" data-stream="{esc(stream["hash"])}" href="#{esc(stream["hash"])}">
  <span class="kicker">{esc(stream["index"])} · {esc(stream["kicker"])}</span>
  <h3>{esc(stream["label"])}</h3>
  <p>{esc(stream["blurb"])}</p>
  {latest_html}
  <div class="count">{len(group)} 则</div>
</a>""".strip()


def plate(image: dict, index: int, total: int) -> str:
    caption = image.get("caption") or ""
    cap_html = inline(caption) if caption else "图"
    alt = image.get("alt") or plain(caption)
    style = ""
    if image.get("w") and image.get("h"):
        style = f' style="aspect-ratio:{int(image["w"])}/{int(image["h"])}"'
    return f"""
<figure class="plate">
  <div class="plate-frame"{style}>
    <button type="button" class="plate-open" data-src="{esc(image["src"])}" data-alt="{esc(alt)}" data-cap="{esc(plain(caption))}" aria-label="放大第 {index} 张，共 {total} 张">
      {img_tag(image)}
    </button>
  </div>
  <figcaption><span class="idx">{index:02d} / {total:02d}</span><span>{cap_html}</span></figcaption>
</figure>""".strip()


def render_entry(entry: dict, newer: dict | None, older: dict | None) -> str:
    dom_id = entry_dom_id(entry)
    images = entry.get("images") or []
    if images:
        plates = f'<div class="plates">{"".join(plate(image, i, len(images)) for i, image in enumerate(images, 1))}</div>'
    else:
        plates = '<p class="no-plates">这一则还没有配图。正文仍可阅读。</p>'
    links = entry.get("links") or []
    if links:
        link_html = "".join(
            f'<a href="{esc(link["url"])}" target="_blank" rel="noopener noreferrer">{esc(link["label"])}<span class="sr">（新窗口）</span></a>'
            for link in links
        )
        side = f'<div class="outlinks">{link_html}</div>'
    else:
        side = '<p class="quiet">这一则没有外链。</p>'
    pager = []
    if newer:
        pager.append(f'<a href="#{esc(entry_dom_id(newer))}">较新 · {esc(newer["date"][5:])}</a>')
    if older:
        pager.append(f'<a href="#{esc(entry_dom_id(older))}">较旧 · {esc(older["date"][5:])}</a>')
    pager_html = f'<nav class="pager" aria-label="同栏前后">{"".join(pager)}</nav>' if pager else ""
    stream_label = next(item["label"] for item in STREAMS if item["hash"] == entry["stream"])
    return f"""
<article class="entry shell" id="{esc(dom_id)}" data-stream="{esc(entry["stream"])}">
  <div class="entry-bar">
    <a class="back" href="#{esc(entry["stream"])}">返回{esc(stream_label)}</a>
    {pager_html}
  </div>
  <header class="entry-head">
    <div class="card-top">
      <time class="date" datetime="{esc(entry["date"])}">{esc(entry["date"])}</time>
      <span class="tags">{tags_html(card_tags(entry))}</span>
    </div>
    <h1 tabindex="-1" data-entry-title>{esc(entry["title"])}</h1>
  </header>
  {plates}
  <div class="entry-body">
    <div class="prose">{entry.get("html") or ""}</div>
    <aside class="side">
      <h2>入口</h2>
      {side}
    </aside>
  </div>
</article>""".strip()


def render_index(entries: list[dict], generated_at: str) -> str:
    by_stream = {stream["hash"]: sorted_entries(entries, stream["hash"]) for stream in STREAMS}
    counts = {key: len(group) for key, group in by_stream.items()}
    image_count = sum(len(entry.get("images") or []) for entry in entries)
    latest_date = max(entry["date"] for entry in entries)
    cover_entry = by_stream["photographer"][0] if by_stream["photographer"] else None
    cover = (cover_entry.get("images") or [None])[0] if cover_entry else None
    cover_html = ""
    if cover_entry and cover:
        cover_html = f"""
<a class="hero-visual" href="#{esc(entry_dom_id(cover_entry))}">
  {img_tag(cover, lazy=False)}
  <span class="hero-cap">{esc(cover_entry["date"])} · {esc(plain(cover_entry["title"]))}</span>
</a>""".strip()

    panels = "".join(render_panel(stream, entries) for stream in STREAMS)
    panels_html = f'<div class="panels">{panels}</div>'

    tab_links = []
    panels_body = []
    for stream in STREAMS:
        group = by_stream[stream["hash"]]
        selected = "true" if stream["hash"] == "photographer" else "false"
        tab_links.append(
            f'<a role="tab" href="#{esc(stream["hash"])}" id="tab-{esc(stream["hash"])}" aria-controls="{esc(stream["hash"])}" aria-selected="{selected}">{esc(stream["label"])}<span class="n">{len(group)}</span></a>'
        )
        cards = "".join(render_card(entry) for entry in group)
        panels_body.append(
            f"""
<div class="stream-panel" id="{esc(stream["hash"])}" role="tabpanel" aria-labelledby="tab-{esc(stream["hash"])}">
  {render_filters(group)}
  <div class="grid">{cards}</div>
  <p class="empty" hidden>这一筛下还没有条目。</p>
</div>""".strip()
        )

    articles = []
    for stream in STREAMS:
        group = by_stream[stream["hash"]]
        for index, entry in enumerate(group):
            newer = group[index - 1] if index > 0 else None
            older = group[index + 1] if index + 1 < len(group) else None
            articles.append(render_entry(entry, newer, older))

    stamp = generated_at[:10] if generated_at else datetime.now().strftime("%Y-%m-%d")
    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <meta name="theme-color" content="#f3f6fb">
  <meta name="description" content="目力摄影策展：每日摄影师、每日审美一课、28mm 专题。按作者、按风格、按焦段分开看。">
  <title>目力 · 三条线分开看</title>
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="css/site.css">
</head>
<body data-stream="photographer">
  <a class="skip" href="#archive">跳到归档</a>
  <nav class="deck" aria-label="主导航">
    <div class="deck-inner shell">
      <a class="brand" href="#top">
        <span class="mark" aria-hidden="true"></span>
        <strong>目力</strong>
        <em>摄影策展</em>
      </a>
      <div class="deck-links">
        <a data-nav href="#photographer"><span class="full">每日摄影师</span><span class="short">摄影师</span></a>
        <a data-nav href="#aesthetic"><span class="full">每日审美一课</span><span class="short">审美</span></a>
        <a data-nav href="#28mm"><span class="full">28mm 专题</span><span class="short">28mm</span></a>
        <a data-nav href="#about">关于</a>
      </div>
    </div>
  </nav>

  <header class="hero shell" id="top">
    <div class="hero-card">
      <div class="hero-grid">
        {cover_html}
        <div class="hero-copy">
          <p class="eyebrow">目力 · 更新至 {esc(latest_date)}</p>
          <h1>三条线，<em>分开看</em></h1>
          <p class="hero-sub">每日摄影师按作者学审美，每日审美一课按风格学审美，28mm 专题按焦段练手法。前两条不收构图技法。</p>
          <p class="hero-note"><strong>一句话：</strong>先把同一类东西并排放好，再点进一则里核对图片和入口。</p>
          <div class="metric-strip" aria-label="收录规模">
            <div class="metric"><strong>{counts["photographer"]}</strong><span>位作者</span></div>
            <div class="metric"><strong>{counts["aesthetic"]}</strong><span>课审美</span></div>
            <div class="metric"><strong>{counts["28mm"]}</strong><span>课 28mm</span></div>
          </div>
        </div>
      </div>
    </div>
  </header>

  <section class="section" id="lines">
    <div class="shell">
      <div class="section-head">
        <span class="section-tag">分卷</span>
        <h2 class="section-title">同一套版式，<em>三种聚类</em></h2>
        <p class="section-sub">作者、风格、焦段各看各的。点一块就进到对应的归档。</p>
      </div>
      {panels_html}
      <div class="callout">
        <span class="label">分工</span>
        <p>摄影师和审美一课都是<strong>审美学习</strong>：一个按作者聚，一个按风格聚。28mm 是<strong>焦段实践</strong>，不放进审美栏。</p>
      </div>
    </div>
  </section>

  <section class="archive-band" id="archive">
    <div class="shell">
      <div class="section-head">
        <span class="section-tag">归档</span>
        <h2 class="section-title">先选一条线，<em>再进入一则</em></h2>
        <p class="section-sub">按日期倒序。卡片上的缩略图来自 CDN，点进去是原文、大图和外链。共 {image_count} 张图。</p>
      </div>
      <div class="tabs" role="tablist" aria-label="三条内容流">{"".join(tab_links)}</div>
      {"".join(panels_body)}
    </div>
  </section>

  <section class="section about" id="about">
    <div class="shell">
      <div class="section-head">
        <span class="section-tag">关于</span>
        <h2 class="section-title">这本册子<em>不混线</em></h2>
        <p class="section-sub">2026-10-27 起按这个分工归档。锚点用来对照，不围着他们打转。</p>
      </div>
      <div class="about-grid">
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>线</th><th>聚类</th><th>看什么</th></tr>
            </thead>
            <tbody>
              <tr><td><strong>每日摄影师</strong></td><td>作者</td><td>语言、系列、可以跟去的入口</td></tr>
              <tr><td><strong>每日审美一课</strong></td><td>风格 / 类型</td><td>判断词，以及什么是好</td></tr>
              <tr><td><strong>28mm 专题</strong></td><td>焦段</td><td>走近、机位、换位，出门能练</td></tr>
            </tbody>
          </table>
        </div>
        <aside class="anchor-card">
          <h3>对照锚点</h3>
          <ul>
            <li><strong>Seiki Hayashi</strong>　地方黑白、电影感静滞、日常非事件。</li>
            <li><strong>Alex Webb</strong>　彩色叠层、巧合、前中后景。锚点不是边界。</li>
          </ul>
        </aside>
      </div>
      <div class="final-hero">
        <p>图都在 CDN 上，仓库里不存原片。掌印确认当日三条推送之后跑一次同步，页面随 main 更新。审美课只谈风格和类型；28mm 的站位、换位留在焦段专题里。同步约定见 <a href="{REPO}/blob/main/SYNC.md">SYNC.md</a>。</p>
      </div>
    </div>
  </section>

  <footer class="site-footer">
    <div class="shell">
      <span>目力 · 摄影策展 · 生成于 {esc(stamp)}</span>
      <span><a href="{SITE}">{SITE}</a> · <a href="{REPO}">GitHub</a></span>
    </div>
  </footer>

  {"".join(articles)}

  <dialog class="lightbox" id="lightbox" aria-label="放大图片">
    <div class="lb-bar">
      <div>
        <button type="button" id="lb-prev">上一张</button>
        <button type="button" id="lb-next">下一张</button>
      </div>
      <button type="button" id="lb-close">关闭</button>
    </div>
    <figure class="lb-figure">
      <img id="lb-img" alt="">
      <figcaption class="lb-cap" id="lb-cap"></figcaption>
    </figure>
    <p class="sr" id="lb-count" aria-live="polite"></p>
  </dialog>
  <script src="js/app.js"></script>
</body>
</html>
"""
