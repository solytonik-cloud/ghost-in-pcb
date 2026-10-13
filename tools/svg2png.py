"""Обрезает SVG схемы KiCad до области (мм) и рендерит в PNG через headless Edge.

    python svg2png.py in.svg out.png x0 y0 x1 y1 [ширина_px]
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def render(svg_path, png_path, x0, y0, x1, y1, width_px=2400):
    svg = Path(svg_path).read_text(encoding="utf-8")
    w, h = x1 - x0, y1 - y0
    height_px = round(width_px * h / w)
    svg = re.sub(r'width="[^"]+" height="[^"]+"', f'width="{width_px}" height="{height_px}"', svg, count=1)
    svg = re.sub(r'viewBox="[^"]+"', f'viewBox="{x0} {y0} {w} {h}"', svg, count=1)
    html = (f'<html><body style="margin:0;background:#fff">{svg[svg.find("<svg"):]}</body></html>')
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "page.html"
        page.write_text(html, encoding="utf-8")
        out = Path(png_path).resolve()
        subprocess.run([EDGE, "--headless", "--disable-gpu", "--hide-scrollbars",
                        f"--screenshot={out}", f"--window-size={width_px},{height_px}",
                        page.as_uri()], check=True, capture_output=True, timeout=60)
    return out


if __name__ == "__main__":
    a = sys.argv
    render(a[1], a[2], *map(float, a[3:7]), *(int(x) for x in a[7:8]))
    print("OK", a[2])
