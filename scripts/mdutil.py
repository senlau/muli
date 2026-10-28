"""Small Markdown subset used by 目力 lessons. No third-party renderer."""

from __future__ import annotations

import html
import re
from typing import Callable

LINK = re.compile(r"\[([^\]]+)\]\(((?:https?://|#)[^)\s]+)\)")
IMAGE_LINE = re.compile(r'^!\[([^\]]*)\]\((\S+?)(?:\s+"[^"]*")?\)$')
LIST_ITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
BLOCK_START = re.compile(r"^(#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|!\[|```|~~~)")


def plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text or "")
    text = re.sub(r"[*`]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def format_plain(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def inline(text: str, external: bool = True, resolve: Callable[[str], str | None] | None = None) -> str:
    """Inline Markdown. `[label](#entry-id)` becomes a site link through `resolve`, or plain text if unknown."""
    parts: list[str] = []
    pos = 0
    for match in LINK.finditer(text or ""):
        parts.append(format_plain(text[pos : match.start()]))
        label = format_plain(match.group(1))
        target = match.group(2)
        if target.startswith("#"):
            href = resolve(target[1:]) if resolve else None
            parts.append(f'<a href="{html.escape(href, quote=True)}">{label}</a>' if href else label)
        else:
            extra = ""
            if external:
                extra = ' target="_blank" rel="noopener noreferrer"'
                label = f'{label}<span class="sr">（新窗口）</span>'
            parts.append(f'<a href="{html.escape(target, quote=True)}"{extra}>{label}</a>')
        pos = match.end()
    parts.append(format_plain((text or "")[pos:]))
    return "".join(parts).replace("\n", "<br>")


def is_cjk(char: str) -> bool:
    if not char:
        return False
    code = ord(char)
    return 0x2E80 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF or 0xFF00 <= code <= 0xFFEF or 0x3000 <= code <= 0x303F


def join_lines(lines: list[str]) -> str:
    """Join soft-wrapped lines: no space between CJK neighbours, a newline for Markdown hard breaks."""
    out = ""
    for index, line in enumerate(lines):
        text = line.strip()
        if index == 0:
            out = text
            continue
        if lines[index - 1].endswith("  "):
            out += "\n" + text
        elif out and (is_cjk(out[-1]) or is_cjk(text[:1])):
            out += text
        else:
            out += " " + text
    return out


def parse_blocks(md: str) -> list[dict]:
    """Split Markdown into heading / para / list / image / code / hr blocks."""
    lines = (md or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].strip().startswith(fence):
                buf.append(lines[j])
                j += 1
            blocks.append({"type": "code", "text": "\n".join(buf)})
            i = j + 1
            continue
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            blocks.append({"type": "hr"})
            i += 1
            continue
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", stripped)
        if match:
            blocks.append({"type": "heading", "level": len(match.group(1)), "text": match.group(2).strip()})
            i += 1
            continue
        match = IMAGE_LINE.match(stripped)
        if match:
            blocks.append({"type": "image", "alt": match.group(1), "src": match.group(2)})
            i += 1
            continue
        if LIST_ITEM.match(stripped):
            ordered = bool(re.match(r"^\d+[.)]\s+", stripped))
            marker = re.compile(r"^\s*\d+[.)]\s+" if ordered else r"^\s*[-*+]\s+")
            items: list[list[str]] = []
            while i < len(lines):
                current = lines[i]
                if marker.match(current):
                    items.append([marker.sub("", current)])
                    i += 1
                    continue
                if items and current.strip() and current[:1] in (" ", "\t") and not LIST_ITEM.match(current):
                    items[-1].append(current)
                    i += 1
                    continue
                break
            blocks.append({"type": "list", "ordered": ordered, "items": [join_lines(item) for item in items]})
            continue
        para = [raw]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            ns = nxt.strip()
            if not ns or BLOCK_START.match(ns) or re.fullmatch(r"-{3,}", ns):
                break
            para.append(nxt)
            i += 1
        blocks.append({"type": "para", "text": join_lines(para)})
    return blocks


def md_to_html(md: str) -> str:
    """Render the lesson subset. The first heading is dropped; the page supplies the title."""
    heading = {1: "h2", 2: "h2", 3: "h2", 4: "h3", 5: "h3", 6: "h3"}
    out: list[str] = []
    skipped_title = False
    for block in parse_blocks(md):
        kind = block["type"]
        if kind == "heading":
            if not skipped_title:
                skipped_title = True
                continue
            tag = heading[block["level"]]
            out.append(f"<{tag}>{inline(block['text'])}</{tag}>")
        elif kind == "para":
            out.append(f"<p>{inline(block['text'])}</p>")
        elif kind == "list":
            tag = "ol" if block["ordered"] else "ul"
            items = "".join(f"<li>{inline(item)}</li>" for item in block["items"])
            out.append(f"<{tag}>{items}</{tag}>")
        elif kind == "image":
            out.append(f'<p><img src="{html.escape(block["src"], quote=True)}" alt="{html.escape(block["alt"], quote=True)}"></p>')
        elif kind == "hr":
            out.append("<hr>")
    return "\n".join(out)
