#!/usr/bin/env python3
"""
snapshot - screenshot a page with Playwright (free, local, no npm install needed).

  python3 snapshot.py <url> [-o out.png] [--width 1280] [--height 800]
                       [--full-page] [--text] [--wait-for "text"]

Uses the Playwright CLI (npx -y playwright@latest screenshot). Chromium is
already installed via: npx playwright install chromium

--text also dumps a readable markdown version (uses html2md.py next to this file).
Prints the output path and file size so the agent can then READ/SEE the file.
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
HTML2MD = os.path.join(HERE, "html2md.py")


def default_out(url: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in url)[:60].strip("-")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"shot-{slug or 'page'}-{stamp}.png"


def main() -> int:
    ap = argparse.ArgumentParser(description="screenshot a page (playwright CLI)")
    ap.add_argument("url")
    ap.add_argument("-o", "--out", help="png path (default shot-<url>-<time>.png)")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=800)
    ap.add_argument("--full-page", action="store_true")
    ap.add_argument("--wait-for", help="text to wait for before shooting")
    ap.add_argument("--text", action="store_true", help="also dump readable markdown")
    args = ap.parse_args()

    out = args.out or default_out(args.url)
    out_dir = os.path.dirname(os.path.abspath(out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    cmd = [
        "npx", "-y", "playwright", "screenshot",
        f"--viewport-size={args.width},{args.height}",
    ]
    if args.full_page:
        cmd.append("--full-page")
    if args.wait_for:
        cmd.extend(["--wait-for-timeout", "1500"])
    cmd.extend([args.url, out])

    def run(command: list) -> subprocess.CompletedProcess:
        return subprocess.run(command, capture_output=True, timeout=300)

    try:
        proc = run(cmd)
        # npx may fail to resolve the package; fall back to a global install
        if proc.returncode != 0 and shutil.which("playwright"):
            proc = run(["playwright", "screenshot", f"--viewport-size={args.width},{args.height}",
                        *(["--full-page"] if args.full_page else []), args.url, out])
    except FileNotFoundError:
        print("ERROR: npx not found. Install Node.js 18+.", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("ERROR: screenshot timed out (300s).", file=sys.stderr)
        return 2

    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        print(f"ERROR: playwright screenshot failed (exit {proc.returncode})\n{err[-1200:]}", file=sys.stderr)
        return 1

    if not os.path.isfile(out):
        print(f"ERROR: expected output file missing: {out}", file=sys.stderr)
        return 1

    size = os.path.getsize(out)
    print(f"screenshot: {out} ({size} bytes, {args.width}x{args.height}{', full-page' if args.full_page else ''})")

    if args.text:
        md = out.rsplit(".", 1)[0] + ".md"
        try:
            subprocess.run([sys.executable, HTML2MD, args.url, "-o", md], check=True, timeout=120)
            print(f"text dump:  {md}")
        except Exception as exc:  # noqa: BLE001
            print(f"text dump failed: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
