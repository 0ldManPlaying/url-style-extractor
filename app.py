"""Streamlit UI for the URL Style Extractor."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

ROOT = Path(__file__).parent
OUTPUTS_DIR = ROOT / "outputs"

st.set_page_config(
    page_title="URL Style Extractor",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
  .block-container { padding-top: 2rem; max-width: 1200px; }

  /* Hide Streamlit chrome we don't need */
  #MainMenu, footer { visibility: hidden; }
  header[data-testid="stHeader"] { background: transparent; }

  /* Hero */
  .hero {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%);
    border-radius: 18px;
    padding: 2.5rem 2.25rem;
    margin-bottom: 1.75rem;
    color: white;
    box-shadow: 0 10px 40px rgba(99, 102, 241, 0.25);
  }
  .hero h1 {
    color: white !important;
    margin: 0 0 0.5rem 0;
    font-size: 2.25rem;
    font-weight: 700;
    letter-spacing: -0.02em;
  }
  .hero p {
    color: rgba(255,255,255,0.92);
    margin: 0;
    font-size: 1.05rem;
    line-height: 1.5;
  }

  /* Section header */
  .section-h {
    font-size: 1.05rem;
    font-weight: 600;
    margin: 1.5rem 0 0.75rem 0;
    letter-spacing: -0.01em;
    opacity: 0.95;
  }

  /* Color cards */
  .swatch {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(128,128,128,0.18);
    margin-bottom: 4px;
  }
  .swatch-block { height: 92px; width: 100%; }
  .swatch-meta {
    padding: 8px 12px;
    font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    font-size: 0.82em;
    background: rgba(128,128,128,0.05);
  }
  .swatch-hex { font-weight: 600; display: block; }
  .swatch-w { opacity: 0.55; font-size: 0.85em; }

  /* Type scale samples — render in actual fonts */
  .type-sample {
    padding: 0.85rem 0;
    border-bottom: 1px solid rgba(128,128,128,0.12);
  }
  .type-sample:last-child { border-bottom: none; }
  .type-tag {
    display: inline-block;
    font-family: ui-monospace, monospace;
    font-size: 0.72em;
    padding: 2px 8px;
    background: rgba(128,128,128,0.12);
    border-radius: 5px;
    margin-right: 0.5rem;
    vertical-align: middle;
  }
  .type-meta {
    opacity: 0.55;
    font-size: 0.78em;
    font-family: ui-monospace, monospace;
  }
  .type-preview {
    margin-top: 0.4rem;
    line-height: 1.2;
  }

  /* Token chips */
  .chip {
    display: inline-block;
    padding: 4px 10px;
    margin: 0 6px 6px 0;
    background: rgba(128,128,128,0.1);
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 6px;
    font-family: ui-monospace, monospace;
    font-size: 0.82em;
  }
  .chip .count { opacity: 0.55; margin-left: 6px; }

  /* Sidebar tweaks */
  [data-testid="stSidebar"] h2 { margin-top: 0; }
  [data-testid="stSidebar"] .stButton button {
    text-align: left;
    justify-content: flex-start;
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
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    if proc.returncode != 0:
        return False, proc.stderr or proc.stdout
    return True, proc.stdout


def run_render(json_path: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "render_moodboard.py"), str(json_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
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
    """Load the page's Google Fonts so the type-scale preview renders correctly."""
    if not urls:
        return
    links = "\n".join(
        f'<link rel="stylesheet" href="{u}">' for u in urls
    )
    st.markdown(links, unsafe_allow_html=True)


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


def render_type_scale(samples: dict) -> None:
    sample_text = "The quick brown fox jumps over the lazy dog"
    rows = []
    for tag, s in samples.items():
        if not s:
            continue
        family = s["fontFamily"]
        size = s["fontSize"]
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
    st.markdown(f"<a href='{data['url']}' target='_blank' style='opacity:0.7;font-size:0.9em'>{data['url']}</a>", unsafe_allow_html=True)

    fold = out_dir / "screenshot-fold.png"
    if fold.exists():
        st.image(str(fold), caption="Above the fold (1440×900)", use_container_width=True)

    # Colors
    st.markdown('<div class="section-h">🎨 Foreground colors — text, icons, borders</div>', unsafe_allow_html=True)
    render_swatches(data["colors"])

    st.markdown('<div class="section-h">🖼️ Background colors — surfaces, fills</div>', unsafe_allow_html=True)
    render_swatches(data["backgrounds"])

    # Typography
    st.markdown('<div class="section-h">🔤 Typography</div>', unsafe_allow_html=True)
    if data["googleFonts"]:
        st.markdown("**Google Fonts loaded by the page:**")
        for f in data["googleFonts"]:
            st.markdown(f"- [{f}]({f})")

    if data["fonts"]:
        st.markdown("**Top font-families (ranked by usage area):**")
        for f in data["fonts"]:
            st.markdown(f"- `{f['value']}` — weight {f['weight']:.0f}")

    st.markdown('<div class="section-h">Type scale — rendered in the actual fonts</div>', unsafe_allow_html=True)
    render_type_scale(data["samples"])

    # Tokens grid
    st.markdown('<div class="section-h">📐 Design tokens</div>', unsafe_allow_html=True)
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
        st.markdown('<div class="section-h">🎯 CSS custom properties</div>', unsafe_allow_html=True)
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

    # Downloads
    st.markdown('<div class="section-h">⬇️ Export</div>', unsafe_allow_html=True)
    moodboard = out_dir / "moodboard.md"
    styles_json = out_dir / "styles.json"

    dl1, dl2, dl3 = st.columns(3)
    if moodboard.exists():
        dl1.download_button(
            "📄 moodboard.md",
            data=moodboard.read_bytes(),
            file_name="moodboard.md",
            mime="text/markdown",
            use_container_width=True,
        )
    if styles_json.exists():
        dl2.download_button(
            "🧾 styles.json",
            data=styles_json.read_bytes(),
            file_name="styles.json",
            mime="application/json",
            use_container_width=True,
        )
    dl3.download_button(
        "📦 Everything as zip",
        data=make_zip(out_dir),
        file_name=f"{out_dir.name}-moodboard.zip",
        mime="application/zip",
        use_container_width=True,
    )


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 🎨 URL Style Extractor")
    st.caption("Reverse-engineer the visual style of any website.")
    st.divider()
    st.markdown("### History")
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
        '<div style="opacity:0.5;font-size:0.8em">'
        '<a href="https://github.com/0ldManPlaying/url-style-extractor" target="_blank" style="color:inherit">GitHub repo →</a>'
        "</div>",
        unsafe_allow_html=True,
    )


# ---------- Main ----------
st.markdown(
    """
<div class="hero">
  <h1>URL Style Extractor</h1>
  <p>Extract the visual DNA from any live website — color palette, fonts, type scale,
  spacing, shadows, design tokens, and screenshots — in one click.</p>
</div>
    """,
    unsafe_allow_html=True,
)

with st.form("extract_form", clear_on_submit=False):
    col_url, col_btn = st.columns([4, 1])
    url_input = col_url.text_input(
        "URL",
        placeholder="https://stripe.com",
        label_visibility="collapsed",
    )
    submit = col_btn.form_submit_button("Extract →", type="primary", use_container_width=True)

selected_dir: Path | None = None

if submit and url_input:
    url = normalize_url(url_input)
    out_dir = OUTPUTS_DIR / domain_for(url)
    with st.status(f"Extracting **{url}** …", expanded=True) as status:
        st.write("🌐 Launching headless Chromium and loading the page…")
        ok, msg = run_extract(url, out_dir)
        if not ok:
            status.update(label="Extraction failed", state="error")
            st.error(msg)
            st.stop()
        st.write("📝 Generating markdown moodboard…")
        ok2, msg2 = run_render(out_dir / "styles.json")
        if not ok2:
            status.update(label="Rendering failed", state="error")
            st.error(msg2)
            st.stop()
        status.update(label="Done!", state="complete")
    st.session_state["selected_dir"] = str(out_dir)
    selected_dir = out_dir
elif "selected_dir" in st.session_state:
    selected_dir = Path(st.session_state["selected_dir"])

if selected_dir and (selected_dir / "styles.json").exists():
    data = json.loads((selected_dir / "styles.json").read_text(encoding="utf-8"))
    render_results(selected_dir, data)
else:
    st.info(
        "Enter a URL above and hit **Extract**. The first run can take 10-30 seconds "
        "while Chromium loads the page."
    )
