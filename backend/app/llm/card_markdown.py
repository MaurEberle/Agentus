"""A Hugging Face model card (README.md) as Markdown the app's viewer can show safely.

Cards mix Markdown with HTML (centred logos, badge rows, benchmark tables, <details>). The viewer
renders Markdown only and never raw HTML, so the HTML the cards use is turned into Markdown here:
images and links keep their target, tables become Markdown tables, headings and emphasis stay,
everything else keeps its text and loses the tag. Relative links and images point into the repo.
Code blocks and inline code stay untouched.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

HUB = "https://huggingface.co"

_FRONT_MATTER = re.compile(r"\A---[ \t]*\n.*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.S)
_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_DROPPED_BLOCK = re.compile(r"<(script|style|svg|iframe|noscript)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
_MD_LINK = re.compile(r"(!?)\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_ONLY_IMAGE = re.compile(r"!\[[^\[\]]*\]\([^)\s]+\)")
_INDENTED_IMAGE = re.compile(r"^[ \t]+!\[")
_DOUBLE_BOLD = re.compile(r"\*{4}([^*\n]+?)\*{4}")
_BLANK_RUNS = re.compile(r"\n{3,}")
_PLACEHOLDER = re.compile("(\\d+)")

# Tags that only carry layout; their text stays.
_TRANSPARENT = frozenset(
    {"span", "font", "u", "small", "big", "sup", "sub", "abbr", "mark", "picture", "source", "video", "audio",
     "thead", "tbody", "tfoot", "colgroup", "col", "caption", "nav", "header", "footer", "main", "article",
     "aside", "label", "kbd", "s", "strike", "del", "ins", "dl", "dt", "dd", "body", "html", "head", "meta"}
)
_BLOCK = frozenset({"p", "div", "section", "center", "details", "figure", "figcaption", "blockquote"})
_HEADINGS = {f"h{level}": level for level in range(1, 7)}
_EMPHASIS = {"strong": "**", "b": "**", "em": "*", "i": "*", "code": "`"}
_KNOWN = (
    _TRANSPARENT | _BLOCK | set(_HEADINGS) | set(_EMPHASIS)
    | {"img", "a", "br", "hr", "summary", "ul", "ol", "li", "table", "tr", "th", "td", "pre"}
)


def resolve_url(url: str, repo: str, *, image: bool) -> str | None:
    """Absolute https target for a card link or image, or None when it goes nowhere useful."""
    # Spaces and brackets would end the Markdown target early.
    value = (url or "").strip().replace(" ", "%20").replace("(", "%28").replace(")", "%29")
    lowered = value.lower()
    if not value or lowered.startswith(("#", "javascript:", "data:", "vbscript:", "file:")):
        return None
    if lowered.startswith(("https://", "http://")):
        return value
    if lowered.startswith("mailto:"):
        return None if image else value
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("/"):
        return HUB + value
    if re.match(r"^[a-z][a-z0-9+.-]*:", lowered):
        return None
    path = value[2:] if value.startswith("./") else value
    return f"{HUB}/{repo}/{'resolve' if image else 'blob'}/main/{path}"


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


class _CardHtml(HTMLParser):
    """HTML inside a card's Markdown, written back as Markdown. Unknown tags stay as text."""

    def __init__(self, repo: str) -> None:
        super().__init__(convert_charrefs=True)
        self.repo = repo
        self.out: list[str] = []
        # Open <a>: its target, and whether an image showed up inside (a badge: keep the image only).
        self.links: list[dict[str, object]] = []
        self.lists: list[dict[str, int | str]] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.pre = 0

    # -- writing -------------------------------------------------------------------------------
    def write(self, text: str) -> None:
        if self.cell is not None:
            self.cell.append(text)
        else:
            self.out.append(text)

    def block(self) -> None:
        if self.cell is not None:
            self.cell.append(" ")
        else:
            self.out.append("\n\n")

    # -- parser hooks --------------------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        values = {key.lower(): value or "" for key, value in attrs}
        if name not in _KNOWN:
            self.write(self.get_starttag_text() or "")
        elif name == "img":
            src = resolve_url(values.get("src", ""), self.repo, image=True)
            if src:
                alt = " ".join(values.get("alt", "").split()).replace("[", "(").replace("]", ")")
                self.write(f"![{alt}]({src})")
                if self.links:
                    self.links[-1]["image"] = True
        elif name == "a":
            href = resolve_url(values.get("href", ""), self.repo, image=False)
            self.links.append({"href": href, "start": len(self.cell if self.cell is not None else self.out), "image": False, "cell": self.cell is not None})
            if href:
                self.write("[")
        elif name == "br":
            self.write(" " if self.cell is not None else "\n")
        elif name == "hr":
            self.write("\n\n---\n\n")
        elif name in _BLOCK:
            self.block()
        elif name in _HEADINGS:
            self.block()
            self.write("#" * _HEADINGS[name] + " ")
        elif name == "summary":
            self.block()
            self.write("**")
        elif name in _EMPHASIS:
            self.write(_EMPHASIS[name])
        elif name == "pre":
            self.pre += 1
            self.write("\n\n```\n")
        elif name in ("ul", "ol"):
            self.lists.append({"kind": name, "count": 0})
            self.write("\n")
        elif name == "li":
            current = self.lists[-1] if self.lists else {"kind": "ul", "count": 0}
            current["count"] = int(current["count"]) + 1
            marker = f"{current['count']}. " if current["kind"] == "ol" else "- "
            self.write("\n" + "  " * max(0, len(self.lists) - 1) + marker)
        elif name == "table":
            self.table = []
        elif name == "tr" and self.table is not None:
            self.row = []
        elif name in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in _KNOWN:
            self.handle_starttag(tag, attrs)
            if tag.lower() not in {"img", "br", "hr", "col", "source", "meta"}:
                self.handle_endtag(tag)
        else:
            self.write(self.get_starttag_text() or "")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name not in _KNOWN:
            self.write(f"</{tag}>")
        elif name == "a":
            link = self.links.pop() if self.links else None
            if link and link["href"]:
                target = self.cell if link["cell"] and self.cell is not None else self.out
                if link["image"]:
                    # A badge or logo link: the image alone reads better than a link around it.
                    start = int(link["start"])  # type: ignore[arg-type]
                    if start < len(target) and target[start] == "[":
                        target.pop(start)
                else:
                    self.write(f"]({link['href']})")
        elif name in _BLOCK or name in _HEADINGS:
            self.block()
        elif name == "summary":
            self.write("**")
            self.block()
        elif name in _EMPHASIS:
            self.write(_EMPHASIS[name])
        elif name == "pre":
            self.pre = max(0, self.pre - 1)
            self.write("\n```\n\n")
        elif name in ("ul", "ol"):
            if self.lists:
                self.lists.pop()
            self.write("\n\n")
        elif name in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(_cell("".join(self.cell)))
            self.cell = None
        elif name == "tr" and self.row is not None and self.table is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif name == "table" and self.table is not None:
            rows, self.table, self.row, self.cell = self.table, None, None, None
            self.write(_table(rows))

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        else:
            self.out.append(data)

    def text(self) -> str:
        self.close()
        if self.table is not None:
            # An unclosed table still shows what it had.
            self.out.append(_table(self.table + ([self.row] if self.row else [])))
        return "".join(self.out)


def _table(rows: list[list[str]]) -> str:
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(padded[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in padded[1:]]
    return "\n\n" + "\n".join(lines) + "\n\n"


def _prose(text: str, repo: str) -> str:
    """Markdown outside code fences: HTML to Markdown, links resolved; inline code untouched."""
    kept: list[str] = []

    def protect(match: re.Match[str]) -> str:
        kept.append(match.group(0))
        return f"{len(kept) - 1}"

    text = _INLINE_CODE.sub(protect, text)
    text = _COMMENT.sub("", text)
    text = _DROPPED_BLOCK.sub("", text)
    text = _AUTOLINK.sub(lambda match: f"[{match.group(1)}]({match.group(1)})", text)
    if "<" in text or "&" in text:
        parser = _CardHtml(repo)
        parser.feed(text)
        text = parser.text()

    def link(match: re.Match[str]) -> str:
        image, label, url = match.group(1) == "!", match.group(2), match.group(3)
        if not image:
            label = _MD_LINK.sub(link, label)
            # A badge or logo link: the image alone, as with HTML links around images.
            if _ONLY_IMAGE.fullmatch(label.strip()):
                return label.strip()
        target = resolve_url(url, repo, image=image)
        if target is None:
            return "" if image else label
        return f"{'!' if image else ''}[{label}]({target})"

    text = _MD_LINK.sub(link, text)
    # <summary><b>…</b></summary> comes out bold twice.
    text = _DOUBLE_BOLD.sub(r"**\1**", text)
    return _PLACEHOLDER.sub(lambda match: kept[int(match.group(1))], text)


_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}/[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


def card_base_model(raw: str) -> str | None:
    """The first ``base_model`` of the card's YAML header (``a/b``, ``- a/b`` or ``["a/b"]``)."""
    text = raw.replace("\r\n", "\n").lstrip("﻿")
    header = _FRONT_MATTER.match(text)
    if not header:
        return None
    lines = header.group(0).split("\n")
    for index, line in enumerate(lines):
        found = re.match(r"^base_model:[ \t]*(.*)$", line)
        if not found:
            continue
        inline = found.group(1).strip()
        if inline:
            candidates = [part for part in re.split(r"[\[\],]", inline) if part.strip()]
        else:
            candidates = []
            for item in lines[index + 1 :]:
                listed = re.match(r"^[ \t]*-[ \t]*(.+)$", item)
                if not listed:
                    break
                candidates.append(listed.group(1))
        for candidate in candidates:
            value = candidate.split("#", 1)[0].strip().strip("'\"")
            if _REPO.fullmatch(value):
                return value
        return None
    return None


def card_markdown(raw: str, repo: str) -> str:
    """The card's text without its YAML header, ready for the viewer."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    text = _FRONT_MATTER.sub("", text, count=1)
    parts: list[str] = []
    prose: list[str] = []
    fence: str | None = None
    for line in text.split("\n"):
        found = _FENCE.match(line)
        if fence is None and found:
            parts.append(_prose("\n".join(prose), repo))
            prose = []
            fence = found.group(1)[0] * len(found.group(1))
            parts.append("\n" + line)
        elif fence is not None:
            parts.append("\n" + line)
            if found and found.group(1).startswith(fence):
                fence = None
                parts.append("\n")
        else:
            prose.append(line)
    if prose:
        parts.append(_prose("\n".join(prose), repo))
    out = "".join(parts)
    # Images that sat indented inside HTML blocks start their line; elsewhere indentation stays.
    out = "\n".join((line.strip() if _INDENTED_IMAGE.match(line) else line.rstrip()) for line in out.split("\n"))
    return _BLANK_RUNS.sub("\n\n", out).strip()
