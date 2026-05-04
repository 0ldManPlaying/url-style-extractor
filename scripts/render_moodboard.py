"""Render a markdown moodboard from extract.py output.

Usage:
    python scripts/render_moodboard.py <styles.json> [output.md]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def hex_swatch_html(hex_value: str) -> str:
    color = hex_value.split(" ")[0] if hex_value.startswith("#") else "#cccccc"
    return (
        f'<span style="display:inline-block;width:24px;height:24px;'
        f'background:{color};border:1px solid #ccc;border-radius:4px;'
        f'vertical-align:middle"></span>'
    )


def render(json_path: Path, out_path: Path | None = None) -> Path:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    out_path = out_path or json_path.parent / "moodboard.md"

    md: list[str] = []
    md.append(f"# Moodboard — {data['title']}")
    md.append("")
    md.append(f"**Source:** <{data['url']}>")
    md.append("")
    md.append("![Above the fold](screenshot-fold.png)")
    md.append("")

    md.append("## Color palette — foreground (text, icons, borders)")
    md.append("")
    md.append("| Swatch | Hex | RGB | Weight |")
    md.append("|---|---|---|---|")
    for c in data["colors"]:
        md.append(f"| {hex_swatch_html(c['hex'])} | `{c['hex']}` | `{c['rgb']}` | {c['weight']:.0f} |")
    md.append("")

    md.append("## Color palette — backgrounds (surfaces, fills)")
    md.append("")
    md.append("| Swatch | Hex | RGB | Weight |")
    md.append("|---|---|---|---|")
    for c in data["backgrounds"]:
        md.append(f"| {hex_swatch_html(c['hex'])} | `{c['hex']}` | `{c['rgb']}` | {c['weight']:.0f} |")
    md.append("")

    md.append("## Typography")
    md.append("")
    if data["googleFonts"]:
        md.append("**Google Fonts loaded:**")
        md.append("")
        for f in data["googleFonts"]:
            md.append(f"- <{f}>")
        md.append("")

    md.append("**Top font-families (ranked by usage area):**")
    md.append("")
    for f in data["fonts"]:
        md.append(f"- `{f['value']}` — weight {f['weight']:.0f}")
    md.append("")

    md.append("### Type scale")
    md.append("")
    md.append("| Element | Family | Size | Weight | Line-height | Letter-spacing | Color |")
    md.append("|---|---|---|---|---|---|---|")
    for tag, s in data["samples"].items():
        if not s:
            continue
        md.append(
            f"| `{tag}` | {s['fontFamily']} | {s['fontSize']} | {s['fontWeight']} | "
            f"{s['lineHeight']} | {s.get('letterSpacing', '—')} | `{s['color']}` |"
        )
    md.append("")

    if data["fontFaces"]:
        md.append("### Same-origin @font-face declarations")
        md.append("")
        md.append("```css")
        for face in data["fontFaces"]:
            md.append(face)
        md.append("```")
        md.append("")

    md.append("## Border radii")
    md.append("")
    for r in data["radii"]:
        md.append(f"- `{r['value']}` — used {r['weight']:.0f}×")
    md.append("")

    md.append("## Shadows")
    md.append("")
    for s in data["shadows"]:
        md.append(f"- `{s['value']}`")
    md.append("")

    md.append("## Spacing (top values across visible elements)")
    md.append("")
    for s in data["spacing"]:
        md.append(f"- `{s['value']}`")
    md.append("")

    if data["cssVars"]:
        md.append("## CSS custom properties (design tokens on :root)")
        md.append("")
        md.append("```css")
        md.append(":root {")
        for name, val in data["cssVars"].items():
            md.append(f"  {name}: {val};")
        md.append("}")
        md.append("```")
        md.append("")

    md.append("## Full-page screenshot")
    md.append("")
    md.append("![Full page](screenshot-full.png)")
    md.append("")

    out_path.write_text("\n".join(md), encoding="utf-8")
    return out_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python render_moodboard.py <styles.json> [output.md]", file=sys.stderr)
        sys.exit(1)
    json_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    result = render(json_path, out_path)
    print(f"Moodboard: {result}")


if __name__ == "__main__":
    main()
