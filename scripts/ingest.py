#!/usr/bin/env python3
"""Ingest 目力's four streams into content markdown and the static site.

Trigger contract: after 掌印 / 目力 confirms the day's push files, run

    python3 scripts/ingest.py --brief /path/to/vault

That upserts content/{photographer,aesthetic,28mm}/YYYY-MM-DD.md and
content/meaning/YYYY-MM-DD-slug.md, then rewrites every page (index.html,
learn.html, practice.html, life.html, archive.html and one page per article)
plus data/catalog.json. Entries marked `edited` are never overwritten.
Commit with `git add -A` and push main.

    python3 scripts/ingest.py --json path/to/content.json --brief /path/to/brief
    python3 scripts/ingest.py --from-content
    python3 scripts/ingest.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mdutil import md_to_html, plain  # noqa: E402
from render_site import STREAMS, entry_path, render_site  # noqa: E402

CDN = "https://fastly.jsdelivr.net/gh/senlau/picx-images-hosting@master/muli/"
ROOT = Path(__file__).resolve().parents[1]
STREAM_FROM_JSON = {
    "photographer": "photographer",
    "aesthetic": "aesthetic",
    "mm28": "28mm",
    "28mm": "28mm",
    "meaning": "meaning",
}
FOLDER_OF = {item["hash"]: item["folder"] for item in STREAMS}


def extract_images(md: str) -> list[dict]:
    images: list[dict] = []
    seen: set[str] = set()

    def add(src: str, alt: str = "", caption: str = "") -> None:
        src = unescape(src).rstrip("）)。.,")
        if not src or src in seen:
            return
        if not re.search(r"\.(jpg|jpeg|png|webp|gif)$", src, re.I):
            return
        seen.add(src)
        images.append({"src": src, "alt": unescape(alt or "").strip(), "caption": unescape(caption or "").strip()})

    for match in re.finditer(
        r"<figure[^>]*>\s*<img\b([^>]+)>(?:\s*<figcaption[^>]*>(.*?)</figcaption>)?\s*</figure>",
        md,
        re.I | re.S,
    ):
        attrs, cap = match.group(1), match.group(2) or ""
        src_m = re.search(r'src=["\']([^"\']+)["\']', attrs, re.I)
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', attrs, re.I)
        if not src_m:
            continue
        cap_txt = re.sub(r"<[^>]+>", "", cap).strip()
        add(src_m.group(1), alt_m.group(1) if alt_m else "", cap_txt)

    for match in re.finditer(r"<img\b([^>]+)/?>", md, re.I):
        attrs = match.group(1)
        src_m = re.search(r'src=["\']([^"\']+)["\']', attrs, re.I)
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', attrs, re.I)
        if src_m:
            add(src_m.group(1), alt_m.group(1) if alt_m else "", "")

    for match in re.finditer(
        r"CDN:\s*(https://fastly\.jsdelivr\.net/[^\s]+)\s*\n\s*图注[：:]\s*([^\n]+)",
        md,
    ):
        add(match.group(1), "", match.group(2).strip())

    for match in re.finditer(
        r"https://fastly\.jsdelivr\.net/gh/senlau/picx-images-hosting@master/muli/[^\s)\"']+",
        md,
    ):
        add(match.group(0), "", "")
    return images


def strip_figures(md: str) -> str:
    md = re.sub(r'<div\s+style="display:flex;[\s\S]*?</div>\s*', "", md, flags=re.I)
    md = re.sub(r"<figure[\s\S]*?</figure>\s*", "", md, flags=re.I)
    md = re.sub(r"<img\b[^>]*/?>\s*", "", md, flags=re.I)
    md = re.sub(r"\n##\s*本机图\s*\+\s*CDN[\s\S]*?(?=\n##\s|\Z)", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md


def extract_links(md: str) -> list[dict]:
    links = []
    seen = set()
    for label, url in re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", md):
        key = (label.strip(), url.strip())
        if key in seen:
            continue
        seen.add(key)
        links.append({"label": label.strip(), "url": url.strip()})
    return links


def first_heading(md: str) -> str:
    match = re.search(r"^#{1,3}\s+(.+)$", md, re.M)
    return match.group(1).strip() if match else ""


def parse_date_title(heading: str, fallback_date: str) -> tuple[str, str]:
    heading = heading.strip()
    match = re.match(r"^(\d{4}-\d{2}-\d{2})\s*[｜|]\s*(.+)$", heading)
    if match:
        return match.group(1), match.group(2).strip()
    match = re.match(r"^每日审美一课\s*[｜|]\s*(\d{4}-\d{2}-\d{2})\s*$", heading)
    if match:
        return match.group(1), ""
    match = re.match(r"^28mm\s*专题\s*[｜|]\s*(.+)$", heading)
    if match:
        return fallback_date, match.group(1).strip()
    return fallback_date, heading


def make_summary(md_clean: str) -> str:
    lines: list[str] = []
    for line in md_clean.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("!"):
            if lines:
                break
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            if lines:
                break
            continue
        plain_line = re.sub(r"\*+", "", stripped).strip()
        if plain_line.startswith("专题名：") or re.fullmatch(r"28mm 专题 · .+课", plain_line):
            continue
        if len(plain_line) < 12 and "课" in plain_line:
            continue
        lines.append(stripped)
        if len(" ".join(lines)) >= 220:
            break
    text = " ".join(lines)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    parts = [part for part in re.split(r"(?<=[。！？])\s*", text) if part.strip()]
    if not parts:
        return text[:200]
    summary = "".join(parts[:3])
    if len(parts) == 1 and len(summary) > 240:
        summary = summary[:240].rstrip("，、；, ") + "…"
    return summary


def tags_from(stream: str, title: str, category: str) -> list[str]:
    tags: list[str] = []
    if category:
        tags.append(category)
    for match in re.finditer(r"（([^）]+)）", title):
        for part in re.split(r"[·/／、,，]", match.group(1)):
            piece = part.strip()
            if piece and piece not in tags and len(piece) < 40:
                tags.append(piece)
    if stream == "28mm" and "28mm" not in tags:
        tags.append("28mm")
    out: list[str] = []
    seen = set()
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out[:8]


def category_photographer(md: str, title: str) -> str:
    match = re.search(r"(?:####|##)\s*类别\s*\n+([^\n#]+)", md)
    if match:
        return match.group(1).strip()
    match = re.search(r"（([^）]+)）", title)
    if match:
        return match.group(1).split("·")[0].strip()
    return ""


def category_aesthetic(md: str, title: str) -> str:
    return ""


def category_mm28(md: str, title: str) -> str:
    match = re.search(r"第([一二三四五六七八九十\d]+)课", title)
    if match:
        return f"第{match.group(1)}课"
    match = re.search(r"\*\*28mm 专题 · ([^*]+)\*\*", md)
    if match:
        return match.group(1).strip()
    return "28mm专题"


def blank_entry() -> dict:
    return {
        "date": "",
        "title": "",
        "stream": "",
        "subtitle": "",
        "summary": "",
        "category": "",
        "tags": [],
        "topics": [],
        "people": [],
        "images": [],
        "links": [],
        "body": "",
    }


def looks_like_slug(alt: str, src: str) -> bool:
    stem = Path(src.split("?", 1)[0]).stem.lower()
    norm = (alt or "").strip().lower().replace(" ", "-")
    return (not alt) or norm == stem or alt.strip() == Path(src).stem


def polish_image(image: dict) -> None:
    if image.get("caption") and looks_like_slug(image.get("alt") or "", image["src"]):
        image["alt"] = plain(image["caption"])[:180]


def finalize(entry: dict) -> dict:
    entry["body"] = strip_figures(entry.get("body") or "")
    if not entry.get("images"):
        entry["images"] = extract_images(entry["body"])
    for image in entry["images"]:
        polish_image(image)
    if not entry.get("links"):
        entry["links"] = extract_links(entry["body"])
    if not entry.get("summary"):
        entry["summary"] = make_summary(entry["body"])
    if entry["stream"] == "photographer":
        match = re.search(r"今天这位是\*\*([^*]+)\*\*[：:]([^\n]+)", entry["body"])
        if match:
            entry["subtitle"] = plain(match.group(2))
    entry["html"] = md_to_html(entry["body"])
    return entry


def entry_from_md(md: str, stream: str, fallback_date: str) -> dict:
    heading = first_heading(md)
    date, title = parse_date_title(heading, fallback_date)
    subtitle = ""
    if stream == "aesthetic":
        h2 = ""
        h2m = re.search(r"^##\s+(.+)$", md, re.M)
        if h2m:
            h2 = h2m.group(1).strip()
        if heading.startswith("每日审美一课"):
            title = h2 or title or date
        elif not title:
            title = h2 or heading or date
    if stream == "photographer":
        match = re.search(r"今天这位是\*\*([^*]+)\*\*[：:]([^\n]+)", md)
        if match:
            subtitle = plain(match.group(2))
        category = category_photographer(md, title)
    elif stream == "aesthetic":
        category = category_aesthetic(md, title or heading)
    else:
        match = re.search(r"专题名：\*\*([^*]+)\*\*", md)
        if match:
            subtitle = match.group(1).strip()
        category = category_mm28(md, title)
    if not title:
        title = heading or fallback_date
    entry = blank_entry()
    entry.update(
        {
            "date": date,
            "title": title,
            "stream": stream,
            "subtitle": subtitle,
            "category": category,
            "tags": tags_from(stream, title, category),
            "images": extract_images(md),
            "links": extract_links(md),
            "body": md.strip() + "\n",
        }
    )
    return finalize(entry)


def rollup_sections(text: str, stop_heading: str | None) -> list[tuple[str, str, str]]:
    if stop_heading:
        idx = text.find(stop_heading)
        if idx != -1:
            text = text[:idx]
    sections = []
    for part in re.split(r"\n(?=### \d{4}-\d{2}-\d{2})", text):
        match = re.match(r"### (\d{4}-\d{2}-\d{2})[｜|](.+)", part.strip())
        if not match:
            continue
        body = part.strip() + "\n"
        sections.append((match.group(1), match.group(2).strip(), body))
    return sections


def merge_images(dst: dict, src_images: list[dict]) -> None:
    by_src = {image["src"]: image for image in dst["images"]}
    for image in src_images:
        current = by_src.get(image["src"])
        if current is None:
            dst["images"].append(dict(image))
            by_src[image["src"]] = dst["images"][-1]
            continue
        if image.get("caption") and not current.get("caption"):
            current["caption"] = image["caption"]
        if image.get("alt") and looks_like_slug(current.get("alt") or "", image["src"]):
            if not looks_like_slug(image["alt"], image["src"]):
                current["alt"] = image["alt"]


def entry_key(entry: dict) -> tuple[str, str, str]:
    return (entry["stream"], entry["date"], entry.get("slug") or "")


def upsert(entries: list[dict], incoming: dict) -> list[dict]:
    for index, entry in enumerate(entries):
        if entry_key(entry) == entry_key(incoming):
            if entry.get("edited"):
                print(f"keep edited {entry_path(entry)}", file=sys.stderr)
                return entries
            merge_images(entry, incoming.get("images") or [])
            incoming_body = (incoming.get("body") or "").strip()
            current_body = (entry.get("body") or "").strip()
            if len(plain(current_body)) < 400 and len(incoming_body) > len(current_body) + 80:
                entry["body"] = incoming["body"]
                if incoming.get("title"):
                    entry["title"] = incoming["title"]
                if incoming.get("subtitle"):
                    entry["subtitle"] = incoming["subtitle"]
                if incoming.get("category"):
                    entry["category"] = incoming["category"]
                if incoming.get("tags"):
                    entry["tags"] = incoming["tags"]
                entry["summary"] = ""
                entry["links"] = incoming.get("links") or entry.get("links") or []
            finalize(entry)
            entries[index] = entry
            return entries
    entries.append(finalize(incoming))
    return entries


def derive_meaning_slug(title: str) -> str:
    """Derive a slug for meaning entries from the title.

    Takes the first token before a Chinese colon (：), extracts the latin surname
    (last word if multiple), and lowercases. Fallback to first latin word.
    Examples:
        "John Mannell：Portrait Per Day 与..." -> "mannell"
        "Michael Goldrei：Chance Street 与..." -> "goldrei"
    """
    match = re.match(r"^([^：]+)", title)
    if not match:
        return ""
    name_part = match.group(1).strip()
    words = [w for w in name_part.split() if re.fullmatch(r"[A-Za-z]+", w)]
    if not words:
        return ""
    return words[-1].lower()


def parse_brief(root: Path) -> list[dict]:
    entries: list[dict] = []
    daily = root / "daily"
    mm = root / "28mm"
    if daily.is_dir():
        for folder in sorted(path for path in daily.iterdir() if path.is_dir()):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", folder.name):
                rec = folder / "recommendation.md"
                if rec.exists():
                    entries.append(entry_from_md(rec.read_text(encoding="utf-8"), "photographer", folder.name))
            if folder.name.endswith("-aesthetic"):
                date = folder.name[: -len("-aesthetic")]
                lesson = folder / "lesson.md"
                if not lesson.exists():
                    continue
                md = lesson.read_text(encoding="utf-8")
                chat = folder / "CHAT_PUSH.md"
                if chat.exists() and len(md) < 800:
                    chat_md = chat.read_text(encoding="utf-8")
                    if len(chat_md) > len(md):
                        md = chat_md
                entries.append(entry_from_md(md, "aesthetic", date))
        meaning_stories = daily / "meaning-stories"
        if meaning_stories.is_dir():
            for date_folder in sorted(path for path in meaning_stories.iterdir() if path.is_dir()):
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_folder.name):
                    continue
                for md_file in sorted(date_folder.glob("*.md")):
                    md = md_file.read_text(encoding="utf-8")
                    incoming = entry_from_md(md, "meaning", date_folder.name)
                    slug = derive_meaning_slug(incoming["title"])
                    if slug:
                        incoming["slug"] = slug
                    entries = upsert(entries, incoming)
    if mm.is_dir():
        for folder in sorted(path for path in mm.iterdir() if path.is_dir()):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", folder.name):
                continue
            lesson = folder / "lesson.md"
            if lesson.exists():
                entries.append(entry_from_md(lesson.read_text(encoding="utf-8"), "28mm", folder.name))

    rollups = [
        (root / "作者长卷.md", "photographer", "## 专题批次"),
        (root / "审美词本.md", "aesthetic", None),
        (root / "广角手记.md", "28mm", None),
        (root / "意义长卷.md", "meaning", None),
    ]
    for path, stream, stop in rollups:
        if not path.exists():
            continue
        for date, title, body in rollup_sections(path.read_text(encoding="utf-8"), stop):
            incoming = entry_from_md(body, stream, date)
            if title and (not incoming["title"] or incoming["title"] == date):
                incoming["title"] = title
            if stream == "meaning":
                slug = derive_meaning_slug(incoming["title"])
                if slug:
                    incoming["slug"] = slug
            entries = upsert(entries, incoming)
    return entries


def normalize_json_entry(raw: dict, stream: str) -> dict:
    images = []
    for image in raw.get("images") or []:
        images.append(
            {
                "src": image.get("src") or "",
                "alt": image.get("alt") or "",
                "caption": image.get("caption") or "",
                **({"w": image["w"], "h": image["h"]} if image.get("w") and image.get("h") else {}),
            }
        )
    entry = blank_entry()
    entry.update(
        {
            "date": raw.get("date") or "",
            "title": raw.get("title") or "",
            "stream": stream,
            "subtitle": raw.get("subtitle") or "",
            "summary": raw.get("summary") or "",
            "category": raw.get("category") or "",
            "tags": list(raw.get("tags") or []),
            "images": [image for image in images if image["src"]],
            "links": [
                {"label": link.get("label") or link.get("url") or "", "url": link["url"]}
                for link in (raw.get("links") or [])
                if link.get("url")
            ],
            "body": (raw.get("bodyMarkdown") or raw.get("body") or "").strip() + "\n",
        }
    )
    return finalize(entry)


def keep_edited(current: list[dict], incoming: list[dict]) -> list[dict]:
    """A snapshot never replaces an entry that has been edited by hand."""
    edited = {entry_key(entry): entry for entry in current if entry.get("edited")}
    merged = [edited.pop(entry_key(entry), entry) for entry in incoming]
    return merged + list(edited.values())


def load_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    streams = data["streams"] if isinstance(data, dict) and "streams" in data else data
    entries: list[dict] = []
    for key, items in streams.items():
        stream = STREAM_FROM_JSON.get(key)
        if not stream:
            raise SystemExit(f"unknown stream in JSON: {key}")
        for raw in items:
            entries.append(normalize_json_entry(raw, stream))
    return entries


def enrich_from_brief(entries: list[dict], root: Path) -> None:
    blobs = []
    for path in sorted(root.rglob("*.md")):
        blobs.append(path.read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for blob in blobs:
        for image in extract_images(blob):
            current = index.get(image["src"])
            if current is None:
                index[image["src"]] = dict(image)
                continue
            if image.get("caption") and not current.get("caption"):
                current["caption"] = image["caption"]
            if image.get("alt") and looks_like_slug(current.get("alt") or "", image["src"]):
                if not looks_like_slug(image["alt"], image["src"]):
                    current["alt"] = image["alt"]
    for entry in entries:
        present = {image["src"] for image in entry["images"]}
        blob_best = ""
        best_hits = 0
        for blob in blobs:
            hits = sum(1 for src in present if src in blob)
            if hits > best_hits:
                best_hits = hits
                blob_best = blob
        for image in entry["images"]:
            found = index.get(image["src"])
            if not found:
                continue
            if found.get("caption") and not image.get("caption"):
                image["caption"] = found["caption"]
            if found.get("alt") and looks_like_slug(image.get("alt") or "", image["src"]):
                if not looks_like_slug(found["alt"], image["src"]):
                    image["alt"] = found["alt"]
            polish_image(image)
        if blob_best and best_hits:
            rank = {image["src"]: i for i, image in enumerate(extract_images(blob_best))}
            entry["images"].sort(key=lambda image: rank.get(image["src"], 10_000))
        entry["html"] = md_to_html(entry["body"])


def dump_front_matter(entry: dict) -> str:
    thumbs = []
    for image in entry["images"]:
        item = {"src": image["src"], "alt": image.get("alt") or "", "caption": image.get("caption") or ""}
        if image.get("w") and image.get("h"):
            item["w"] = int(image["w"])
            item["h"] = int(image["h"])
        thumbs.append(item)
    fields = {
        "date": entry["date"],
        "title": entry["title"],
        "stream": entry["stream"],
        "subtitle": entry.get("subtitle") or "",
        "summary": entry.get("summary") or "",
        "category": entry.get("category") or "",
        "tags": entry.get("tags") or [],
    }
    for key in ("topics", "people"):
        if entry.get(key):
            fields[key] = entry[key]
    fields["thumbs"] = thumbs
    fields["links"] = entry.get("links") or []
    for key in ("credit", "slug"):
        if entry.get(key):
            fields[key] = entry[key]
    for key in ("edited", "featured"):
        if entry.get(key):
            fields[key] = True
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    lines.append("")
    lines.append((entry.get("body") or "").strip() + "\n")
    return "\n".join(lines)


def parse_front_matter(text: str) -> dict:
    if not text.startswith("---\n"):
        raise ValueError("missing front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated front matter")
    meta = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = json.loads(value.strip())
    body = text[end + 5 :]
    if body.startswith("\n"):
        body = body[1:]
    images = []
    for image in meta.get("thumbs") or []:
        item = {"src": image["src"], "alt": image.get("alt") or "", "caption": image.get("caption") or ""}
        if image.get("w") and image.get("h"):
            item["w"] = image["w"]
            item["h"] = image["h"]
        images.append(item)
    entry = blank_entry()
    entry.update(
        {
            "date": meta["date"],
            "title": meta["title"],
            "stream": meta["stream"],
            "subtitle": meta.get("subtitle") or "",
            "summary": meta.get("summary") or "",
            "category": meta.get("category") or "",
            "tags": meta.get("tags") or [],
            "topics": meta.get("topics") or [],
            "people": meta.get("people") or [],
            "images": images,
            "links": meta.get("links") or [],
            "body": body,
        }
    )
    for key in ("credit", "slug"):
        if meta.get(key):
            entry[key] = meta[key]
    for key in ("edited", "featured"):
        if meta.get(key):
            entry[key] = True
    entry["html"] = md_to_html(body)
    return entry


def content_path(root: Path, entry: dict) -> Path:
    folder = FOLDER_OF[entry["stream"]]
    if entry["stream"] == "meaning" and entry.get("slug"):
        return root / "content" / folder / f'{entry["date"]}-{entry["slug"]}.md'
    return root / "content" / folder / f'{entry["date"]}.md'


def write_content(root: Path, entries: list[dict]) -> None:
    for entry in entries:
        path = content_path(root, entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_front_matter(entry), encoding="utf-8")


def load_content(root: Path) -> list[dict]:
    entries = []
    base = root / "content"
    for stream in STREAMS:
        folder = base / stream["folder"]
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            entries.append(parse_front_matter(path.read_text(encoding="utf-8")))
    return entries


def parse_image_size(data: bytes) -> tuple[int, int] | None:
    import struct

    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X" and len(data) >= 30:
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height
        if chunk == b"VP8 " and len(data) >= 30:
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
            return width, height
        if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
            b0, b1, b2, b3 = data[21:25]
            width = 1 + (((b1 & 0x3F) << 8) | b0)
            height = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
            return width, height
    if len(data) >= 4 and data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", data[i + 5 : i + 9])
                return int(width), int(height)
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD9:
                i += 2
                continue
            if i + 4 > len(data):
                break
            seglen = struct.unpack(">H", data[i + 2 : i + 4])[0]
            if seglen < 2:
                break
            i += 2 + seglen
    return None


def probe_dimensions(entries: list[dict], cache_path: Path) -> None:
    cache: dict[str, list[int]] = {}
    missing: set[str] = set()
    if cache_path.exists():
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
            cache = loaded.get("sizes", loaded if isinstance(loaded, dict) and "sizes" not in loaded else {})
            # older caches stored sizes at the top level
            if "sizes" in loaded:
                cache = loaded["sizes"]
                missing = set(loaded.get("missing") or [])
            else:
                cache = {key: value for key, value in loaded.items() if isinstance(value, list)}
        except json.JSONDecodeError:
            cache = {}
    needed = []
    for entry in entries:
        for image in entry["images"]:
            src = image["src"]
            if src in missing:
                continue
            if src in cache and len(cache[src]) == 2:
                image["w"], image["h"] = cache[src]
            elif src not in needed:
                needed.append(src)

    def fetch(url: str) -> tuple[str, tuple[int, int] | None, int | None]:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "muli-ingest", "Range": "bytes=0-131071"},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                data = response.read(131072)
        except urllib.error.HTTPError as exc:
            return url, None, exc.code
        return url, parse_image_size(data), None

    if needed:
        import urllib.error

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(fetch, url) for url in needed]
            for future in as_completed(futures):
                try:
                    url, size, status = future.result()
                except Exception as exc:  # noqa: BLE001 — one CDN miss should not stop the site
                    print(f"probe failed: {exc}", file=sys.stderr)
                    continue
                if status == 404:
                    missing.add(url)
                    print(f"probe 404, dropping {url}", file=sys.stderr)
                    continue
                if size:
                    cache[url] = [size[0], size[1]]
                else:
                    print(f"probe no size: {url}", file=sys.stderr)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"sizes": cache, "missing": sorted(missing)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    for entry in entries:
        kept = []
        for image in entry["images"]:
            if image["src"] in missing:
                continue
            size = cache.get(image["src"])
            if size:
                image["w"], image["h"] = size
            kept.append(image)
        entry["images"] = kept


def load_topics(root: Path) -> list[dict]:
    path = root / "content" / "topics.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_catalog(root: Path, entries: list[dict], generated_at: str, topics: list[dict]) -> None:
    payload = {
        "generatedAt": generated_at,
        "site": "https://senlau.github.io/muli/",
        "counts": {
            stream["hash"]: sum(1 for entry in entries if entry["stream"] == stream["hash"])
            for stream in STREAMS
        },
        "topics": [{"slug": topic["slug"], "name": topic["name"]} for topic in topics],
        "entries": [
            {
                "date": entry["date"],
                "title": entry["title"],
                "stream": entry["stream"],
                "url": entry_path(entry),
                "subtitle": entry.get("subtitle") or "",
                "summary": entry.get("summary") or "",
                "category": entry.get("category") or "",
                "tags": entry.get("tags") or [],
                "topics": entry.get("topics") or [],
                "people": entry.get("people") or [],
                "edited": bool(entry.get("edited")),
                "images": [
                    {
                        "src": image["src"],
                        "alt": image.get("alt") or "",
                        "caption": image.get("caption") or "",
                        **({"w": image["w"], "h": image["h"]} if image.get("w") and image.get("h") else {}),
                    }
                    for image in entry["images"]
                ],
                "links": entry.get("links") or [],
                **({"slug": entry["slug"]} if entry.get("slug") else {}),
            }
            for entry in sorted(entries, key=lambda item: (item["stream"], item["date"], item.get("slug") or ""), reverse=False)
        ],
    }
    path = root / "data" / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish(root: Path, entries: list[dict], generated_at: str) -> None:
    if not entries:
        raise SystemExit("no entries to publish")
    for entry in entries:
        if not entry.get("html"):
            entry["html"] = md_to_html(entry.get("body") or "")
        for image in entry["images"]:
            if not str(image["src"]).startswith("https://"):
                raise SystemExit(f"refusing non-HTTPS image: {image['src']}")
    topics = load_topics(root)
    write_content(root, entries)
    write_catalog(root, entries, generated_at, topics)
    pages = render_site(entries, generated_at, topics)
    for stream in STREAMS:
        folder = root / stream["folder"]
        if folder.is_dir():
            for stale in folder.glob("*.html"):
                if f'{stream["folder"]}/{stale.name}' not in pages:
                    stale.unlink()
    for rel, html_text in pages.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html_text, encoding="utf-8")
    counts = {stream["hash"]: 0 for stream in STREAMS}
    images = 0
    for entry in entries:
        counts[entry["stream"]] += 1
        images += len(entry["images"])
    print(
        f"entries photographer={counts['photographer']} aesthetic={counts['aesthetic']} 28mm={counts['28mm']} "
        f"meaning={counts['meaning']} images={images} pages={len(pages)}"
    )


def self_test() -> None:
    sample = """
1. `/tmp/riobranco-dulce-jangadeiro.jpg`
   CDN: https://fastly.jsdelivr.net/gh/senlau/picx-images-hosting@master/muli/riobranco-dulce-jangadeiro.jpg
   图注：*Dulce Sudor Amargo*｜Piata 海滩
"""
    images = extract_images(sample)
    assert len(images) == 1, images
    assert "Piata" in images[0]["caption"]
    figure = """
<figure><img src="https://fastly.jsdelivr.net/gh/senlau/picx-images-hosting@master/muli/parke-dream-shadow-stride.jpg" alt="Stride">
<figcaption>*Dream/Life*｜办公人</figcaption></figure>
"""
    parsed = extract_images(figure)
    assert parsed[0]["alt"] == "Stride"
    assert "办公人" in parsed[0]["caption"]
    html_out = md_to_html("### 2026-10-27｜标题\n\n今天是**一句**。\n\n- 甲\n- 乙\n\n[Magnum](https://www.magnumphotos.com/)\n")
    assert "<h2>" not in html_out.split("</p>")[0] or "标题" not in html_out
    assert "标题" not in html_out
    assert "<strong>一句</strong>" in html_out
    assert "<li>甲</li>" in html_out
    assert "magnumphotos.com" in html_out
    entry = blank_entry()
    entry.update(
        {
            "date": "2026-10-27",
            "title": "示例（大师 · 测试）",
            "stream": "photographer",
            "subtitle": "一句足够长的副题，用来放在卡片上。",
            "summary": "摘要。",
            "category": "大师",
            "tags": ["大师", "测试"],
            "images": [
                {
                    "src": "https://fastly.jsdelivr.net/gh/senlau/picx-images-hosting@master/muli/parke-dream-shadow-stride.jpg",
                    "alt": "alt",
                    "caption": "*Dream/Life*",
                }
            ],
            "links": [{"label": "Magnum", "url": "https://www.magnumphotos.com/"}],
            "body": "### 2026-10-27｜示例\n\n正文。\n",
        }
    )
    text = dump_front_matter(entry)
    again = parse_front_matter(text)
    assert again["title"] == entry["title"]
    assert again["images"][0]["src"] == entry["images"][0]["src"]
    assert "正文" in again["body"]
    assert "edited" not in text and "topics" not in text

    lesson = blank_entry()
    lesson.update(
        {
            "date": "2026-10-28",
            "title": "剪影可读（Readable Silhouette）· 非惊喜",
            "stream": "aesthetic",
            "category": "非惊喜",
            "body": "## 剪影可读 · 非惊喜\n\n今早已推。细节可以死，外形必须活。\n\n## 跟锚点的关系\n\n见 Parke。\n\n"
            "## 可练一句\n\n先看外轮廓。\n\n喜欢 / 一般 / 不感兴趣，回一句就行。\n",
        }
    )
    edited = blank_entry()
    edited.update(
        {
            "date": "2026-10-27",
            "title": "不敢看陌生人眼睛的人",
            "stream": "meaning",
            "slug": "mannell",
            "topics": ["陌生人与肖像"],
            "credit": "图片：Portrait Per Day",
            "edited": True,
            "body": "先开口。\n\n## 可以借用的做法\n\n- 对照 [示例](#photographer-2026-10-27)。\n- [不存在](#aesthetic-1999-01-01)\n",
        }
    )
    edited = parse_front_matter(dump_front_matter(edited))
    assert edited["edited"] and edited["slug"] == "mannell" and edited["topics"] == ["陌生人与肖像"]
    entries = [finalize(entry), finalize(lesson), edited]

    raw_twin = dict(edited, edited=False, title="原稿", body="原稿正文。\n")
    assert upsert(entries, raw_twin)[2]["title"] == "不敢看陌生人眼睛的人"
    other_story = dict(raw_twin, slug="bryce")
    assert len(upsert(list(entries), other_story)) == 4
    snapshot = keep_edited(entries, [raw_twin])
    assert snapshot[0]["title"] == "不敢看陌生人眼睛的人"

    pages = render_site(entries, "2026-10-28T00:00:00+08:00", [{"slug": "portrait", "name": "陌生人与肖像", "note": ""}])
    home = pages["index.html"]
    for path in ("learn.html", "practice.html", "life.html", "archive.html",
                 "photographer/2026-10-27.html", "aesthetic/2026-10-28.html", "meaning/2026-10-27-mannell.html"):
        assert path in pages, path
    assert home.count("<h1") == 1
    assert '"photographer-2026-10-27":"photographer/2026-10-27.html"' in home
    assert '"meaning-2026-10-27-mannell":"meaning/2026-10-27-mannell.html"' in home
    assert "四条线" not in home and "Grok Bot 作品" in home
    for html_text in pages.values():
        assert html_text.count("觉非的 Grok Bot") == 1
        assert html_text.count("<h1") == 1
    article = pages["aesthetic/2026-10-28.html"]
    assert "<h1>剪影可读</h1>" in article and "Readable Silhouette" in article
    assert "风格对照" in article and "今日练习" in article
    for word in ("非惊喜", "跟锚点", "可练一句", "今早", "回一句就行"):
        assert word not in article, word
    story = pages["meaning/2026-10-27-mannell.html"]
    assert 'href="../photographer/2026-10-27.html">示例</a>' in story
    assert "<li>不存在</li>" in story
    assert "图片：Portrait Per Day" in story
    assert 'href="../archive.html#topic-portrait"' in story
    print("self-test ok")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest 目力 streams and rebuild the static site.")
    parser.add_argument("--json", type=Path, help="Canonical content.json snapshot (streams photographer/aesthetic/mm28).")
    parser.add_argument("--brief", type=Path, help="Vault or brief root with daily/, 28mm/, and the three rollup notes.")
    parser.add_argument("--from-content", action="store_true", help="Rebuild the site from content/*.md only.")
    parser.add_argument("--probe", action="store_true", help="Fetch CDN image dimensions for stable aspect ratios.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return

    root = args.root
    generated_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
    if args.from_content or (not args.json and not args.brief):
        entries = load_content(root)
    elif args.json:
        entries = load_json(args.json)
        if args.brief:
            enrich_from_brief(entries, args.brief)
        entries = keep_edited(load_content(root), entries)
    else:
        entries = load_content(root)
        for incoming in parse_brief(args.brief):
            entries = upsert(entries, incoming)

    if not entries:
        raise SystemExit("nothing to ingest; pass --json, --brief, or commit content/*.md and use --from-content")
    if args.probe:
        probe_dimensions(entries, root / "data" / "dimensions.json")
        for entry in entries:
            entry["html"] = md_to_html(entry.get("body") or "")
    publish(root, entries, generated_at)


if __name__ == "__main__":
    main()
