"""Streamlit UI for the URL Style Extractor."""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

ROOT = Path(__file__).parent
OUTPUTS_DIR = ROOT / "outputs"


@st.cache_resource(show_spinner="First-run setup: installing Chromium for Playwright (one-time, ~150 MB)…")
def _ensure_chromium() -> bool:
    """Install Playwright Chromium on cloud-deploy targets where it's missing.

    Local Windows users get Chromium via start.bat; Streamlit Community Cloud
    and similar Linux hosts won't have it pre-installed. Cached as a resource
    so the install only runs once per app cold-start.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            exe = p.chromium.executable_path
            if exe and Path(exe).exists():
                return True
    except Exception:
        pass

    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
    )
    return True


_ensure_chromium()


st.set_page_config(
    page_title="URL Style Extractor",
    page_icon=":art:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- Icons (Lucide, MIT — inline SVG so they recolor with the theme) ----------

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
    'stroke-linecap="round" stroke-linejoin="round" '
    'style="vertical-align:-3px;flex-shrink:0">{body}</svg>'
)

ICON_BODIES = {
    "palette": (
        '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/>'
        '<circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/>'
        '<circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/>'
        '<circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/>'
        '<path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 '
        "0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 "
        "1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z\"/>"
    ),
    "image": (
        '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>'
        '<circle cx="9" cy="9" r="2"/>'
        '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'
    ),
    "type": (
        '<polyline points="4 7 4 4 20 4 20 7"/>'
        '<line x1="9" x2="15" y1="20" y2="20"/>'
        '<line x1="12" x2="12" y1="4" y2="20"/>'
    ),
    "ruler": (
        '<path d="M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7'
        'a2.41 2.41 0 0 1 0-3.4l2.6-2.6a2.41 2.41 0 0 1 3.4 0Z"/>'
        '<path d="m14.5 12.5 2-2"/><path d="m11.5 9.5 2-2"/>'
        '<path d="m8.5 6.5 2-2"/><path d="m17.5 15.5 2-2"/>'
    ),
    "braces": (
        '<path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5a2 2 0 0 0 2 2h1"/>'
        '<path d="M16 21h1a2 2 0 0 0 2-2v-5a2 2 0 0 1 2-2 2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"/>'
    ),
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" x2="12" y1="15" y2="3"/>'
    ),
    "globe": (
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>'
        '<path d="M2 12h20"/>'
    ),
    "file-text": (
        '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="16" x2="8" y1="13" y2="13"/>'
        '<line x1="16" x2="8" y1="17" y2="17"/>'
        '<line x1="10" x2="8" y1="9" y2="9"/>'
    ),
    "history": (
        '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>'
        '<path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>'
    ),
    "external-link": (
        '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
    ),
    "compare": (
        '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/>'
        '<path d="M13 6h3a2 2 0 0 1 2 2v7"/>'
        '<path d="M11 18H8a2 2 0 0 1-2-2V9"/>'
    ),
    "wand": (
        '<path d="M15 4V2"/><path d="M15 16v-2"/>'
        '<path d="M8 9h2"/><path d="M20 9h2"/>'
        '<path d="M17.8 11.8 19 13"/>'
        '<path d="M15 9h.01"/><path d="M17.8 6.2 19 5"/>'
        '<path d="m3 21 9-9"/><path d="M12.2 6.2 11 5"/>'
    ),
}


def icon(name: str, size: int = 18) -> str:
    body = ICON_BODIES.get(name, "")
    return _SVG.format(size=size, body=body)


# ---------- CSS ----------

CUSTOM_CSS = """
<style>
  /* Fonts — closest free matches to Kiro's AWS Diatype family */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  /* Kiro design tokens */
  :root {
    --k-bg-0: #000000;
    --k-bg-1: #19161d;
    --k-bg-2: #28242e;
    --k-bg-3: #4a464f;
    --k-fg-0: #fafafa;
    --k-fg-1: #c1bec6;
    --k-fg-2: #928d9a;
    --k-fg-3: #5e5966;
    --k-accent: #9147ff;
    --k-accent-light: #c59eff;
    --k-success: #80ffb5;
    --k-r-sm: 4px;
    --k-r-md: 16px;
    --k-r-lg: 32px;
    --k-r-pill: 9999px;
  }

  html, body, [data-testid="stAppViewContainer"], .stMarkdown, p, span, div, label {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }
  h1, h2, h3, h4, h5 {
    font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    letter-spacing: -0.025em !important;
    color: var(--k-fg-0);
  }
  code, pre, .swatch-meta, .swatch-hex, .swatch-w, .chip, .type-tag, .type-meta {
    font-family: 'JetBrains Mono', ui-monospace, "SF Mono", Menlo, Consolas, monospace !important;
  }

  .block-container { padding-top: 2rem; max-width: 1200px; }
  #MainMenu, footer { visibility: hidden; }
  header[data-testid="stHeader"] { background: transparent; }

  /* Hero — dark surface with subtle purple radial glow */
  .hero {
    position: relative;
    background: var(--k-bg-1);
    background-image:
      radial-gradient(circle at top right, rgba(145, 71, 255, 0.20), transparent 55%),
      radial-gradient(circle at bottom left, rgba(197, 158, 255, 0.05), transparent 50%);
    border: 1px solid var(--k-bg-2);
    border-radius: var(--k-r-md);
    padding: 2.75rem 2.25rem;
    margin-bottom: 1.5rem;
    overflow: hidden;
  }
  .hero-eyebrow {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--k-accent-light);
    margin-bottom: 0.85rem;
  }
  .hero h1 {
    color: var(--k-fg-0) !important;
    font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    font-size: 2.75rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.04em !important;
    line-height: 1.05 !important;
    margin: 0 0 0.6rem 0 !important;
  }
  .hero p {
    color: var(--k-fg-1);
    font-size: 1.02rem;
    line-height: 1.55;
    max-width: 620px;
    margin: 0;
  }

  /* Section eyebrow — JetBrains Mono uppercase, purple icon */
  .section-h {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin: 2rem 0 1rem 0;
    color: var(--k-fg-1);
  }
  .section-h svg { color: var(--k-accent-light); opacity: 1; }

  /* Color swatches — tight 4px Kiro radius */
  .swatch {
    border-radius: var(--k-r-sm);
    overflow: hidden;
    border: 1px solid var(--k-bg-2);
    background: var(--k-bg-1);
    margin-bottom: 8px;
  }
  .swatch-block { height: 80px; width: 100%; }
  .swatch-meta {
    padding: 8px 10px;
    font-size: 0.74em !important;
    background: var(--k-bg-1);
  }
  .swatch-hex { color: var(--k-fg-0) !important; font-weight: 500; display: block; }
  .swatch-w { color: var(--k-fg-3) !important; font-size: 0.85em; }

  /* Type scale */
  .type-sample {
    padding: 1rem 0;
    border-bottom: 1px solid var(--k-bg-2);
  }
  .type-sample:last-child { border-bottom: none; }
  .type-tag {
    display: inline-block;
    font-size: 0.7em !important;
    padding: 3px 9px;
    background: var(--k-bg-2);
    color: var(--k-accent-light);
    border-radius: var(--k-r-sm);
    margin-right: 0.5rem;
    vertical-align: middle;
  }
  .type-meta {
    color: var(--k-fg-3) !important;
    font-size: 0.76em !important;
  }
  .type-preview {
    margin-top: 0.5rem;
    color: var(--k-fg-0);
    line-height: 1.2;
  }

  /* Chips */
  .chip {
    display: inline-block;
    padding: 5px 10px;
    margin: 0 6px 6px 0;
    background: var(--k-bg-1);
    border: 1px solid var(--k-bg-2);
    border-radius: var(--k-r-sm);
    font-size: 0.78em !important;
    color: var(--k-fg-1);
  }
  .chip .count { color: var(--k-fg-3); margin-left: 8px; }

  /* Site meta link */
  .site-meta a {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--k-accent-light) !important;
    font-size: 0.88em;
    text-decoration: none;
    font-family: 'JetBrains Mono', monospace !important;
  }
  .site-meta a:hover { color: var(--k-fg-0) !important; }

  /* Buttons — Kiro pill-shape */
  .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    border-radius: var(--k-r-pill) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    letter-spacing: -0.005em !important;
    transition: all 0.15s ease !important;
    padding: 0.45rem 1.15rem !important;
  }
  .stButton > button[kind="primary"],
  .stFormSubmitButton > button[kind="primary"] {
    background: var(--k-accent) !important;
    border-color: var(--k-accent) !important;
    color: #fafafa !important;
  }
  .stButton > button[kind="primary"]:hover,
  .stFormSubmitButton > button[kind="primary"]:hover {
    background: var(--k-accent-light) !important;
    border-color: var(--k-accent-light) !important;
    color: var(--k-bg-0) !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(145, 71, 255, 0.25);
  }
  .stDownloadButton > button {
    background: var(--k-bg-1) !important;
    border: 1px solid var(--k-bg-2) !important;
    color: var(--k-fg-0) !important;
  }
  .stDownloadButton > button:hover {
    background: var(--k-bg-2) !important;
    border-color: var(--k-accent) !important;
    color: var(--k-fg-0) !important;
  }

  /* Text input */
  .stTextInput > div > div > input,
  .stTextInput input {
    background: var(--k-bg-1) !important;
    border: 1px solid var(--k-bg-2) !important;
    border-radius: var(--k-r-sm) !important;
    color: var(--k-fg-0) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.92em !important;
  }
  .stTextInput input:focus {
    border-color: var(--k-accent) !important;
    box-shadow: 0 0 0 3px rgba(145, 71, 255, 0.18) !important;
  }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background: var(--k-bg-1) !important;
    border-right: 1px solid var(--k-bg-2) !important;
  }
  [data-testid="stSidebar"] h2 { margin-top: 0; font-size: 1rem; }
  [data-testid="stSidebar"] .stButton button {
    background: transparent !important;
    border: 1px solid transparent !important;
    text-align: left !important;
    justify-content: flex-start !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82em !important;
    font-weight: 400 !important;
    color: var(--k-fg-1) !important;
    border-radius: var(--k-r-sm) !important;
    padding: 5px 10px !important;
  }
  [data-testid="stSidebar"] .stButton button:hover {
    background: var(--k-bg-2) !important;
    border-color: var(--k-bg-2) !important;
    color: var(--k-fg-0) !important;
    transform: none !important;
    box-shadow: none !important;
  }
  [data-testid="stSidebar"] .section-h { margin-top: 0.5rem !important; }

  .sidebar-title {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
    letter-spacing: -0.02em;
    color: var(--k-fg-0);
  }
  .sidebar-title svg { color: var(--k-accent-light); }

  /* Status line in extraction progress */
  .status-line {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0.3rem 0;
    font-family: 'Inter', sans-serif;
    color: var(--k-fg-1);
    font-size: 0.92em;
  }
  .status-line svg { color: var(--k-accent-light); }

  /* Code blocks */
  [data-testid="stCodeBlock"], pre {
    background: var(--k-bg-1) !important;
    border: 1px solid var(--k-bg-2) !important;
    border-radius: var(--k-r-sm) !important;
  }
  [data-testid="stCodeBlock"] code { color: var(--k-fg-1) !important; }

  /* Status / alert / info boxes */
  [data-testid="stAlert"] {
    background: var(--k-bg-1) !important;
    border: 1px solid var(--k-bg-2) !important;
    border-left: 3px solid var(--k-accent) !important;
    border-radius: var(--k-r-sm) !important;
  }
  [data-testid="stStatus"] {
    background: var(--k-bg-1) !important;
    border: 1px solid var(--k-bg-2) !important;
    border-radius: var(--k-r-sm) !important;
  }

  /* Images get a light frame */
  [data-testid="stImage"] img {
    border-radius: var(--k-r-md);
    border: 1px solid var(--k-bg-2);
  }

  /* Expander */
  [data-testid="stExpander"] {
    background: var(--k-bg-1) !important;
    border: 1px solid var(--k-bg-2) !important;
    border-radius: var(--k-r-sm) !important;
  }
  [data-testid="stExpander"] summary { font-family: 'Inter', sans-serif; }

  /* Dataframe — when used */
  [data-testid="stDataFrame"] { border-radius: var(--k-r-sm); }

  /* Captions and small text */
  .stCaption, [data-testid="stCaptionContainer"] { color: var(--k-fg-3) !important; }

  /* Links */
  a { color: var(--k-accent-light); }
  a:hover { color: var(--k-fg-0); }

  /* Tabs */
  [data-testid="stTabs"] [role="tablist"] {
    gap: 4px;
    border-bottom: 1px solid var(--k-bg-2);
    margin-bottom: 1rem;
  }
  [data-testid="stTabs"] [role="tab"] {
    background: transparent !important;
    border-radius: var(--k-r-sm) var(--k-r-sm) 0 0 !important;
    padding: 0.5rem 1rem !important;
    color: var(--k-fg-2) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    border: 1px solid transparent !important;
    border-bottom: none !important;
  }
  [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: var(--k-fg-0) !important;
    background: var(--k-bg-1) !important;
    border-color: var(--k-bg-2) !important;
  }
  [data-testid="stTabs"] [role="tab"]:hover {
    color: var(--k-fg-0) !important;
  }
  /* Hide Streamlit's red/pink active-tab indicator */
  [data-testid="stTabs"] [role="tablist"] [data-baseweb="tab-highlight"],
  [data-testid="stTabs"] [data-baseweb="tab-border"] {
    background: var(--k-accent) !important;
  }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------- helpers ----------

def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def domain_for(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "") or "site"


def run_extract(url: str, out_dir: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "extract.py"), url, str(out_dir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
    )
    if proc.returncode != 0:
        return False, proc.stderr or proc.stdout
    return True, proc.stdout


def run_render(json_path: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "render_moodboard.py"), str(json_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
    )
    if proc.returncode != 0:
        return False, proc.stderr or proc.stdout
    return True, proc.stdout


def run_styleguide(json_path: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_styleguide.py"), str(json_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
    )
    if proc.returncode != 0:
        return False, proc.stderr or proc.stdout
    return True, proc.stdout


def make_zip(out_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.iterdir():
            if f.is_file():
                zf.write(f, arcname=f.name)
    return buf.getvalue()


def inject_google_fonts(urls: list[str]) -> None:
    if not urls:
        return
    links = "\n".join(f'<link rel="stylesheet" href="{u}">' for u in urls)
    st.markdown(links, unsafe_allow_html=True)


def section_header(name: str, label: str) -> None:
    st.markdown(f'<div class="section-h">{icon(name)}<span>{label}</span></div>', unsafe_allow_html=True)


def render_swatches(colors: list[dict], cols_per_row: int = 6) -> None:
    if not colors:
        st.caption("None detected.")
        return
    for i in range(0, len(colors), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, c in zip(cols, colors[i : i + cols_per_row]):
            hex_clean = c["hex"].split(" ")[0]
            col.markdown(
                f"""
<div class="swatch">
  <div class="swatch-block" style="background:{hex_clean}"></div>
  <div class="swatch-meta">
    <span class="swatch-hex">{c['hex']}</span>
    <span class="swatch-w">weight {c['weight']:.0f}</span>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )


_PX_RE = re.compile(r"(\d+(?:\.\d+)?)px")


def _cap_px(size: str, cap_px: int | None) -> str:
    if not cap_px:
        return size
    m = _PX_RE.match(size)
    if m and float(m.group(1)) > cap_px:
        return f"{cap_px}px"
    return size


def render_type_scale(samples: dict, cap_px: int | None = None) -> None:
    sample_text = "The quick brown fox jumps over the lazy dog"
    rows = []
    for tag, s in samples.items():
        if not s:
            continue
        family = s["fontFamily"]
        size = _cap_px(s["fontSize"], cap_px)
        weight = s["fontWeight"]
        lh = s["lineHeight"]
        primary_family = family.split(",")[0].strip().strip('"\'')
        rows.append(
            f"""
<div class="type-sample">
  <span class="type-tag">{tag}</span>
  <span class="type-meta">{size} · {weight} · {primary_family}</span>
  <div class="type-preview" style="font-family:{family};font-size:{size};font-weight:{weight};line-height:{lh}">
    {sample_text}
  </div>
</div>
            """
        )
    if rows:
        st.markdown("".join(rows), unsafe_allow_html=True)
    else:
        st.caption("No type-scale samples detected.")


def render_chips(items: list[dict], with_count: bool = True) -> None:
    if not items:
        st.caption("None detected.")
        return
    chips = "".join(
        f'<span class="chip">{x["value"]}'
        + (f'<span class="count">{x["weight"]:.0f}×</span>' if with_count else "")
        + "</span>"
        for x in items
    )
    st.markdown(chips, unsafe_allow_html=True)


def render_results(out_dir: Path, data: dict) -> None:
    inject_google_fonts(data.get("googleFonts", []))

    st.markdown(f"### {data['title'] or '—'}")
    st.markdown(
        f'<div class="site-meta"><a href="{data["url"]}" target="_blank">'
        f'{data["url"]}{icon("external-link", 14)}</a></div>',
        unsafe_allow_html=True,
    )

    fold = out_dir / "screenshot-fold.png"
    if fold.exists():
        st.image(str(fold), caption="Above the fold (1440×900)", use_container_width=True)

    section_header("palette", "Foreground colors — text, icons, borders")
    render_swatches(data["colors"])

    section_header("image", "Background colors — surfaces, fills")
    render_swatches(data["backgrounds"])

    section_header("type", "Typography")
    if data["googleFonts"]:
        st.markdown("**Google Fonts loaded by the page**")
        for f in data["googleFonts"]:
            st.markdown(f"- [{f}]({f})")

    if data["fonts"]:
        st.markdown("**Top font-families (ranked by usage area)**")
        for f in data["fonts"]:
            st.markdown(f"- `{f['value']}` — weight {f['weight']:.0f}")

    st.markdown('<div style="margin-top:1rem;font-size:0.85em;opacity:0.7">Type scale rendered in the actual fonts</div>', unsafe_allow_html=True)
    render_type_scale(data["samples"])

    section_header("ruler", "Design tokens")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Border radii**")
        render_chips(data["radii"])
    with col2:
        st.markdown("**Spacing**")
        render_chips(data["spacing"], with_count=False)
    with col3:
        st.markdown("**Shadows**")
        if data["shadows"]:
            for s in data["shadows"]:
                st.code(s["value"], language="css")
        else:
            st.caption("None detected.")

    if data.get("cssVars"):
        section_header("braces", "CSS custom properties")
        css = ":root {\n" + "\n".join(
            f"  {name}: {val};" for name, val in data["cssVars"].items()
        ) + "\n}"
        st.code(css, language="css")

    if data.get("fontFaces"):
        with st.expander("Same-origin @font-face declarations"):
            st.code("\n".join(data["fontFaces"]), language="css")

    full = out_dir / "screenshot-full.png"
    if full.exists():
        with st.expander("Full-page screenshot"):
            st.image(str(full), use_container_width=True)

    section_header("download", "Export")
    moodboard = out_dir / "moodboard.md"
    styles_json = out_dir / "styles.json"
    styleguide = out_dir / "styleguide.md"

    dl1, dl2, dl3, dl4 = st.columns(4)
    if styleguide.exists():
        dl1.download_button(
            "styleguide.md",
            data=styleguide.read_bytes(),
            file_name=f"{out_dir.name}-styleguide.md",
            mime="text/markdown",
            help="Drop into .claude/skills/ as a Claude Code Skill",
            use_container_width=True,
        )
    if moodboard.exists():
        dl2.download_button(
            "moodboard.md",
            data=moodboard.read_bytes(),
            file_name=f"{out_dir.name}-moodboard.md",
            mime="text/markdown",
            help="Human-readable visual reference",
            use_container_width=True,
        )
    if styles_json.exists():
        dl3.download_button(
            "styles.json",
            data=styles_json.read_bytes(),
            file_name=f"{out_dir.name}-styles.json",
            mime="application/json",
            help="Raw extraction data",
            use_container_width=True,
        )
    dl4.download_button(
        "Download ZIP",
        data=make_zip(out_dir),
        file_name=f"{out_dir.name}-styles.zip",
        mime="application/zip",
        help="Everything bundled (markdown, JSON, screenshots)",
        use_container_width=True,
    )


def render_compare_view() -> None:
    if not OUTPUTS_DIR.exists():
        st.info("No extractions yet — use the **Extract** tab first.")
        return
    sites = sorted(
        [d for d in OUTPUTS_DIR.iterdir() if d.is_dir() and (d / "styles.json").exists()],
        key=lambda d: d.name,
    )
    if len(sites) < 2:
        st.info("Extract at least two URLs first, then come back here.")
        return

    site_names = [d.name for d in sites]
    col_a, col_b = st.columns(2)
    a_name = col_a.selectbox("Site A", site_names, index=0, key="cmp_a")
    default_b = 1 if site_names[0] == a_name else 0
    b_name = col_b.selectbox("Site B", site_names, index=default_b, key="cmp_b")

    if a_name == b_name:
        st.warning("Pick two different sites.")
        return

    dir_a = OUTPUTS_DIR / a_name
    dir_b = OUTPUTS_DIR / b_name
    data_a = json.loads((dir_a / "styles.json").read_text(encoding="utf-8"))
    data_b = json.loads((dir_b / "styles.json").read_text(encoding="utf-8"))

    inject_google_fonts(
        list(set(data_a.get("googleFonts", []) + data_b.get("googleFonts", [])))
    )

    pane_a, pane_b = st.columns(2)
    for pane, dir_, data in [(pane_a, dir_a, data_a), (pane_b, dir_b, data_b)]:
        with pane:
            st.markdown(f"#### {data['title'] or '—'}")
            st.markdown(
                f'<div class="site-meta"><a href="{data["url"]}" target="_blank">'
                f'{data["url"]}{icon("external-link", 12)}</a></div>',
                unsafe_allow_html=True,
            )
            fold = dir_ / "screenshot-fold.png"
            if fold.exists():
                st.image(str(fold), use_container_width=True)

            st.markdown(
                f'<div class="section-h">{icon("palette", 14)}<span>Foreground</span></div>',
                unsafe_allow_html=True,
            )
            render_swatches(data["colors"][:6], cols_per_row=3)

            st.markdown(
                f'<div class="section-h">{icon("image", 14)}<span>Background</span></div>',
                unsafe_allow_html=True,
            )
            render_swatches(data["backgrounds"][:6], cols_per_row=3)

            st.markdown(
                f'<div class="section-h">{icon("type", 14)}<span>Type scale</span></div>',
                unsafe_allow_html=True,
            )
            key_samples = {
                k: data["samples"].get(k)
                for k in ["h1", "h2", "body", "button"]
                if (data.get("samples") or {}).get(k)
            }
            render_type_scale(key_samples, cap_px=28)

            st.markdown(
                f'<div class="section-h">{icon("ruler", 14)}<span>Border radii</span></div>',
                unsafe_allow_html=True,
            )
            render_chips(data["radii"][:6])


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown(
        f'<div class="sidebar-title">{icon("palette", 20)}<span>URL Style Extractor</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Reverse-engineer the visual style of any website.")
    st.divider()

    st.markdown(
        f'<div class="section-h" style="margin-top:0">{icon("history")}<span>History</span></div>',
        unsafe_allow_html=True,
    )
    if OUTPUTS_DIR.exists():
        history = sorted(
            [d for d in OUTPUTS_DIR.iterdir() if d.is_dir() and (d / "styles.json").exists()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if history:
            for d in history:
                if st.button(d.name, key=f"hist-{d.name}", use_container_width=True):
                    st.session_state["selected_dir"] = str(d)
                    st.rerun()
        else:
            st.caption("No extractions yet.")
    else:
        st.caption("No extractions yet.")

    st.divider()
    st.markdown(
        f'<div style="opacity:0.5;font-size:0.8em">'
        f'<a href="https://github.com/0ldManPlaying/url-style-extractor" target="_blank" '
        f'style="color:inherit;display:inline-flex;align-items:center;gap:0.35rem;text-decoration:none">'
        f'GitHub repo{icon("external-link", 13)}</a></div>',
        unsafe_allow_html=True,
    )


# ---------- Main ----------
st.markdown(
    """
<div class="hero">
  <div class="hero-eyebrow">Style extraction · v1</div>
  <h1>URL Style Extractor</h1>
  <p>Extract the visual DNA from any live website — color palette, fonts, type scale,
  spacing, shadows, design tokens, and screenshots — in one click.</p>
</div>
    """,
    unsafe_allow_html=True,
)

tab_extract, tab_compare = st.tabs(["Extract", "Compare two sites"])

with tab_extract:
    with st.form("extract_form", clear_on_submit=False):
        col_url, col_btn = st.columns([4, 1])
        url_input = col_url.text_input(
            "URL", placeholder="https://stripe.com", label_visibility="collapsed",
        )
        submit = col_btn.form_submit_button("Extract", type="primary", use_container_width=True)

    selected_dir: Path | None = None

    if submit and url_input:
        url = normalize_url(url_input)
        out_dir = OUTPUTS_DIR / domain_for(url)
        with st.status(f"Extracting **{url}** …", expanded=True) as status:
            st.markdown(
                f'<div class="status-line">{icon("globe", 16)}<span>Launching headless Chromium and loading the page…</span></div>',
                unsafe_allow_html=True,
            )
            ok, msg = run_extract(url, out_dir)
            if not ok:
                status.update(label="Extraction failed", state="error")
                st.error(msg)
                st.stop()
            st.markdown(
                f'<div class="status-line">{icon("file-text", 16)}<span>Generating markdown moodboard…</span></div>',
                unsafe_allow_html=True,
            )
            ok2, msg2 = run_render(out_dir / "styles.json")
            if not ok2:
                status.update(label="Rendering failed", state="error")
                st.error(msg2)
                st.stop()
            st.markdown(
                f'<div class="status-line">{icon("wand", 16)}<span>Generating Skill / style guide…</span></div>',
                unsafe_allow_html=True,
            )
            ok3, msg3 = run_styleguide(out_dir / "styles.json")
            if not ok3:
                status.update(label="Style-guide generation failed", state="error")
                st.error(msg3)
                st.stop()
            status.update(label="Done", state="complete")
        st.session_state["selected_dir"] = str(out_dir)
        selected_dir = out_dir
    elif "selected_dir" in st.session_state:
        selected_dir = Path(st.session_state["selected_dir"])

    if selected_dir and (selected_dir / "styles.json").exists():
        # Backfill styleguide.md for older extractions that predate the generator
        if not (selected_dir / "styleguide.md").exists():
            run_styleguide(selected_dir / "styles.json")
        data = json.loads((selected_dir / "styles.json").read_text(encoding="utf-8"))
        render_results(selected_dir, data)
    else:
        st.info(
            "Enter a URL above and click **Extract**. The first run can take 10-30 seconds "
            "while Chromium loads the page."
        )

with tab_compare:
    render_compare_view()
