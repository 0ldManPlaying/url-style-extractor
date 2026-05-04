---
name: url-style-extractor
description: Extract a visual style moodboard from any live website URL. Use this when the user provides a URL and asks to extract styles, build a moodboard, generate a stylesheet, analyze a site's design language, capture design tokens, scrape colors and fonts, or reverse-engineer a UI. Outputs a markdown moodboard with a hex color palette, font families and Google Fonts links, type scale (h1-h6, body, button), spacing, border radii, shadows, CSS custom properties, and screenshots.
---

# URL Style Extractor

This skill extracts the visual design language from a live website and produces a markdown moodboard. The moodboard is meant as input for a new design system, a follow-up Skill, a style guide, or a redesign brief.

## When to use

Trigger when the user gives a URL and asks anything like:

- "extract the style from <url>"
- "build a moodboard from <url>"
- "what fonts and colors does <url> use?"
- "give me the design tokens of <url>"
- "scrape the styles from this site"

## How to use

1. **Confirm the URL** with the user if ambiguous (missing protocol, multiple URLs, etc.).

2. **Run the extractor** — it launches headless Chromium, navigates, and dumps computed styles + screenshots:

   ```bash
   python scripts/extract.py <url>
   ```

   Output: `outputs/<domain>/styles.json`, `screenshot-fold.png`, `screenshot-full.png`.

3. **Render the moodboard** — turns the JSON into a human-readable markdown file:

   ```bash
   python scripts/render_moodboard.py outputs/<domain>/styles.json
   ```

   Output: `outputs/<domain>/moodboard.md`.

4. **Generate the style guide** — turns the JSON into a Skill-format markdown the user can drop into `.claude/skills/`:

   ```bash
   python scripts/generate_styleguide.py outputs/<domain>/styles.json
   ```

   Output: `outputs/<domain>/styleguide.md` with frontmatter (name, description), color tokens mapped to roles (`--bg-0`, `--fg-0`, `--accent`, etc.), type scale, geometry rules, and "how to apply this style" guidance.

5. **Show the result** to the user. The `styleguide.md` is usually what they want — it's a ready-to-use skill that captures the source site's visual DNA. Offer the moodboard as well for human review.

## Setup (first run only)

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## What gets extracted

- **Colors** (foreground and background separately) ranked by visual area, converted to hex.
- **Font families** ranked by usage area, plus `<link>` tags pointing at fonts.googleapis.com and any same-origin `@font-face` rules.
- **Type scale** — computed `font-family`, `font-size`, `font-weight`, `line-height`, `letter-spacing`, `color` for `h1`-`h6`, `body`, `p`, `button`, `a`.
- **Spacing, border radii, shadows** ranked by frequency across visible elements.
- **CSS custom properties** — every `--*` defined on `:root`.
- **Screenshots** — above-the-fold (1440×900) and full-page.

## Notes and limits

- Cross-origin stylesheets may not expose their rules due to CORS — `@font-face` data may be incomplete. Google Fonts is still detected via `<link>` tags.
- Some sites block headless browsers (Cloudflare, bot detection). If a site fails to load, try editing `extract.py` to set a desktop user-agent on the context.
- Authenticated/private pages won't work without explicit cookies/login.
- The color ranking weights by element bounding-box area, so dominant colors (large hero backgrounds, body text) bubble to the top — not just the most-used CSS values.
