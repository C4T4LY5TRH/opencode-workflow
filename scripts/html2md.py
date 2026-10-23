#!/usr/bin/env python3
"""
html2md - fetch a web page (or local html) and convert it to clean markdown.

Zero dependencies. Python stdlib only.

  python3 html2md.py <url|file> [-o out.md] [--keep-nav]

Drops: script, style, noscript, svg, iframe, form, nav, header, footer, aside.
Keeps: headings, paragraphs, lists, links, code, pre, tables, blockquote, hr.
Uses pandoc instead when it is on PATH (better tables), then falls back.
"""

import argparse
import gzip
import io
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from html.parser import HTMLParser

SKIP_TAGS = {
    "script", "style", "noscript", "svg", "iframe", "form", "nav",
    "header", "footer", "aside", "template", "button", "select", "option",
}
BLOCK_TAGS = {
    "p", "div", "section", "article", "main", "ul", "ol", "table", "tr",
    "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "br",
    "figure", "figcaption", "details", "summary", "dl", "dt", "dd",
}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


class Converter(HTMLParser):
    def __init__(self, keep_nav: bool = False):
        super().__init__(convert_charrefs=True)
        self.keep_nav = keep_nav
        self.out = []
        self.skip_depth = 0
        self.title = ""
        self.in_title = False
        self.list_stack = []
        self.item_counters = []
        self.in_pre = False
        self.pre_buffer = []
        self.in_code = False
        self.code_buffer = []
        self.href = None
        self.link_text = []
        self.in_table = False
        self.row = []
        self.cell = None
        self.cell_buffer = []
        self.skip_tags = set() if keep_nav else SKIP_TAGS

    # -- helpers
    def w(self, s: str):
        self.out.append(s)

    def newline(self, n=1):
        while self.out and self.out[-1].endswith("\n" * n):
            self.out.pop()
        self.w("\n" * n)

    # -- parser
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.skip_tags:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "title":
            self.in_title = True
            return
        if tag == "h1":
            self.newline(2); self.w("# ")
        elif tag == "h2":
            self.newline(2); self.w("## ")
        elif tag == "h3":
            self.newline(2); self.w("### ")
        elif tag == "h4":
            self.newline(2); self.w("#### ")
        elif tag == "h5":
            self.newline(2); self.w("##### ")
        elif tag == "h6":
            self.newline(2); self.w("###### ")
        elif tag == "p" or tag == "div" or tag == "section" or tag == "article":
            self.newline(2)
        elif tag == "br":
            self.w("\n")
        elif tag == "hr":
            self.newline(2); self.w("---"); self.newline(2)
        elif tag == "ul":
            self.newline(2); self.list_stack.append("ul"); self.item_counters.append(0)
        elif tag == "ol":
            self.newline(2); self.list_stack.append("ol"); self.item_counters.append(0)
        elif tag == "li":
            self.newline(1)
            if self.list_stack and self.list_stack[-1] == "ol":
                self.item_counters[-1] += 1
                self.w(f"{self.item_counters[-1]}. ")
            else:
                self.w("- ")
        elif tag == "pre":
            self.newline(2); self.in_pre = True; self.pre_buffer = []
        elif tag == "code" and not self.in_pre:
            self.in_code = True; self.code_buffer = []
        elif tag == "a":
            self.href = attrs.get("href")
            self.link_text = []
        elif tag == "blockquote":
            self.newline(2); self.w("> ")
        elif tag == "table":
            self.newline(2); self.in_table = True
        elif tag in ("td", "th"):
            self.cell = tag
            self.cell_buffer = []
        elif tag == "tr":
            self.row = []
        elif tag == "br" and self.in_pre:
            pass

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag == "title":
            self.in_title = False
            return
        if tag == "pre" and self.in_pre:
            code = "".join(self.pre_buffer).strip("\n")
            self.newline(2)
            self.w("```")
            self.w(code)
            self.w("```")
            self.newline(2)
            self.in_pre = False
        elif tag == "code" and self.in_code:
            text = "".join(self.code_buffer)
            self.w("`" + text.strip() + "`")
            self.in_code = False
        elif tag == "a":
            text = "".join(self.link_text).strip()
            if text:
                if self.href and not self.href.startswith(("javascript:", "#")):
                    self.w(f"[{text}]({self.href})")
                else:
                    self.w(text)
            self.href = None
            self.link_text = []
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop(); self.item_counters.pop()
            self.newline(2)
        elif tag == "blockquote":
            self.newline(2)
        elif tag == "table":
            self.in_table = False
            self.newline(2)
        elif tag in ("td", "th"):
            text = re.sub(r"\s+", " ", "".join(self.cell_buffer)).strip()
            self.row.append(text)
            self.cell = None
        elif tag == "tr":
            if self.in_table and self.row:
                if not hasattr(self, "_header_written"):
                    self.w("| " + " | ".join(self.row) + " |")
                    self.w("|" + "|".join(["---"] * len(self.row)) + "|")
                    self._header_written = True
                else:
                    self.w("| " + " | ".join(self.row) + " |")
            self.row = []

    def handle_data(self, data):
        if self.in_title:
            self.title += data.strip()
            return
        if self.skip_depth:
            return
        if self.in_pre:
            self.pre_buffer.append(data)
            return
        if self.in_code:
            self.code_buffer.append(data)
            return
        if self.href is not None:
            self.link_text.append(data)
            return
        if self.cell is not None:
            self.cell_buffer.append(data)
            return
        text = data.replace("\xa0", " ")
        if not text.strip():
            return
        if self.out and not self.out[-1].endswith((" ", "\n")):
            self.w(" ")
        self.w(re.sub(r"[ \t]+", " ", text))

    def markdown(self) -> str:
        text = "".join(self.out)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text.strip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="html -> clean markdown")
    ap.add_argument("target", help="url or local html file")
    ap.add_argument("-o", "--out", help="output file (default stdout)")
    ap.add_argument("--keep-nav", action="store_true", help="keep nav/header/footer")
    args = ap.parse_args()

    target = args.target
    if target.startswith("http://") or target.startswith("https://"):
        source = target
        try:
            html = fetch(target)
        except Exception as exc:  # noqa: BLE001
            print(f"FETCH FAILED: {exc}", file=sys.stderr)
            sys.exit(2)
    else:
        source = "file://" + os.path.abspath(target)
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            html = fh.read()

    converter = Converter(keep_nav=args.keep_nav)
    try:
        converter.feed(html)
    except Exception as exc:  # noqa: BLE001
        print(f"PARSE WARN: {exc}", file=sys.stderr)
    markdown = converter.markdown()

    if shutil.which("pandoc"):
        try:
            proc = subprocess.run(
                ["pandoc", "-f", "html", "-t", "gfm", "--wrap=none"],
                input=html.encode("utf-8"),
                capture_output=True,
                timeout=60,
            )
            if proc.returncode == 0 and len(proc.stdout.decode("utf-8", "replace").strip()) > 200:
                markdown = proc.stdout.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass

    header = f"<!-- source: {source} fetched: {__import__('datetime').date.today()} -->\n\n"
    out = header + markdown
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"wrote {args.out} ({len(out)} chars)")
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()
