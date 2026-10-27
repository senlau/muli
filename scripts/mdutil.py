"""Small Markdown subset used by 目力 lessons. No third-party renderer."""

from __future__ import annotations

import html
import re


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


def inline(text: str, external: bool = True) -> str:
    parts: list[str] = []
    pos = 0
    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
    for match in pattern.finditer(text):
        parts.append(format_plain(text[pos : match.start()]))
        label = format_plain(match.group(1))
        href = html.escape(match.group(2), quote=True)
        extra = ""
        if external:
            extra = ' target="_blank" rel="noopener noreferrer"'
            label = f'{label}<span class="sr">（新窗口）</span>'
        parts.append(f'<a href="{href}"{extra}>{label}</a>')
        pos = match.end()
    parts.append(format_plain(text[pos:]))
    return "".join(parts)


def md_to_html(md: str) -> str:
    """Render the lesson subset. The first heading is dropped; the page supplies the title."""
    lines = (md or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    i = 0
    skipped_title = False
    heading = {1: "h2", 2: "h2", 3: "h2", 4: "h3"}

    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if re.fullmatch(r"-{3,}", stripped):
            blocks.append("<hr>")
            i += 1
            continue
        match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if match:
            if not skipped_title:
                skipped_title = True
                i += 1
                continue
            tag = heading[len(match.group(1))]
            blocks.append(f"<{tag}>{inline(match.group(2).strip())}</{tag}>")
            i += 1
            continue
        if re.match(r"[-*]\s+", stripped):
            items: list[str] = []
            while i < len(lines) and re.match(r"\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i].strip()))
                i += 1
            lis = "".join(f"<li>{inline(item)}</li>" for item in items)
            blocks.append(f"<ul>{lis}</ul>")
            continue
        if re.match(r"\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i].strip()))
                i += 1
            lis = "".join(f"<li>{inline(item)}</li>" for item in items)
            blocks.append(f"<ol>{lis}</ol>")
            continue
        para = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or re.match(r"^(#{1,4}\s+|[-*]\s+|\d+\.\s+|-{3,}$)", nxt):
                break
            para.append(nxt)
            i += 1
        blocks.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(blocks)
