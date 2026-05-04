"""Extract visual style tokens from a live URL using headless Chromium.

Usage:
    python scripts/extract.py <url> [output_dir]

Writes <output_dir>/styles.json plus screenshots. Default output_dir is
outputs/<domain>.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


JS_EXTRACT = r"""
() => {
  const sample = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    return {
      fontFamily: cs.fontFamily,
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      lineHeight: cs.lineHeight,
      letterSpacing: cs.letterSpacing,
      color: cs.color,
      textTransform: cs.textTransform,
    };
  };

  const colorCounts = {};
  const bgCounts = {};
  const fontCounts = {};
  const radiusCounts = {};
  const shadowCounts = {};
  const spacingCounts = {};

  const bump = (obj, key, weight) => {
    if (!key) return;
    obj[key] = (obj[key] || 0) + weight;
  };

  for (const el of document.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    const area = r.width * r.height;
    const cs = getComputedStyle(el);

    if (cs.color && cs.color !== 'rgba(0, 0, 0, 0)') bump(colorCounts, cs.color, area);
    if (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)') bump(bgCounts, cs.backgroundColor, area);
    if (cs.fontFamily) bump(fontCounts, cs.fontFamily, area);
    if (cs.borderRadius && cs.borderRadius !== '0px') bump(radiusCounts, cs.borderRadius, 1);
    if (cs.boxShadow && cs.boxShadow !== 'none') bump(shadowCounts, cs.boxShadow, 1);
    for (const prop of ['padding', 'margin', 'gap']) {
      const val = cs[prop];
      if (val && val !== '0px' && val !== 'normal') bump(spacingCounts, prop + ': ' + val, 1);
    }
  }

  const fontFaces = [];
  for (const sheet of document.styleSheets) {
    try {
      for (const rule of sheet.cssRules || []) {
        if (rule.constructor && rule.constructor.name === 'CSSFontFaceRule') {
          fontFaces.push(rule.cssText);
        }
      }
    } catch (e) { /* CORS-blocked stylesheet */ }
  }

  const googleFonts = Array.from(
    document.querySelectorAll('link[href*="fonts.googleapis.com"], link[href*="fonts.gstatic.com"]')
  ).map(l => l.href);

  const cssVars = {};
  const rootStyle = getComputedStyle(document.documentElement);
  for (let i = 0; i < rootStyle.length; i++) {
    const name = rootStyle[i];
    if (name.startsWith('--')) cssVars[name] = rootStyle.getPropertyValue(name).trim();
  }

  return {
    title: document.title,
    samples: {
      h1: sample('h1'),
      h2: sample('h2'),
      h3: sample('h3'),
      h4: sample('h4'),
      h5: sample('h5'),
      h6: sample('h6'),
      body: sample('body'),
      p: sample('p'),
      button: sample('button'),
      a: sample('a'),
    },
    colorCounts, bgCounts, fontCounts, radiusCounts, shadowCounts, spacingCounts,
    fontFaces, googleFonts, cssVars,
  };
}
"""


_RGB_RE = re.compile(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)")


def rgb_to_hex(rgb_str: str) -> str:
    m = _RGB_RE.match(rgb_str.strip())
    if not m:
        return rgb_str
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    a = float(m.group(4)) if m.group(4) else 1.0
    hex_part = f"#{r:02x}{g:02x}{b:02x}"
    if a < 1.0:
        return f"{hex_part} (alpha {a:.2f})"
    return hex_part


def top_n(counts: dict, n: int) -> list[dict]:
    items = sorted(counts.items(), key=lambda x: -x[1])[:n]
    return [{"value": k, "weight": round(v, 2)} for k, v in items]


async def extract(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=60_000)
        except Exception:
            await page.goto(url, wait_until="load", timeout=60_000)

        await page.screenshot(path=str(out_dir / "screenshot-fold.png"), full_page=False)
        await page.screenshot(path=str(out_dir / "screenshot-full.png"), full_page=True)

        data = await page.evaluate(JS_EXTRACT)
        await browser.close()

    result = {
        "url": url,
        "title": data["title"],
        "samples": data["samples"],
        "colors": [
            {"rgb": c["value"], "hex": rgb_to_hex(c["value"]), "weight": c["weight"]}
            for c in top_n(data["colorCounts"], 12)
        ],
        "backgrounds": [
            {"rgb": c["value"], "hex": rgb_to_hex(c["value"]), "weight": c["weight"]}
            for c in top_n(data["bgCounts"], 12)
        ],
        "fonts": top_n(data["fontCounts"], 8),
        "radii": top_n(data["radiusCounts"], 8),
        "shadows": top_n(data["shadowCounts"], 6),
        "spacing": top_n(data["spacingCounts"], 12),
        "fontFaces": data["fontFaces"][:20],
        "googleFonts": data["googleFonts"],
        "cssVars": data["cssVars"],
    }

    json_path = out_dir / "styles.json"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return json_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python extract.py <url> [output_dir]", file=sys.stderr)
        sys.exit(1)
    url = sys.argv[1]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if len(sys.argv) > 2:
        out = Path(sys.argv[2])
    else:
        domain = urlparse(url).netloc.replace("www.", "") or "site"
        out = Path("outputs") / domain

    json_path = asyncio.run(extract(url, out))
    print(f"Extracted to: {json_path}")
    print(f"Screenshots:  {out / 'screenshot-fold.png'}, {out / 'screenshot-full.png'}")


if __name__ == "__main__":
    main()
