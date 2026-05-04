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


def swatch_grid(colors: list[dict], cols_per_row: int = 6) -> None:
    if not colors:
        st.caption("Geen kleuren gevonden.")
        return
    for i in range(0, len(colors), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, c in zip(cols, colors[i : i + cols_per_row]):
            hex_clean = c["hex"].split(" ")[0]
            col.markdown(
                f"""
<div style="background:{hex_clean};height:88px;border-radius:8px;
border:1px solid rgba(0,0,0,0.1);margin-bottom:6px"></div>
<div style="font-family:monospace;font-size:0.85em">
  <strong>{c['hex']}</strong><br>
  <span style="color:#888">w {c['weight']:.0f}</span>
</div>
                """,
                unsafe_allow_html=True,
            )


def make_zip(out_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.iterdir():
            if f.is_file():
                zf.write(f, arcname=f.name)
    return buf.getvalue()


def render_results(out_dir: Path, data: dict) -> None:
    st.subheader(data["title"] or "—")
    st.caption(data["url"])

    fold = out_dir / "screenshot-fold.png"
    if fold.exists():
        st.image(str(fold), caption="Above the fold (1440×900)", use_container_width=True)

    st.divider()

    st.markdown("### 🎨 Foreground colors (text, icons, borders)")
    swatch_grid(data["colors"])

    st.markdown("### 🖼️ Background colors (surfaces, fills)")
    swatch_grid(data["backgrounds"])

    st.divider()

    st.markdown("### 🔤 Typography")
    if data["googleFonts"]:
        st.markdown("**Google Fonts loaded:**")
        for f in data["googleFonts"]:
            st.markdown(f"- [{f}]({f})")

    if data["fonts"]:
        st.markdown("**Top font-families (ranked by usage area):**")
        for f in data["fonts"]:
            st.markdown(f"- `{f['value']}` — weight {f['weight']:.0f}")

    type_rows = []
    for tag, s in data["samples"].items():
        if not s:
            continue
        type_rows.append(
            {
                "element": tag,
                "family": s["fontFamily"],
                "size": s["fontSize"],
                "weight": s["fontWeight"],
                "line-height": s["lineHeight"],
                "letter-spacing": s.get("letterSpacing", "—"),
                "color": s["color"],
            }
        )
    if type_rows:
        st.markdown("**Type scale**")
        st.dataframe(type_rows, use_container_width=True, hide_index=True)

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 📐 Border radii")
        if data["radii"]:
            for r in data["radii"]:
                st.markdown(f"- `{r['value']}` ({r['weight']:.0f}×)")
        else:
            st.caption("Geen radii gevonden.")
    with col2:
        st.markdown("### 🌫️ Shadows")
        if data["shadows"]:
            for s in data["shadows"]:
                st.code(s["value"], language="css")
        else:
            st.caption("Geen shadows gevonden.")
    with col3:
        st.markdown("### 📏 Spacing")
        if data["spacing"]:
            for s in data["spacing"]:
                st.markdown(f"- `{s['value']}`")
        else:
            st.caption("Geen spacing-tokens gevonden.")

    if data.get("cssVars"):
        st.divider()
        st.markdown("### 🎯 CSS custom properties (design tokens)")
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

    st.divider()
    st.markdown("### ⬇️ Downloads")
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
        "📦 alles als zip",
        data=make_zip(out_dir),
        file_name=f"{out_dir.name}-moodboard.zip",
        mime="application/zip",
        use_container_width=True,
    )


# ---------- Sidebar: history ----------
with st.sidebar:
    st.markdown("## 🎨 URL Style Extractor")
    st.caption("Haal het stijl-DNA uit elke website.")
    st.divider()
    st.markdown("### Geschiedenis")
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
            st.caption("Nog geen extracties.")
    else:
        st.caption("Nog geen extracties.")


# ---------- Main ----------
st.title("🎨 URL Style Extractor")
st.markdown(
    "Geef een URL en haal het stijl-DNA eruit: kleurenpalet, fonts, type-scale, "
    "spacing, shadows, design tokens en screenshots."
)

with st.form("extract_form", clear_on_submit=False):
    col_url, col_btn = st.columns([4, 1])
    url_input = col_url.text_input(
        "URL",
        placeholder="https://stripe.com",
        label_visibility="collapsed",
    )
    submit = col_btn.form_submit_button("Extract", type="primary", use_container_width=True)

selected_dir: Path | None = None

if submit and url_input:
    url = normalize_url(url_input)
    out_dir = OUTPUTS_DIR / domain_for(url)
    with st.status(f"Extracting **{url}** …", expanded=True) as status:
        st.write("🌐 Headless Chromium starten en pagina laden…")
        ok, msg = run_extract(url, out_dir)
        if not ok:
            status.update(label="Extractie mislukt", state="error")
            st.error(msg)
            st.stop()
        st.write("📝 Moodboard markdown genereren…")
        ok2, msg2 = run_render(out_dir / "styles.json")
        if not ok2:
            status.update(label="Rendering mislukt", state="error")
            st.error(msg2)
            st.stop()
        status.update(label="Klaar!", state="complete")
    st.session_state["selected_dir"] = str(out_dir)
    selected_dir = out_dir
elif "selected_dir" in st.session_state:
    selected_dir = Path(st.session_state["selected_dir"])

if selected_dir and (selected_dir / "styles.json").exists():
    data = json.loads((selected_dir / "styles.json").read_text(encoding="utf-8"))
    render_results(selected_dir, data)
else:
    st.info(
        "Vul een URL in en druk op **Extract**. De eerste run kan 10-30 seconden duren "
        "terwijl Chromium de pagina laadt."
    )
