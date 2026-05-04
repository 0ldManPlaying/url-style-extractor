"""Generate a Claude Code Skill / design guide from extracted styles.

Reads a styles.json produced by extract.py and emits a markdown file with
Skill-style frontmatter plus design tokens, type scale, and "how to apply"
guidance — drop it under `.claude/skills/<name>/SKILL.md` and Claude will
build UIs in the source site's visual style.

Usage:
    python scripts/generate_styleguide.py <styles.json> [output.md]

The generator is deterministic: no API calls, no LLM. It uses a small set
of heuristics to map raw extraction data onto design roles (background,
surface, foreground, muted, accent), so the same input always yields the
same output.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


# ---------- color math ----------

_RGB_RE = re.compile(r"rgba?\(([^)]+)\)")


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#").split(" ")[0]
    if len(h) != 6:
        return (0, 0, 0)
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    rf, gf, bf = r / 255, g / 255, b / 255
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    l = (mx + mn) / 2
    if mx == mn:
        return (0.0, 0.0, l * 100)
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == rf:
        h = ((gf - bf) / d + (6 if gf < bf else 0)) / 6
    elif mx == gf:
        h = ((bf - rf) / d + 2) / 6
    else:
        h = ((rf - gf) / d + 4) / 6
    return (h * 360, s * 100, l * 100)


def luminance(hex_str: str) -> float:
    """Perceptual brightness 0-255."""
    r, g, b = hex_to_rgb(hex_str)
    return 0.299 * r + 0.587 * g + 0.114 * b


def saturation(hex_str: str) -> float:
    r, g, b = hex_to_rgb(hex_str)
    return rgb_to_hsl(r, g, b)[1]


def is_chromatic(hex_str: str, sat_threshold: float = 25) -> bool:
    """True if the color carries a real hue (not gray/white/black)."""
    r, g, b = hex_to_rgb(hex_str)
    _, s, l = rgb_to_hsl(r, g, b)
    return s > sat_threshold and 5 < l < 95


def clean_hex(hex_with_alpha: str) -> str:
    return hex_with_alpha.split(" ")[0]


# ---------- role assignment ----------

def pick_roles(data: dict) -> dict[str, str]:
    """Map weighted color rankings onto semantic roles."""
    bgs = [clean_hex(c["hex"]) for c in data.get("backgrounds", [])]
    fgs = [clean_hex(c["hex"]) for c in data.get("colors", [])]

    bg_0 = bgs[0] if bgs else "#ffffff"
    bg_1 = next((b for b in bgs[1:] if b != bg_0), bg_0)
    bg_2 = next((b for b in bgs[2:] if b not in {bg_0, bg_1}), bg_1)

    fg_0 = fgs[0] if fgs else "#000000"
    # Muted text = the next foreground whose luminance differs meaningfully
    # from fg_0. Skips near-duplicates like #ffffff vs #fafafa.
    fg_1 = fg_0
    for f in fgs[1:]:
        if abs(luminance(f) - luminance(fg_0)) > 10:
            fg_1 = f
            break

    # Accent = the most saturated chromatic color across top 8 of each list
    candidates = []
    for c in (data.get("colors", []) + data.get("backgrounds", []))[:16]:
        h = clean_hex(c["hex"])
        if is_chromatic(h):
            candidates.append((h, saturation(h), c["weight"]))
    # Sort by saturation primarily, weight as tie-breaker
    candidates.sort(key=lambda x: (-x[1], -x[2]))
    accent = candidates[0][0] if candidates else fg_0
    accent_light = next(
        (h for h, _, _ in candidates[1:] if abs(luminance(h) - luminance(accent)) > 30),
        accent,
    )

    return {
        "bg_0": bg_0,
        "bg_1": bg_1,
        "bg_2": bg_2,
        "fg_0": fg_0,
        "fg_1": fg_1,
        "accent": accent,
        "accent_light": accent_light,
    }


# ---------- font detection ----------

_FONT_QUOTE_RE = re.compile(r'^["\']|["\']$')


def primary_font(family_str: str) -> str:
    first = family_str.split(",")[0].strip()
    return _FONT_QUOTE_RE.sub("", _FONT_QUOTE_RE.sub("", first))


def detect_fonts(data: dict) -> dict[str, str]:
    samples = data.get("samples", {}) or {}
    fonts_ranked = [f["value"] for f in data.get("fonts", [])]

    h1_family = primary_font(samples.get("h1", {}).get("fontFamily", "")) if samples.get("h1") else ""
    body_family = primary_font(samples.get("body", {}).get("fontFamily", "")) if samples.get("body") else ""
    button_family = primary_font(samples.get("button", {}).get("fontFamily", "")) if samples.get("button") else ""

    # Prefer pure monospace ("mono" without "semi") since "Semi Mono" is a
    # display face used for headings on some sites (e.g. AWS Diatype Rounded
    # Semi Mono on kiro.dev), not the code/inline mono.
    mono = ""
    for f in fonts_ranked:
        low = f.lower()
        if ("mono" in low and "semi" not in low) or "courier" in low or "consolas" in low or "menlo" in low:
            mono = primary_font(f)
            break
    if not mono:
        # Fallback: any font with "mono" if no pure-mono was found
        for f in fonts_ranked:
            if "mono" in f.lower():
                mono = primary_font(f)
                break

    return {
        "heading": h1_family or body_family or "system-ui",
        "body": body_family or "system-ui",
        "button": button_family or body_family or "system-ui",
        "mono": mono or "ui-monospace",
    }


# ---------- radius and spacing analysis ----------

_PX_RE = re.compile(r"(\d+(?:\.\d+)?)px")


def parse_first_px(value: str) -> float | None:
    m = _PX_RE.search(value)
    return float(m.group(1)) if m else None


def analyze_radii(data: dict) -> dict[str, list[str]]:
    radii = [r["value"] for r in data.get("radii", [])]
    pills = [r for r in radii if any(parse_first_px(p) and parse_first_px(p) >= 100 for p in r.split())]
    tight = []
    medium = []
    large = []
    for r in radii:
        first = parse_first_px(r)
        if first is None:
            continue
        if first < 100 and first <= 6:
            tight.append(r)
        elif first < 100 and first <= 20:
            medium.append(r)
        elif first < 100:
            large.append(r)
    return {"pill": pills, "tight": tight, "medium": medium, "large": large}


# ---------- markdown rendering ----------

def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s or "site"


def render(data: dict) -> str:
    url = data.get("url", "")
    title = data.get("title", "") or url
    domain = urlparse(url).netloc.replace("www.", "") or "site"
    slug = slugify(domain) + "-style"

    roles = pick_roles(data)
    fonts = detect_fonts(data)
    radii = analyze_radii(data)
    samples = data.get("samples", {}) or {}

    is_dark = luminance(roles["bg_0"]) < 80
    theme_label = "dark" if is_dark else "light"

    accent_hsl = rgb_to_hsl(*hex_to_rgb(roles["accent"]))
    accent_descriptor = f"vibrant" if accent_hsl[1] > 70 else "muted"

    has_pills = bool(radii["pill"])
    tight_first = sorted({parse_first_px(r) for r in radii["tight"] if parse_first_px(r)})
    tight_descriptor = f"{int(tight_first[0])}px" if tight_first else "no tight radius detected"

    google_fonts = data.get("googleFonts", []) or []

    out: list[str] = []
    out.append("---")
    out.append(f"name: {slug}")
    out.append(
        f"description: Build UIs in the visual style of {title}. "
        f"{theme_label.capitalize()} theme with {accent_descriptor} accent {roles['accent']}, "
        f"{tight_descriptor} tight radius for inputs/cards"
        + (", pill-shaped (9999px) buttons" if has_pills else "")
        + f", primary face {fonts['heading']}. Use this skill when the user asks for "
        f"UIs that should match {domain} or asks for the same look and feel."
    )
    out.append("---")
    out.append("")
    out.append(f"# {title} — design language")
    out.append("")
    out.append(
        f"Reverse-engineered from <{url}> on {date.today().isoformat()} "
        f"using [URL Style Extractor](https://github.com/0ldManPlaying/url-style-extractor)."
    )
    out.append("")

    # Theme
    out.append("## Theme")
    out.append("")
    out.append(
        f"**{theme_label.capitalize()} theme** with {accent_descriptor} accent. "
        f"Primary canvas `{roles['bg_0']}`, primary text `{roles['fg_0']}`, "
        f"signature accent `{roles['accent']}`."
    )
    out.append("")

    # Color tokens
    out.append("## Color tokens")
    out.append("")
    out.append("```css")
    out.append(":root {")
    out.append(f"  --bg-0: {roles['bg_0']};        /* primary canvas */")
    out.append(f"  --bg-1: {roles['bg_1']};        /* elevated surface */")
    out.append(f"  --bg-2: {roles['bg_2']};        /* card / border */")
    out.append(f"  --fg-0: {roles['fg_0']};        /* primary text */")
    out.append(f"  --fg-1: {roles['fg_1']};        /* muted text */")
    out.append(f"  --accent: {roles['accent']};       /* primary accent — buttons, focus, links */")
    out.append(f"  --accent-light: {roles['accent_light']}; /* lighter accent — icons, hover */")
    out.append("}")
    out.append("```")
    out.append("")

    # Typography
    out.append("## Typography")
    out.append("")
    out.append(f"- **Heading face:** `{fonts['heading']}`")
    out.append(f"- **Body face:** `{fonts['body']}`")
    out.append(f"- **Button face:** `{fonts['button']}`")
    out.append(f"- **Mono face:** `{fonts['mono']}`")
    if google_fonts:
        out.append("")
        out.append("**Source page loads these Google Fonts:**")
        for f in google_fonts:
            out.append(f"- <{f}>")
    out.append("")
    out.append("**Type scale:**")
    out.append("")
    out.append("| Element | Size | Weight | Line-height | Letter-spacing |")
    out.append("|---|---|---|---|---|")
    for tag in ["h1", "h2", "h3", "body", "p", "button", "a"]:
        s = samples.get(tag)
        if not s:
            continue
        out.append(
            f"| `{tag}` | {s['fontSize']} | {s['fontWeight']} | "
            f"{s['lineHeight']} | {s.get('letterSpacing', '—')} |"
        )
    out.append("")

    # Geometry
    out.append("## Geometry")
    out.append("")
    if tight_first:
        out.append(f"- **Tight radius** for inputs, swatches, code blocks: `{int(tight_first[0])}px`")
    if radii["medium"]:
        out.append(f"- **Medium radius** for cards: `{radii['medium'][0]}`")
    if radii["large"]:
        out.append(f"- **Large radius** for hero / feature cards: `{radii['large'][0]}`")
    if has_pills:
        out.append("- **Pill (`9999px`)** for all buttons — used heavily on the source page")
    spacing = [s["value"] for s in data.get("spacing", [])][:6]
    if spacing:
        out.append("")
        out.append("**Common spacing values (top of frequency distribution):**")
        for s in spacing:
            out.append(f"- `{s}`")
    shadows = data.get("shadows", []) or []
    if shadows:
        out.append("")
        out.append("**Shadow tokens:**")
        out.append("```css")
        for s in shadows[:3]:
            out.append(s["value"] + ";")
        out.append("```")
    out.append("")

    # Application rules
    out.append("## How to apply this style")
    out.append("")
    out.append(f"1. Use `--bg-0` ({roles['bg_0']}) for the page canvas, `--bg-1` for elevated surfaces (cards, sidebars, modals), and `--bg-2` for card borders / dividers.")
    out.append(f"2. Body text in `--fg-0` ({roles['fg_0']}), secondary / muted text in `--fg-1` ({roles['fg_1']}). Maintain WCAG AA contrast against the bg.")
    out.append(f"3. Headings use `{fonts['heading']}` with the type scale above. Body uses `{fonts['body']}`.")
    out.append(
        f"4. Primary actions are buttons styled in `--accent` ({roles['accent']}) "
        + ("as 9999px pills" if has_pills else "")
        + f". Hover state shifts to `--accent-light` ({roles['accent_light']})."
    )
    out.append(f"5. Icons, links, and decorative accents use `--accent-light` ({roles['accent_light']}).")
    if tight_first:
        out.append(f"6. Inputs and cards use `{int(tight_first[0])}px` border-radius — consistent and tight, not soft.")
    out.append(f"7. Theme baseline is **{theme_label}** — do not invert without an explicit reason; users came for this aesthetic.")
    out.append("")

    # Source data
    out.append("## Source extraction")
    out.append("")
    out.append(f"- URL: <{url}>")
    out.append(f"- Extracted: {date.today().isoformat()}")
    out.append(f"- Tool: [URL Style Extractor](https://github.com/0ldManPlaying/url-style-extractor)")
    out.append("")

    return "\n".join(out)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python generate_styleguide.py <styles.json> [output.md]", file=sys.stderr)
        sys.exit(1)
    json_path = Path(sys.argv[1])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    md = render(data)

    if len(sys.argv) > 2:
        out_path = Path(sys.argv[2])
    else:
        out_path = json_path.parent / "styleguide.md"

    out_path.write_text(md, encoding="utf-8")
    print(f"Style guide: {out_path}")


if __name__ == "__main__":
    main()
