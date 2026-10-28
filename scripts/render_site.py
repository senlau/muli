"""Render 目力 as static pages: home, three section pages, the archive and one page per article."""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date as Date
from urllib.parse import urlparse

from mdutil import LINK, format_plain, inline, parse_blocks, plain

STREAMS = [
    {"key": "photographer", "folder": "photographer", "hash": "photographer", "label": "摄影师", "section": "learn"},
    {"key": "aesthetic", "folder": "aesthetic", "hash": "aesthetic", "label": "视觉语言", "section": "learn"},
    {"key": "28mm", "folder": "28mm", "hash": "28mm", "label": "28mm 专题", "section": "practice"},
    {"key": "meaning", "folder": "meaning", "hash": "meaning", "label": "摄影与人生", "section": "life"},
]
STREAM = {item["key"]: item for item in STREAMS}
STREAM_ORDER = {item["key"]: index for index, item in enumerate(STREAMS)}
STREAM_HREF = {
    "photographer": "learn.html#photographer",
    "aesthetic": "learn.html#aesthetic",
    "28mm": "practice.html",
    "meaning": "life.html",
}

SECTIONS = [
    {"key": "home", "href": "index.html", "label": "首页"},
    {"key": "learn", "href": "learn.html", "label": "审美学习"},
    {"key": "practice", "href": "practice.html", "label": "摄影实践"},
    {"key": "life", "href": "life.html", "label": "摄影与人生"},
    {"key": "archive", "href": "archive.html", "label": "归档"},
]

SITE = "https://senlau.github.io/muli/"
REPO = "https://github.com/senlau/muli"
CREDIT = "觉非的 Grok Bot 作品"
WEEKDAYS = "一二三四五六日"

PRACTICE_PLAN = "只带一支 28mm 出门：先走近，再降低机位，再侧移半步。每课只练一件事，按顺序读。"
LIFE_DEK = "摄影师在抑郁、焦虑和流离之中，怎样借一台相机重新出门、开口。"
ABOUT = [
    "这里按篇整理对摄影作品的看法：每篇先给一个判断，再用作品逐张说明，最后留一个出门就能做的练习。摄影师与视觉语言大致每天一篇，28mm 专题按课推进，摄影与人生不定期更新。",
    "文中的「风格对照」常拿两位摄影师当坐标：Seiki Hayashi 的静滞与负空间，Alex Webb 的彩色叠层。坐标只用来对照，不是边界。",
    "图片版权归原作者。每篇文末列出作品出处与延伸阅读。",
]

UNNUMBERED = {"核心判断", "资料来源"}
BOXED = {"今日练习": "practice", "可以借用的做法": "borrow"}
SORT_NAME = {"Miguel Rio Branco": "Rio Branco", "Anuar Patjane Floriuk": "Patjane"}

# Fallback clean-up for entries synced from the vault that nobody has edited yet.
RENAME = [
    (re.compile(r"^(跟锚点|对照锚点)"), "风格对照"),
    (re.compile(r"^同类场面常见废法"), "常见构图问题"),
    (re.compile(r"^常见(翻车|误读)"), "常见问题"),
    (re.compile(r"^(可练一句|一条可练|可练技法)"), "今日练习"),
    (re.compile(r"^这个风格在看什么"), "在看什么"),
    (re.compile(r"^看片时注意"), "看片时注意"),
    (re.compile(r"^今日判断词"), "判断词"),
    (re.compile(r"^可辨认的语言特征"), "语言特征"),
    (re.compile(r"^(入门系列|书)"), "书与系列"),
    (re.compile(r"^(逐图短评|示例)"), "作品观察"),
    (re.compile(r"^为何在\s*28mm"), "为什么是 28mm"),
    (re.compile(r"^怎么站"), "怎么站"),
    (re.compile(r"^技巧"), "为什么成立"),
    (re.compile(r"^可借力点"), "可以借用的做法"),
    (re.compile(r"^出处"), "资料来源"),
]
DROP_SECTION = re.compile(r"^(类别|入口|查看更多|可合并进|课后补记)")
DROP_LINE = re.compile(r"(喜欢\s*/\s*一般\s*/\s*不感兴趣|回一句就行|有用\s*/\s*一般\s*/\s*想换方向|^\s*\*\*反馈\*\*)")
INTERNAL = re.compile(
    r"(昨天|昨日|昨审美|（昨）|今早|今天上午|今天这位|已推|复推|复读|本周|周主题|选题硬规则|基于你|你点名|你已|你问过|你认|你喜欢|反馈|"
    r"收到推送|允许拍完不发|允许不发|高审计|"
    r"187\s*cm|杭州|拉丁文名即可|不必硬造|未凑数|SOURCES|Wayback|现时常 ?500|官网现 ?404|免得)"
)
# Raw sections are put back into the reading order: judgement, works, analysis, practice, references.
ORDER = {
    "核心判断": 0, "在看什么": 1, "作品观察": 2,
    "语言特征": 3, "为什么成立": 3, "看片时注意": 3, "判断词": 3, "为什么是 28mm": 3, "怎么站": 3,
    "风格对照": 4, "常见问题": 5, "常见构图问题": 5, "今日练习": 6, "可以借用的做法": 6,
    "书与系列": 7, "资料来源": 8,
}
NUMBERED_WORK = re.compile(r"^\*\*(\d+)\.\s*(.+?)\*\*\s*(.*)$", re.S)


def esc(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def wrap(tag: str, cls: str, content: str) -> str:
    return f'<{tag} class="{cls}">{content}</{tag}>' if content else ""


def rich(text: str) -> str:
    """Inline emphasis without links, for text that already sits inside a link."""
    return format_plain(LINK.sub(lambda match: match.group(1), text or ""))


def fmt_date(iso: str) -> str:
    return (iso or "").replace("-", ".")


def weekday(iso: str) -> str:
    try:
        return "周" + WEEKDAYS[Date.fromisoformat(iso).weekday()]
    except ValueError:
        return ""


def entry_id(entry: dict) -> str:
    if entry["stream"] == "meaning" and entry.get("slug"):
        return f'{entry["stream"]}-{entry["date"]}-{entry["slug"]}'
    return f'{entry["stream"]}-{entry["date"]}'


entry_dom_id = entry_id


def entry_path(entry: dict) -> str:
    folder = STREAM[entry["stream"]]["folder"]
    if entry["stream"] == "meaning" and entry.get("slug"):
        return f'{folder}/{entry["date"]}-{entry["slug"]}.html'
    return f'{folder}/{entry["date"]}.html'


def ratio(image: dict) -> float:
    width, height = image.get("w"), image.get("h")
    if width and height:
        return float(width) / float(height)
    return 1.5


def domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def slugify(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    if words:
        return "-".join(word.lower() for word in words)
    return "x" + hashlib.md5(text.encode("utf-8")).hexdigest()[:6]


def sort_name(name: str) -> str:
    latin = " ".join(re.findall(r"[A-Za-zÀ-ÿ]+", name))
    if latin in SORT_NAME:
        return SORT_NAME[latin].lower()
    words = latin.split()
    return (words[-1] if words else name).lower()


# ── display text ──────────────────────────────────────────────


def scrub(text: str) -> str:
    """Drop sentences that only make sense inside the bot's working notes."""
    parts = [part for part in re.split(r"(?<=[。！？])", text) if part.strip()]
    kept = [part for part in parts if not INTERNAL.search(part)]
    return "".join(kept).strip()


def title_of(entry: dict) -> str:
    title = plain(entry.get("title") or "")
    if entry.get("edited"):
        return title
    title = re.sub(r"\s*·\s*非惊喜\s*$", "", title)
    if entry["stream"] == "photographer":
        title = re.sub(r"（[^）]*）\s*$", "", title)
    elif entry["stream"] == "aesthetic":
        title = re.sub(r"（[^）]*）", "", title)
    elif entry["stream"] == "28mm":
        title = re.sub(r"^第[一二三四五六七八九十\d]+课[：:]\s*", "", title)
    return title.strip() or plain(entry.get("title") or "")


def subtitle_of(entry: dict) -> str:
    if entry.get("edited"):
        return plain(entry.get("subtitle") or "")
    title = plain(entry.get("title") or "")
    if entry["stream"] == "photographer":
        match = re.search(r"（([^）]*)）\s*$", title)
        if not match:
            return ""
        parts = [part.strip() for part in re.split(r"[·・]", match.group(1))]
        return " · ".join(part for part in parts if part and part not in ("大师", "当代", "新锐"))
    if entry["stream"] == "aesthetic":
        match = re.search(r"（([A-Za-z][^）]*)）", title)
        return match.group(1).strip() if match else ""
    if entry["stream"] == "28mm":
        match = re.match(r"^(第[一二三四五六七八九十\d]+课)", title)
        return match.group(1) if match else (entry.get("category") or "")
    subtitle = plain(entry.get("subtitle") or "")
    return subtitle if len(subtitle) <= 40 else ""


def dek_of(entry: dict) -> str:
    text = plain(entry.get("summary") or "")
    if entry.get("edited"):
        return text
    subtitle = plain(entry.get("subtitle") or "")
    if entry["stream"] == "photographer" and len(subtitle) >= 24:
        text = subtitle
    text = re.sub(r"^今天这位是[^：:]{1,40}[：:]", "", text)
    head, sep, tail = text.partition("——")
    if sep and len(head) <= 40:
        text = tail
    text = scrub(text) or text
    if len(text) > 120:
        cut = max(text.rfind("。", 0, 120), text.rfind("；", 0, 120))
        text = text[: cut + 1] if cut > 30 else text[:118].rstrip("，、；, ") + "…"
    return text


def lesson_label(entry: dict) -> str:
    return subtitle_of(entry) if entry["stream"] == "28mm" else ""


# ── article body ──────────────────────────────────────────────


def clean_raw(entry: dict, blocks: list[dict]) -> list[dict]:
    title = title_of(entry)
    out: list[dict] = []
    dropping: int | None = None
    seen_heading = False
    for block in blocks:
        kind = block["type"]
        if kind == "heading":
            text = re.sub(r"\s*·\s*非惊喜\s*$", "", plain(block["text"]))
            if dropping is not None:
                if block["level"] > dropping:
                    continue
                dropping = None
            if not any(item["type"] != "heading" for item in out):
                if not seen_heading or (title and title in text):
                    seen_heading = True
                    continue
            seen_heading = True
            if DROP_SECTION.match(text):
                dropping = block["level"]
                continue
            for pattern, name in RENAME:
                if pattern.match(text):
                    text = name
                    break
            out.append({**block, "text": text})
            continue
        if dropping is not None or kind in ("code", "hr"):
            continue
        if kind == "para":
            raw = block["text"]
            flat = plain(raw)
            if DROP_LINE.search(raw) or re.fullmatch(r"28mm 专题 · .+课", flat) or flat.startswith("专题名："):
                continue
            if flat in (title, plain(entry.get("title") or "")) or flat.startswith(title + "（"):
                continue
            if not NUMBERED_WORK.match(raw):
                raw = re.sub(r"^今天这位是\*\*([^*]+)\*\*[：:]", r"**\1**：", raw)
                cleaned = scrub(raw)
                if not cleaned:
                    continue
                raw = cleaned
            out.append({**block, "text": raw})
            continue
        if kind == "list":
            items = [scrub(item) for item in block["items"] if not DROP_LINE.search(item)]
            items = [item for item in items if item and not INTERNAL.search(item[:24])]
            if items:
                out.append({**block, "items": items})
            continue
        out.append(block)
    levels = [block["level"] for block in out if block["type"] == "heading"]
    top = min(levels) if levels else 2
    for block in out:
        if block["type"] == "heading":
            block["level"] = 2 if block["level"] <= top else 3
    return out


def split_sections(blocks: list[dict]) -> tuple[list[dict], list[dict]]:
    intro: list[dict] = []
    sections: list[dict] = []
    for block in blocks:
        if block["type"] == "heading" and block["level"] <= 2:
            sections.append({"title": block["text"], "blocks": []})
        elif sections:
            sections[-1]["blocks"].append(block)
        else:
            intro.append(block)
    return intro, sections


def image_block(image: dict) -> dict:
    return {"type": "image", "alt": image.get("alt") or "", "src": image["src"]}


def place_images(entry: dict, intro: list[dict], sections: list[dict]) -> None:
    """Interleave thumbs into a raw body that carries no image lines of its own."""
    pool = list(entry.get("images") or [])
    if not pool:
        return
    if entry["stream"] in ("photographer", "meaning"):
        intro.insert(0, image_block(pool.pop(0)))
    works = next((sec for sec in sections if plain(sec["title"]) == "作品观察"), None)
    if works and pool:
        placed: list[dict] = []
        for block in works["blocks"]:
            match = NUMBERED_WORK.match(block["text"]) if block["type"] == "para" else None
            if match and pool:
                placed.append({"type": "heading", "level": 3, "text": match.group(2).strip()})
                placed.append(image_block(pool.pop(0)))
                if match.group(3).strip():
                    placed.append({"type": "para", "text": match.group(3).strip()})
            elif block["type"] == "list" and block["ordered"] and pool:
                for item in block["items"]:
                    if pool:
                        placed.append(image_block(pool.pop(0)))
                    placed.append({"type": "para", "text": item})
            else:
                placed.append(block)
        works["blocks"] = placed
    if not pool:
        return
    if entry["stream"] == "meaning":
        spread(intro, pool)
        return
    if works is None:
        works = {"title": "作品观察", "blocks": []}
        sections.append(works)
    works["blocks"].extend(image_block(image) for image in pool)


def spread(blocks: list[dict], images: list[dict]) -> None:
    """Hang images evenly between the paragraphs of a narrative."""
    paras = sum(1 for block in blocks if block["type"] == "para")
    slots: dict[int, list[dict]] = {}
    for index, image in enumerate(images):
        after = max(1, round((index + 1) * paras / (len(images) + 1))) if paras else 0
        slots.setdefault(after, []).append(image)
    out: list[dict] = []
    seen = 0
    for block in blocks:
        out.append(block)
        if block["type"] == "para":
            seen += 1
            out.extend(image_block(image) for image in slots.pop(seen, []))
    for rest in slots.values():
        out.extend(image_block(image) for image in rest)
    blocks[:] = out


def reorder(sections: list[dict]) -> None:
    rank = 0
    keyed = []
    for index, sec in enumerate(sections):
        rank = ORDER.get(plain(sec["title"]), rank)
        keyed.append((rank, index, sec))
    sections[:] = [sec for _, _, sec in sorted(keyed, key=lambda item: (item[0], item[1]))]


def same_text(flat: str, dek: str) -> bool:
    flat = re.sub(r"^[^：:。]{1,40}[：:]", "", flat).strip()
    return len(dek) >= 8 and flat.endswith(dek)


def repeats(dek: str, intro: list[dict], sections: list[dict]) -> bool:
    """True when the body already opens with the dek, so the header should not say it twice."""
    if len(dek) < 16:
        return False
    parts = []
    for block in intro + [block for sec in sections for block in sec["blocks"]]:
        if block["type"] == "para":
            parts.append(plain(block["text"]))
        elif block["type"] == "list":
            parts.extend(plain(item) for item in block["items"])
    return dek[:16] in " ".join(parts)


def append_unused(entry: dict, intro: list[dict], sections: list[dict]) -> None:
    used = {block["src"] for block in intro if block["type"] == "image"}
    for sec in sections:
        used.update(block["src"] for block in sec["blocks"] if block["type"] == "image")
    spare = [image for image in entry.get("images") or [] if image["src"] not in used]
    if not spare:
        return
    holder = next((sec for sec in sections if any(b["type"] == "image" for b in sec["blocks"])), None)
    target = holder["blocks"] if holder else intro
    target.extend(image_block(image) for image in spare)


class Page:
    """Rendering context for one article."""

    def __init__(self, site: "Site", entry: dict, depth: int) -> None:
        self.site = site
        self.entry = entry
        self.depth = depth
        self.images = {image["src"]: image for image in entry.get("images") or []}
        self.linked: set[str] = set()

    def resolve(self, target: str) -> str | None:
        other = self.site.by_id.get(target)
        if other is None:
            return None
        self.linked.add(target)
        return self.site.href(self.depth, entry_path(other))

    def text(self, md: str) -> str:
        return inline(md, resolve=self.resolve)

    def plate(self, block: dict, caption: bool = True, lead: bool = False) -> str:
        image = self.images.get(block["src"]) or {"src": block["src"], "alt": block.get("alt") or "", "caption": ""}
        cap = image.get("caption") or ""
        alt = image.get("alt") or plain(cap) or block.get("alt") or ""
        size = ""
        if image.get("w") and image.get("h"):
            size = f' width="{int(image["w"])}" height="{int(image["h"])}"'
        loading = 'loading="eager" fetchpriority="high"' if lead else 'loading="lazy"'
        label = f"放大查看：{plain(cap)}" if cap else "放大查看图片"
        figcaption = f"<figcaption>{inline(cap)}</figcaption>" if caption and cap else ""
        classes = "plate plate-lead" if lead else "plate"
        return (
            f'<figure class="{classes}" style="--r:{ratio(image):.4f}">'
            f'<button type="button" class="plate-open" data-src="{esc(image["src"])}" data-cap="{esc(plain(cap))}" aria-label="{esc(label)}">'
            f'<img src="{esc(image["src"])}" alt="{esc(alt)}"{size} {loading} decoding="async"></button>'
            f"{figcaption}</figure>"
        )

    def blocks(self, blocks: list[dict]) -> str:
        out: list[str] = []
        previous: dict | None = None
        for block in blocks:
            kind = block["type"]
            if kind == "para":
                out.append(f"<p>{self.text(block['text'])}</p>")
            elif kind == "list":
                tag = "ol" if block["ordered"] else "ul"
                items = "".join(f"<li>{self.text(item)}</li>" for item in block["items"])
                out.append(f"<{tag}>{items}</{tag}>")
            elif kind == "heading":
                out.append(f'<h3 class="work">{self.text(block["text"])}</h3>')
            elif kind == "image":
                titled = previous is not None and previous["type"] == "heading"
                out.append(self.plate(block, caption=not titled))
            elif kind == "hr":
                out.append('<hr class="rule">')
            previous = block
        return "\n".join(out)


# ── site ──────────────────────────────────────────────────────


class Site:
    def __init__(self, entries: list[dict], generated_at: str, topics: list[dict] | None = None) -> None:
        def order(entry: dict) -> tuple:
            return (-Date.fromisoformat(entry["date"]).toordinal(), STREAM_ORDER[entry["stream"]], entry.get("slug") or "")

        self.generated_at = generated_at
        self.entries = sorted(entries, key=order)
        self.by_id = {entry_id(entry): entry for entry in self.entries}
        self.by_stream = {item["key"]: [e for e in self.entries if e["stream"] == item["key"]] for item in STREAMS}
        self.latest = self.entries[0]["date"] if self.entries else ""
        self.topics = self.collect_topics(topics or [])
        self.people = self.collect_people()
        self.featured = self.pick_featured()

    # data

    def collect_topics(self, declared: list[dict]) -> list[dict]:
        found: list[dict] = []
        by_name: dict[str, dict] = {}
        for item in declared:
            topic = {"slug": item["slug"], "name": item["name"], "note": item.get("note") or "", "entries": []}
            found.append(topic)
            by_name[topic["name"]] = topic
        for entry in self.entries:
            for name in entry.get("topics") or []:
                topic = by_name.get(name)
                if topic is None:
                    topic = {"slug": slugify(name), "name": name, "note": "", "entries": []}
                    found.append(topic)
                    by_name[name] = topic
                topic["entries"].append(entry)
        self.topic_by_name = by_name
        return [topic for topic in found if topic["entries"]]

    def collect_people(self) -> list[dict]:
        index: dict[str, list[dict]] = {}
        for entry in self.entries:
            for name in entry.get("people") or []:
                index.setdefault(name, []).append(entry)
        people = [{"name": name, "slug": slugify(name), "entries": found} for name, found in index.items()]
        people.sort(key=lambda person: (sort_name(person["name"]), person["name"]))
        return people

    def pick_featured(self) -> dict | None:
        flagged = [entry for entry in self.entries if entry.get("featured")]
        if flagged:
            return flagged[0]
        day = [entry for entry in self.entries if entry["date"] == self.latest]
        with_images = [entry for entry in day if entry.get("images")]
        return (with_images or day or [None])[0]

    def chronological(self, stream: str) -> list[dict]:
        return sorted(self.by_stream[stream], key=lambda e: (e["date"], e.get("slug") or ""))

    # urls

    def href(self, depth: int, path: str) -> str:
        return "../" * depth + path

    def topic_href(self, topic: dict, depth: int) -> str:
        return self.href(depth, f"archive.html#topic-{topic['slug']}")

    # shared pieces

    def layout(self, *, depth: int, section: str, title: str, description: str, main: str,
               path: str, image: str = "", head_extra: str = "") -> str:
        up = "../" * depth
        current = ' aria-current="page"' if depth == 0 else ' aria-current="true"'
        nav = "".join(
            f'<a href="{up}{item["href"]}"{current if item["key"] == section else ""}>{esc(item["label"])}</a>'
            for item in SECTIONS
        )
        foot_nav = "".join(f'<a href="{up}{item["href"]}">{esc(item["label"])}</a>' for item in SECTIONS)
        foot_nav += f'<a href="{up}index.html#about">关于</a>'
        og_image = f'<meta property="og:image" content="{esc(image)}">' if image else ""
        return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#f3f6fb">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{SITE}{'' if path == 'index.html' else esc(path)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
{og_image}
<link rel="icon" href="{up}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{up}css/site.css">
<script>document.documentElement.classList.add("js");addEventListener("load",function(){{if(!window.muliReady)document.documentElement.classList.remove("js")}});</script>
{head_extra}
</head>
<body data-section="{esc(section)}">
<a class="skip" href="#main">跳到正文</a>
<header class="site-header">
  <div class="bar">
    <a class="brand" href="{up}index.html"><span class="mark" aria-hidden="true"></span>目力</a>
    <nav class="nav" aria-label="主导航">{nav}</nav>
  </div>
</header>
<main id="main" tabindex="-1">
{main}
</main>
<footer class="site-footer">
  <div class="bar">
    <a class="brand brand-foot" href="{up}index.html"><span class="mark" aria-hidden="true"></span>目力</a>
    <nav class="foot-nav" aria-label="页脚导航">{foot_nav}</nav>
    <p class="foot-meta"><span>最近更新 <time datetime="{esc(self.latest)}">{fmt_date(self.latest)}</time></span><span>{CREDIT}</span><a href="{REPO}">GitHub</a></p>
  </div>
</footer>
<dialog class="lightbox" id="lightbox" aria-label="放大图片">
  <div class="lb-bar">
    <span class="lb-count" id="lb-count" aria-live="polite"></span>
    <span class="lb-actions">
      <button type="button" id="lb-prev">上一张</button>
      <button type="button" id="lb-next">下一张</button>
      <button type="button" id="lb-close">关闭</button>
    </span>
  </div>
  <figure class="lb-figure"><img id="lb-img" alt=""><figcaption id="lb-cap"></figcaption></figure>
</dialog>
<script src="{up}js/app.js" defer></script>
</body>
</html>
"""

    def kicker(self, entry: dict) -> str:
        stream = STREAM[entry["stream"]]
        return f'<span class="kicker k-{stream["section"]}">{esc(stream["label"])}</span>'

    def thumb(self, image: dict, eager: bool = False) -> str:
        size = f' width="{int(image["w"])}" height="{int(image["h"])}"' if image.get("w") and image.get("h") else ""
        loading = 'loading="eager" fetchpriority="high"' if eager else 'loading="lazy"'
        return f'<img src="{esc(image["src"])}" alt=""{size} {loading} decoding="async" style="--r:{ratio(image):.4f}">'

    def strip(self, entry: dict) -> str:
        chosen: list[dict] = []
        total = 0.0
        for image in entry.get("images") or []:
            if chosen and total + ratio(image) > 3.3:
                continue
            chosen.append(image)
            total += ratio(image)
            if len(chosen) == 4:
                break
        if not chosen:
            return '<span class="strip strip-empty" aria-hidden="true"></span>'
        cells = "".join(
            f'<span class="cell" style="--r:{ratio(image):.4f}">{self.thumb(image)}</span>' for image in chosen
        )
        return f'<span class="strip" aria-hidden="true">{cells}</span>'

    def row(self, entry: dict, depth: int = 0, label: str = "") -> str:
        subtitle = subtitle_of(entry)
        dek = dek_of(entry)
        meta = label or f'<time datetime="{esc(entry["date"])}">{fmt_date(entry["date"])}</time>'
        sub = f'<span class="row-sub">{rich(subtitle)}</span>' if subtitle and not label else ""
        dek_html = f'<span class="row-dek">{rich(dek)}</span>' if dek else ""
        return (
            f'<li class="row"><a class="row-link" href="{self.href(depth, entry_path(entry))}">'
            f'<span class="row-meta">{meta}</span>'
            f'<span class="row-text"><span class="row-title">{esc(title_of(entry))}</span>{sub}{dek_html}</span>'
            f"{self.strip(entry)}</a></li>"
        )

    def index_item(self, entry: dict, show_date: bool = True, depth: int = 0) -> str:
        subtitle = subtitle_of(entry)
        date_html = f'<time datetime="{esc(entry["date"])}">{fmt_date(entry["date"])}</time>' if show_date else ""
        sub = f'<span class="ix-sub">{rich(subtitle)}</span>' if subtitle else ""
        return (
            f'<li><a href="{self.href(depth, entry_path(entry))}">{date_html}{self.kicker(entry)}'
            f'<span class="ix-title">{esc(title_of(entry))}</span>{sub}</a></li>'
        )

    def tablist(self, prefix: str, label: str, tabs: list[tuple[str, str]], sync: bool) -> str:
        links = []
        for index, (key, text) in enumerate(tabs):
            selected = "true" if index == 0 else "false"
            data = f' data-hash="{esc(key)}"' if sync else ""
            links.append(
                f'<a role="tab" id="{prefix}tab-{esc(key)}" href="#{prefix}panel-{esc(key)}" '
                f'aria-controls="{prefix}panel-{esc(key)}" aria-selected="{selected}"{data}>{esc(text)}</a>'
            )
        return f'<div class="tablist" role="tablist" aria-label="{esc(label)}">{"".join(links)}</div>'

    def panel(self, prefix: str, key: str, title: str, body: str, active: bool) -> str:
        state = " is-active" if active else ""
        return (
            f'<section class="tabpanel{state}" id="{prefix}panel-{esc(key)}" role="tabpanel" '
            f'aria-labelledby="{prefix}tab-{esc(key)}"><h2 class="panel-title">{esc(title)}</h2>{body}</section>'
        )

    # pages

    def render_home(self) -> str:
        featured = self.featured
        main: list[str] = ['<h1 class="sr">目力</h1>']
        shown: set[str] = set()
        if featured:
            shown.add(entry_id(featured))
            peers = [entry for entry in self.entries if entry["date"] == featured["date"] and entry is not featured]
            shown.update(entry_id(entry) for entry in peers)
            main.append(self.render_issue(featured, peers))
        tabs = [(item["key"], item["label"]) for item in STREAMS if self.by_stream[item["key"]]]
        panels = []
        for index, (key, label) in enumerate(tabs):
            pool = [entry for entry in self.by_stream[key] if entry_id(entry) not in shown] or self.by_stream[key]
            cards = "".join(self.card(entry) for entry in pool[:3])
            more = f'<p class="more"><a href="{STREAM_HREF[key]}">查看全部{esc(label)} →</a></p>'
            panels.append(self.panel("home-", key, label, f'<ul class="cards">{cards}</ul>{more}', index == 0))
        main.append(
            f"""<section class="recent" aria-labelledby="recent-title">
  <div class="tabs-head"><h2 class="label" id="recent-title">近期文章</h2>{self.tablist("home-", "近期文章栏目", tabs, sync=False)}</div>
  {"".join(panels)}
</section>"""
        )
        about = "".join(f"<p>{esc(text)}</p>" for text in ABOUT)
        main.append(
            f"""<section class="about" id="about" aria-labelledby="about-title">
  <h2 class="label" id="about-title">关于</h2>
  <div class="about-text">{about}</div>
</section>"""
        )
        image = (featured.get("images") or [{}])[0].get("src", "") if featured else ""
        return self.layout(
            depth=0,
            section="home",
            title="目力",
            description="目力：摄影师、视觉语言、28mm 专题和摄影与人生的文章。",
            main="\n".join(main),
            path="index.html",
            image=image,
            head_extra=self.legacy_script(),
        )

    def render_issue(self, featured: dict, peers: list[dict]) -> str:
        href = entry_path(featured)
        images = featured.get("images") or []
        lead = images[0] if images else None
        figure = ""
        portrait = bool(lead) and ratio(lead) < 1.05
        if lead:
            cap = lead.get("caption") or ""
            if featured["stream"] == "photographer" and cap:
                cap = f"{title_of(featured)} — {cap}"
            size = f' width="{int(lead["w"])}" height="{int(lead["h"])}"' if lead.get("w") and lead.get("h") else ""
            figure = (
                f'<figure class="issue-figure" style="--r:{ratio(lead):.4f}">'
                f'<a href="{href}" tabindex="-1" aria-hidden="true"><img src="{esc(lead["src"])}" '
                f'alt="{esc(lead.get("alt") or plain(cap))}"{size} loading="eager" fetchpriority="high" decoding="async"></a>'
                f'{wrap("figcaption", "cap", inline(cap) if cap else "")}</figure>'
            )
        topic = next((self.topic_by_name[name] for name in featured.get("topics") or [] if name in self.topic_by_name), None)
        topic_html = (
            f'<p class="issue-topic">本期主题<a href="{self.topic_href(topic, 0)}">{esc(topic["name"])}</a></p>' if topic else ""
        )
        peer_items = []
        for entry in peers:
            pic = (entry.get("images") or [None])[0]
            pic_html = f'<span class="peer-img">{self.thumb(pic)}</span>' if pic else ""
            peer_items.append(
                f'<li><a href="{entry_path(entry)}">{pic_html}<span class="peer-text">{self.kicker(entry)}'
                f'<span class="peer-title">{esc(title_of(entry))}</span>'
                f'{wrap("span", "peer-sub", rich(subtitle_of(entry)))}</span></a></li>'
            )
        also = (
            f'<div class="also"><h3 class="label">同期</h3><ul>{"".join(peer_items)}</ul></div>' if peer_items else ""
        )
        layout = "issue-portrait" if portrait else "issue-wide"
        return f"""<section class="issue {layout}" aria-labelledby="issue-title">
  {figure}
  <div class="issue-text">
    <p class="eyebrow">本期精选<span aria-hidden="true">·</span><time datetime="{esc(featured["date"])}">{fmt_date(featured["date"])}</time><span aria-hidden="true">·</span>{esc(STREAM[featured["stream"]]["label"])}</p>
    <h2 class="display" id="issue-title"><a href="{href}">{esc(title_of(featured))}</a></h2>
    {wrap("p", "subtitle", rich(subtitle_of(featured)))}
    {wrap("p", "dek", rich(dek_of(featured)))}
    {topic_html}
    {also}
  </div>
</section>"""

    def card(self, entry: dict) -> str:
        pic = (entry.get("images") or [None])[0]
        figure = f'<span class="card-img">{self.thumb(pic)}</span>' if pic else '<span class="card-img card-img-empty"></span>'
        subtitle = "" if entry["stream"] == "28mm" else subtitle_of(entry)
        meta = lesson_label(entry) or fmt_date(entry["date"])
        return (
            f'<li class="card"><a href="{entry_path(entry)}">{figure}'
            f'<span class="card-meta"><time datetime="{esc(entry["date"])}">{esc(meta)}</time></span>'
            f'<h3 class="card-title">{esc(title_of(entry))}</h3>'
            f'{wrap("span", "card-sub", rich(subtitle))}{wrap("span", "card-dek", rich(dek_of(entry)))}</a></li>'
        )

    def render_learn(self) -> str:
        tabs = [("photographer", "摄影师"), ("aesthetic", "视觉语言")]
        panels = []
        for index, (key, label) in enumerate(tabs):
            rows = "".join(self.row(entry) for entry in self.by_stream[key])
            panels.append(self.panel("", key, label, f'<ol class="rows">{rows}</ol>', index == 0))
        main = f"""<div class="page">
  <header class="page-head"><h1>审美学习</h1></header>
  <div class="tabs-head">{self.tablist("", "审美学习栏目", tabs, sync=True)}</div>
  {"".join(panels)}
</div>"""
        return self.layout(
            depth=0, section="learn", title="审美学习 · 目力",
            description="摄影师与视觉语言：从作者和画面关系两头学看照片。",
            main=main, path="learn.html",
        )

    def render_practice(self) -> str:
        lessons = self.chronological("28mm")
        rows = "".join(self.row(entry, label=esc(lesson_label(entry) or fmt_date(entry["date"]))) for entry in lessons)
        main = f"""<div class="page">
  <header class="page-head"><h1>摄影实践</h1></header>
  <section class="series" id="series-28mm" aria-labelledby="series-28mm-title">
    <div class="series-head"><h2 id="series-28mm-title">28mm 专题</h2><p>{esc(PRACTICE_PLAN)}</p></div>
    <ol class="rows">{rows}</ol>
  </section>
</div>"""
        return self.layout(
            depth=0, section="practice", title="摄影实践 · 目力",
            description="28mm 专题：走近、低机位、侧移半步，每课一件出门就能练的事。",
            main=main, path="practice.html",
        )

    def render_life(self) -> str:
        rows = "".join(self.row(entry) for entry in self.by_stream["meaning"])
        main = f"""<div class="page">
  <header class="page-head"><h1>摄影与人生</h1><p class="page-dek">{esc(LIFE_DEK)}</p></header>
  <ol class="rows">{rows}</ol>
</div>"""
        return self.layout(
            depth=0, section="life", title="摄影与人生 · 目力",
            description=LIFE_DEK, main=main, path="life.html",
        )

    def render_archive(self) -> str:
        topic_html = []
        for topic in self.topics:
            note = f'<p class="topic-note">{esc(topic["note"])}</p>' if topic["note"] else ""
            items = "".join(self.index_item(entry) for entry in topic["entries"])
            topic_html.append(
                f'<section class="topic" id="topic-{esc(topic["slug"])}"><h3>{esc(topic["name"])}</h3>{note}'
                f'<ul class="index">{items}</ul></section>'
            )
        untagged = [entry for entry in self.entries if not entry.get("topics")]
        if untagged:
            items = "".join(self.index_item(entry) for entry in untagged)
            topic_html.append(f'<section class="topic" id="topic-other"><h3>其他</h3><ul class="index">{items}</ul></section>')
        people_html = []
        for person in self.people:
            items = "".join(
                f'<li><a href="{entry_path(entry)}">{self.kicker(entry)}<span class="ix-title">{esc(title_of(entry))}</span></a></li>'
                for entry in person["entries"]
            )
            people_html.append(
                f'<section class="person" id="person-{esc(person["slug"])}"><h3>{esc(person["name"])}</h3>'
                f'<ul class="mini">{items}</ul></section>'
            )
        days: dict[str, list[dict]] = {}
        for entry in self.entries:
            days.setdefault(entry["date"], []).append(entry)
        day_html = []
        for day, found in days.items():
            items = "".join(self.index_item(entry, show_date=False) for entry in found)
            day_html.append(
                f'<section class="day"><h3><time datetime="{esc(day)}">{fmt_date(day)}</time>'
                f'<span class="weekday">{weekday(day)}</span></h3><ul class="index">{items}</ul></section>'
            )
        tabs = [("topics", "按主题"), ("people", "按作者"), ("timeline", "按时间")]
        bodies = {
            "topics": f'<div class="topics">{"".join(topic_html)}</div>',
            "people": f'<div class="people">{"".join(people_html)}</div>',
            "timeline": f'<div class="timeline">{"".join(day_html)}</div>',
        }
        panels = "".join(self.panel("", key, label, bodies[key], index == 0) for index, (key, label) in enumerate(tabs))
        first = self.entries[-1]["date"] if self.entries else ""
        span = f"{fmt_date(first)} — {fmt_date(self.latest)} · {len(self.entries)} 篇" if self.entries else ""
        main = f"""<div class="page">
  <header class="page-head"><h1>归档</h1><p class="page-meta">{span}</p></header>
  <div class="tabs-head">{self.tablist("", "归档方式", tabs, sync=True)}</div>
  {panels}
</div>"""
        return self.layout(
            depth=0, section="archive", title="归档 · 目力",
            description="按主题、按作者、按时间浏览目力的全部文章。",
            main=main, path="archive.html",
        )

    def render_article(self, entry: dict) -> str:
        depth = 1
        page = Page(self, entry, depth)
        stream = STREAM[entry["stream"]]
        blocks = parse_blocks(entry.get("body") or "")
        raw = not entry.get("edited")
        if raw:
            blocks = clean_raw(entry, blocks)
        intro, sections = split_sections(blocks)
        dek = dek_of(entry)
        header_dek = dek
        if raw:
            intro = [block for block in intro if not (block["type"] == "para" and same_text(plain(block["text"]), dek))]
        if raw and not any(block["type"] == "image" for block in blocks):
            place_images(entry, intro, sections)
        else:
            append_unused(entry, intro, sections)
        if raw:
            reorder(sections)
            if repeats(dek, intro, sections):
                header_dek = ""

        lead_html = ""
        if intro and intro[0]["type"] == "image":
            lead_html = page.plate(intro[0], lead=True)
            intro = intro[1:]
        parts = [f'<div class="intro">{page.blocks(intro)}</div>'] if intro else []
        number = 0
        for sec in sections:
            name = plain(sec["title"])
            content = page.blocks(sec["blocks"])
            if name == "核心判断":
                parts.append(f'<section class="thesis"><h2 class="label">核心判断</h2>{content}</section>')
                continue
            numbered = entry["stream"] != "meaning" and name not in UNNUMBERED
            if numbered:
                number += 1
            classes = ["sec"]
            if name in BOXED:
                classes += ["box", f"box-{BOXED[name]}"]
            if name == "资料来源":
                classes.append("sources")
            num = f'<span class="num">{number:02d}</span><span class="slash" aria-hidden="true">/</span>' if numbered else ""
            parts.append(f'<section class="{" ".join(classes)}"><h2>{num}<span class="name">{esc(name)}</span></h2>{content}</section>')

        header = f"""<header class="article-head">
    <nav class="crumbs" aria-label="位置"><a href="../index.html">目力</a><span aria-hidden="true">/</span><a href="../{STREAM_HREF[entry["stream"]]}">{esc(stream["label"])}</a><span aria-hidden="true">/</span><time datetime="{esc(entry["date"])}">{fmt_date(entry["date"])}</time></nav>
    <h1>{esc(title_of(entry))}</h1>
    {wrap("p", "subtitle", rich(subtitle_of(entry)))}
    {wrap("p", "dek", rich(header_dek))}
  </header>"""
        body_html = "\n".join(parts)
        foot = self.article_foot(entry, page)
        main = f"""<article class="article" data-stream="{esc(entry["stream"])}">
  {header}
  {lead_html}
  <div class="article-body">
{body_html}
  </div>
  {foot}
</article>"""
        image = (entry.get("images") or [{}])[0].get("src", "")
        return self.layout(
            depth=depth,
            section=stream["section"],
            title=f"{title_of(entry)} · {stream['label']} · 目力",
            description=dek or title_of(entry),
            main=main,
            path=entry_path(entry),
            image=image,
        )

    def article_foot(self, entry: dict, page: Page) -> str:
        out: list[str] = []
        if entry.get("credit"):
            out.append(f'<p class="credit">{inline(entry["credit"])}</p>')
        body = entry.get("body") or ""
        seen: set[str] = set()
        links = []
        for link in entry.get("links") or []:
            url = link.get("url") or ""
            if not url or url in seen or url in body:
                continue
            seen.add(url)
            links.append(
                f'<li><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{inline(link.get("label") or url, external=False)}'
                f'<span class="sr">（新窗口）</span></a><span class="domain">{esc(domain(url))}</span></li>'
            )
        if links:
            out.append(f'<section class="further"><h2 class="label">作品与延伸阅读</h2><ul>{"".join(links)}</ul></section>')

        order = self.chronological(entry["stream"])
        position = order.index(entry)
        older = order[position - 1] if position > 0 else None
        newer = order[position + 1] if position + 1 < len(order) else None
        skip = {entry_id(entry)} | page.linked | {entry_id(item) for item in (older, newer) if item}
        mine = [name for name in entry.get("topics") or [] if name in self.topic_by_name]
        scored = []
        for other in self.entries:
            if entry_id(other) in skip:
                continue
            shared = len(set(mine) & set(other.get("topics") or []))
            if shared:
                scored.append((-shared, other))
        scored.sort(key=lambda pair: pair[0])
        related = [other for _, other in scored[:4]]
        if mine:
            topics = "".join(
                f'<a href="{self.topic_href(self.topic_by_name[name], 1)}">{esc(name)}</a>' for name in mine
            )
            items = "".join(self.index_item(other, depth=1) for other in related)
            out.append(
                f'<section class="related"><h2 class="label">{"同一主题" if related else "主题"}'
                f'<span class="topic-links">{topics}</span></h2>{wrap("ul", "index", items)}</section>'
            )
        pager = []
        if older:
            pager.append(
                f'<a class="prev" href="../{entry_path(older)}" rel="prev"><span class="label">上一篇</span>'
                f'<span class="pager-title">{esc(title_of(older))}</span></a>'
            )
        if newer:
            pager.append(
                f'<a class="next" href="../{entry_path(newer)}" rel="next"><span class="label">下一篇</span>'
                f'<span class="pager-title">{esc(title_of(newer))}</span></a>'
            )
        if pager:
            out.append(f'<nav class="pager" aria-label="{esc(STREAM[entry["stream"]]["label"])}前后篇">{"".join(pager)}</nav>')
        return f'<footer class="article-foot">{"".join(out)}</footer>' if out else ""

    def legacy_script(self) -> str:
        known = json.dumps({entry_id(entry): entry_path(entry) for entry in self.entries}, separators=(",", ":"))
        sections = json.dumps({**STREAM_HREF, "archive": "archive.html"}, separators=(",", ":"))
        return (
            "<script>(function(){var k=" + known + ",s=" + sections + ","
            "h=location.hash.slice(1),q=new URLSearchParams(location.search),t=q.get('tab'),n=q.get('entry'),"
            "m={photographer:'photographer',aesthetic:'aesthetic','28mm':'28mm',mm28:'28mm',meaning:'meaning'};"
            "if(t&&m[t])h=m[t]+(n?'-'+n:'');"
            "var u=k[h];if(!u){var p=/^(photographer|aesthetic|28mm|meaning)(?:-|$)/.exec(h);u=p?s[p[1]]:s[h];}"
            "if(u)location.replace(u);})();</script>"
        )


def render_site(entries: list[dict], generated_at: str, topics: list[dict] | None = None) -> dict[str, str]:
    """Return {relative path: html} for every page of the site."""
    site = Site(entries, generated_at, topics)
    pages = {
        "index.html": site.render_home(),
        "learn.html": site.render_learn(),
        "practice.html": site.render_practice(),
        "life.html": site.render_life(),
        "archive.html": site.render_archive(),
    }
    for entry in site.entries:
        pages[entry_path(entry)] = site.render_article(entry)
    return pages


def render_index(entries: list[dict], generated_at: str, topics: list[dict] | None = None) -> str:
    return render_site(entries, generated_at, topics)["index.html"]
