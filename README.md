# URL Style Extractor

A Claude Code Skill that extracts the visual design language from any live website URL and produces a markdown moodboard — colors, fonts, type scale, spacing, shadows, design tokens, and screenshots.

The moodboard is intended as input for building a new design system, follow-up Skill, redesign brief, or style guide.

## What it does

Given a URL, it:

1. Launches headless Chromium (Playwright), loads the page at 1440×900.
2. Walks every visible element and weighs `color`, `background-color`, `font-family`, `border-radius`, `box-shadow`, `padding/margin/gap` by bounding-box area.
3. Samples computed styles for `h1`–`h6`, `body`, `p`, `button`, `a` to capture the type scale.
4. Reads CSS custom properties from `:root`.
5. Detects Google Fonts via `<link>` tags and same-origin `@font-face` rules.
6. Captures above-the-fold and full-page screenshots.
7. Emits `styles.json`, then renders it to `moodboard.md` with hex swatches and a tokens block.

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

```bash
# 1. extract
python scripts/extract.py https://stripe.com

# 2. render moodboard
python scripts/render_moodboard.py outputs/stripe.com/styles.json
```

Outputs land in `outputs/<domain>/`:

- `styles.json` — raw extracted tokens
- `moodboard.md` — human-readable moodboard
- `screenshot-fold.png` — above-the-fold capture
- `screenshot-full.png` — full-page capture

## Using as a Claude Code Skill

This repo *is* a skill. Drop it into your `.claude/skills/` directory (or install it as a plugin) and Claude will trigger it automatically when you give it a URL and ask for styles, a moodboard, or design tokens.

The trigger phrases live in [SKILL.md](SKILL.md).

## Limits

- Cross-origin stylesheets may not expose their rules to the page (CORS), so `@font-face` data can be incomplete.
- Bot-detection (Cloudflare etc.) will block headless Chromium on some sites.
- Authenticated/private pages aren't supported out of the box.
- Color weighting is by element area — useful for finding dominant colors, but a small accent used in many places (e.g. a brand-colored icon) may rank lower than a large neutral background.

## License

MIT
