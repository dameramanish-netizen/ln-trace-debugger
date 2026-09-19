import streamlit as st
import gzip
import os
import tempfile
import pandas as pd
import re
import base64
import hashlib
import io
from html import escape
from PIL import Image, ImageOps
from pathlib import Path

# --- Page Configuration & Theme Styling ---
st.set_page_config(
    page_title="Infor LN Enterprise Trace Debugger",
    page_icon="🔍",
    layout="wide"
)

st.slider(
    "Panel transparency",
    min_value=0,
    max_value=90,
    value=15,
    step=5,
    format="%d%%",
    key="panel_transparency",
    help="0% means solid panels. Higher values reveal more background.",
)

# Appearance is session-local; no external image service is used.
def reset_appearance():
    st.session_state.default_theme = "System"
    st.session_state.background_mode = "Default"
    st.session_state.background_dim = 45
    st.session_state.background_uri = ""
    st.session_state.background_hash = ""
    st.session_state.background_version = st.session_state.get("background_version", 0) + 1
    st.session_state.panel_transparency = 15


def prepare_background(upload):
    if upload.size > 10 * 1024 * 1024:
        raise ValueError("Choose an image smaller than 10 MB.")
    with Image.open(io.BytesIO(upload.getvalue())) as image:
        if image.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError("Choose a JPG, PNG, or WebP image.")
        if image.width * image.height > 25_000_000:
            raise ValueError("Choose an image with fewer than 25 million pixels.")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((2400, 1600))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def apply_appearance():
    mode = st.session_state.get("background_mode", "Default")
    uri = st.session_state.get("background_uri", "") if mode == "Custom" else ""
    if mode == "Presets":
        preset_file = PRESETS[st.session_state.get("nature_preset", "Mountain woods")]
        path = Path(__file__).parent / "assets" / preset_file
        if path.exists():
            uri = "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
        else:
            st.warning("Preset image missing. Upload the assets folder included in the ZIP.")
    dim = st.session_state.get("background_dim", 45) / 100
    background = (
        f'linear-gradient(rgba(9,20,42,{dim}),rgba(9,20,42,{dim})), url("{uri}")'
        if uri else "linear-gradient(135deg,#f5f7fc,#edf2fa)"
    )
    st.markdown("""
    <style>
    .stApp {background: BACKGROUND_VALUE; background-size:cover;
        background-position:center; background-attachment:fixed;}
    [data-testid="stHeader"] {background:rgba(247,249,253,.88);}
    [data-testid="stMainBlockContainer"] {padding-top:2rem; max-width:1600px;}
    [data-testid="stSidebar"] {background:rgba(246,249,255,.94);
        border-right:1px solid #d9e2ef; backdrop-filter:blur(18px);}
    [data-testid="stSidebar"] h2 {font-size:1.3rem;}
    [data-testid="stSidebar"] h3 {font-size:1rem;}
    .hero {padding:18px 22px; margin-bottom:20px; border-radius:12px;
        background:rgba(255,255,255,.91); border:1px solid #dce4f0;}
    .hero h1 {font-size:2rem; padding:0; margin:0; color:#142443;}
    .hero p {margin:6px 0 0; color:#526582;}
    .status-strip,.focus-card {background:rgba(255,255,255,.91);
        border:1px solid #dce4f0; border-radius:10px; padding:16px 20px;
        margin-bottom:18px; color:#142443; backdrop-filter:blur(12px); overflow-wrap:anywhere;}
    .status-strip {display:flex; gap:20px; align-items:center; flex-wrap:wrap;}
    .badge {display:inline-block; background:#eaf1ff; color:#2457ab;
        padding:4px 10px; border-radius:6px; margin:4px 6px 4px 0; font-size:13px;}
    .focus-card pre {white-space:pre-wrap; overflow-wrap:anywhere; font-size:13px;}
    [data-baseweb="tab-list"] {background:rgba(255,255,255,.94);
        border-radius:10px; padding:4px 12px; gap:22px;}
    [data-baseweb="tab"] {color:#344c70;}
    [data-baseweb="tab"][aria-selected="true"] {color:#2563eb;}
    [data-baseweb="tab-highlight"] {background:#2563eb;}
    .st-key-results_panel,.st-key-stack_panel,.st-key-empty_panel {
        background:rgba(255,255,255,.93); border:1px solid #dce4f0;
        border-radius:12px; padding:20px; backdrop-filter:blur(12px);}
    [data-testid="stCode"], [data-testid="stCode"] pre {background:#fff !important;}
    [data-testid="stCode"] code {color:#162b4d !important;
        font-family:Consolas,'Courier New',monospace !important; font-size:13px !important;}
    [data-testid="stButton"] button,[data-testid="stDownloadButton"] button {border-radius:8px;}
    [data-testid="stButton"] button[kind="primary"] {background:#2563eb; color:white; border:0;}
    [data-testid="stAlert"] {background:rgba(245,249,255,.98); color:#142443;}
    @media(max-width:760px) {
        [data-testid="stMainBlockContainer"] {padding:1rem;}
        .hero h1 {font-size:1.5rem;}
        .st-key-results_panel,.st-key-stack_panel {padding:12px;}
    }
    [data-testid="stMainBlockContainer"] {padding:2.8rem 1.5rem 1.5rem; max-width:none;}
    [data-testid="stHeader"] {background:transparent; height:2.5rem;}
    /* Let Streamlit control sidebar width, collapse, and mobile overlays. */
    [data-testid="stSidebarUserContent"] {padding:0 1.1rem 1rem;}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.42rem;}
    [data-testid="stSidebar"] h2 {padding:.2rem 0 .3rem;}
    [data-testid="stSidebar"] h3 {padding:.3rem 0 .15rem; font-size:.95rem;}
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {padding:.4rem; min-height:0;}
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] {display:none;}
    [data-testid="stSidebar"] button {min-height:2rem; padding:.25rem .55rem;}
    [data-testid="stSidebar"] hr {margin:.4rem 0;}
    [data-testid="stSidebar"] [data-testid="stCheckbox"] {min-height:1.7rem;}
    [data-testid="stSidebar"] [data-testid="stCheckbox"] label:has(input:checked) span:first-child {background-color:#2563eb; border-color:#2563eb;}
    .hero {padding:0 0 10px; background:transparent; border:0; margin:0;}
    .hero h1 {color:HEADING_INK; font-size:2rem;}
    .hero p {color:SUBTITLE_COLOR !important; text-shadow:0 1px 3px rgba(0,0,0,.25);}
    .status-strip {margin-bottom:4px; padding:12px 16px; background:rgba(255,255,255,.78);}
    [data-baseweb="tab-list"] {background:transparent; border-radius:0; padding:0; gap:28px;}
    [data-baseweb="tab"] {color:HEADING_INK;}
    [data-baseweb="tab"][aria-selected="true"] {color:ACTIVE_COLOR;}
    .st-key-results_panel,.st-key-stack_panel {background:rgba(255,255,255,.82); padding:16px;}
    .focus-card {background:rgba(255,255,255,.82); margin:12px 0;}
    [data-testid="stSidebar"] {background:rgba(237,243,253,.9);}
    @media(max-width:760px) {
      [data-testid="stMainBlockContainer"] {padding:3rem 1rem 1rem;}
      .hero h1 {font-size:1.5rem;}
    }
    </style>
    """.replace("HEADING_INK", "#ffffff" if uri else "#142443")
       .replace("SUBTITLE_COLOR", "#e4edff" if uri else "#526582")
       .replace("ACTIVE_COLOR", "#93c5fd" if uri else "#2563eb")
       .replace("BACKGROUND_VALUE", background), unsafe_allow_html=True)
    # CSS media query follows the viewer's device, not the server's theme.
    theme = st.session_state.get("default_theme", "System") if mode == "Default" else "Light"
    dark_css = """
    .stApp {background:#0d1422 !important; color:#e5edf9; color-scheme:dark;}
    [data-testid="stSidebar"] {background:#141f32 !important; border-color:#334155;}
    [data-testid="stHeader"] {background:#0d1422;}
    .hero h1,.hero p,[data-baseweb="tab"] {color:#e5edf9 !important;}
    .status-strip,.focus-card,.st-key-results_panel,.st-key-stack_panel {
        background:#18243a !important; color:#e5edf9; border-color:#334155;}
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stWidgetLabel"] p {color:#e5edf9;}
    [data-testid="stCaptionContainer"] p {color:#b8c7df !important;}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {color:#e5edf9;}
    [data-testid="stExpander"] details {background:#141f32; border-color:#334155; color:#e5edf9;}
    [data-testid="stFileUploaderDropzone"], [data-baseweb="input"],
    [data-baseweb="base-input"], [data-baseweb="select"] > div {
        background:#1e2d46 !important; color:#e5edf9 !important; border-color:#475569;}
    input {color:#e5edf9 !important; -webkit-text-fill-color:#e5edf9;}
    input::placeholder {color:#b8c7df !important;}
    button[kind="secondary"],button[kind="tertiary"] {
        background:#20304a; color:#e5edf9; border-color:#475569;}
    .badge {background:#233e62; color:#c6ddff;}
    [data-testid="stCode"], [data-testid="stCode"] pre {background:#101a2a !important;}
    [data-testid="stCode"] code {color:#e5edf9 !important;}
    [data-testid="stAlert"] {background:#20304a !important; color:#e5edf9;}
    """
    if theme == "Dark":
        st.markdown("<style>" + dark_css + "</style>", unsafe_allow_html=True)
    elif theme == "System":
        st.markdown("<style>@media(prefers-color-scheme:dark){" + dark_css + "}</style>",
                    unsafe_allow_html=True)
        transparency = st.session_state.get("panel_transparency", 15)
    alpha = 1 - transparency / 100

    panel_css = """
    /* Adjust backgrounds only; keep text and buttons opaque. */
    [data-testid="stSidebar"],
    .status-strip,
    .focus-card,
    .st-key-results_panel,
    .st-key-stack_panel,
    .st-key-empty_panel {
        background: rgba(PANEL_RGB, PANEL_ALPHA) !important;
    }

    /* Remove the solid background around the trace text. */
    [data-testid="stCode"],
    [data-testid="stCode"] > div,
    [data-testid="stCode"] pre,
    [data-testid="stCode"] code {
        background: transparent !important;
        background-color: transparent !important;
    }
    """

    light_css = (
        panel_css
        .replace("PANEL_RGB", "255, 255, 255")
        .replace("PANEL_ALPHA", str(alpha))
    )

    dark_panel_css = (
        panel_css
        .replace("PANEL_RGB", "20, 31, 50")
        .replace("PANEL_ALPHA", str(alpha))
    )

    if theme == "Dark":
        transparency_css = dark_panel_css
    elif theme == "System":
        transparency_css = (
            light_css
            + "@media (prefers-color-scheme: dark) {"
            + dark_panel_css
            + "}"
        )
    else:
        transparency_css = light_css

    st.markdown(
        "<style>" + transparency_css + "</style>",
        unsafe_allow_html=True,
    )

PRESETS = {
    "Mountain woods": "mountain-woods.jpg",
    "Mount Fuji": "mount-fuji.jpg",
    "Cloudy hills": "cloudy-hills.jpg",
}

# --- State Initialization ---
if "search_strings" not in st.session_state:
    st.session_state.search_strings = []
if "processed_lines" not in st.session_state:
    st.session_state.processed_lines = []
if "display_lines" not in st.session_state:
    st.session_state.display_lines = []
if "temp_file_path" not in st.session_state:
    st.session_state.temp_file_path = None
if "is_compressed" not in st.session_state:
    st.session_state.is_compressed = False
if "selected_line" not in st.session_state:
    st.session_state.selected_line = None

BLACKLIST = ["ottstptcserver"]
TARGETS = ["dal.handle.field.error", "__dal.set.message(", "form.text$("]

def add_keyword():
    kw = st.session_state.keyword_input.strip()
    if kw and kw not in st.session_state.search_strings:
        st.session_state.search_strings.append(kw)
    st.session_state.keyword_input = ""

def clear_keywords():
    st.session_state.search_strings = []
    st.session_state.processed_lines = []
    st.session_state.display_lines = []
    st.session_state.selected_line = None

def clear_full_session():
    if st.session_state.temp_file_path and os.path.exists(st.session_state.temp_file_path):
        try:
            os.remove(st.session_state.temp_file_path)
        except Exception:
            pass
    st.session_state.search_strings = []
    st.session_state.processed_lines = []
    st.session_state.display_lines = []
    st.session_state.selected_line = None
    st.session_state.temp_file_path = None
    st.toast("🧹 Server disk space reset successfully!", icon="🗑️")

# --- UI Sidebar Layout ---
with st.sidebar:
    st.header("Trace setup")
    uploaded_file = st.file_uploader("Upload trace file", type=["txt", "gz"])
    st.subheader("Keywords")
    st.text_input("Add keyword or pattern", key="keyword_input", on_change=add_keyword,
                  placeholder="e.g. dal.handle.field.error")
    st.caption("Press Enter to add a keyword.")
    if st.session_state.search_strings:
        st.button("Clear keywords", on_click=clear_keywords)
    if st.session_state.search_strings:
        st.markdown("".join('<span class="badge">' + escape(k) + '</span>'
                            for k in st.session_state.search_strings), unsafe_allow_html=True)
    st.subheader("Filters")
    inc_dal = st.checkbox("DAL filter", value=True)
    inc_depth = st.checkbox("Depth filter", value=False)
    use_ts = st.checkbox("Trim timestamps in stack", value=True,
                         help="Display each stack line starting at its call arrow.")
    analyze_clicked = st.button("Analyze trace", type="primary", width="stretch",
                                disabled=uploaded_file is None)
    st.button("Clear session", on_click=clear_full_session, width="stretch")
    with st.expander("Appearance", expanded=True):
        st.radio("Background", ["Default", "Presets", "Custom"], horizontal=True, key="background_mode")
        if st.session_state.background_mode == "Default":
            st.radio("Theme", ["System", "Light", "Dark"], horizontal=True, key="default_theme")
        elif st.session_state.background_mode == "Presets":
            preset = st.selectbox("Nature preset", list(PRESETS), key="nature_preset")
            preview = Path(__file__).parent / "assets" / PRESETS[preset]
            if preview.exists():
                st.image(str(preview), caption=preset, width="stretch")
        if st.session_state.background_mode == "Custom":
            bg = st.file_uploader("Upload background image", type=["jpg", "jpeg", "png", "webp"],
                                 key=f"background_upload_{st.session_state.get('background_version', 0)}",
                                 help="Up to 10 MB. Used only for your current session.")
            if bg is not None:
                digest = hashlib.sha256(bg.getvalue()).hexdigest()
                if digest != st.session_state.get("background_hash"):
                    try:
                        st.session_state.background_uri = prepare_background(bg)
                        st.session_state.background_hash = digest
                    except Exception as exc:
                        st.session_state.background_uri = ""
                        st.session_state.background_hash = ""
                        st.error(f"Could not use this image: {exc}")
            else:
                st.session_state.background_uri = ""
                st.session_state.background_hash = ""
        if st.session_state.background_mode != "Default":
            st.slider("Dim background", 0, 85, 45, format="%d%%", key="background_dim")
        st.button("Reset appearance", on_click=reset_appearance, width="stretch")
        st.caption("Appearance applies to this session only.")

apply_appearance()
st.markdown('<div class="hero"><h1>Infor LN Trace Debugger</h1>'
            '<p>Search logs and inspect execution stacks</p></div>', unsafe_allow_html=True)

# --- Memory-Safe Disk Spooling Engine ---
if uploaded_file is not None and analyze_clicked:
    status_container = st.sidebar.empty()
    status_container.info("⏳ Spooling file to temporary server storage...")
    
    try:
        uploaded_file.seek(0)  # Allow repeated Analyze clicks on the same upload.
        is_gz = uploaded_file.name.endswith(".gz")
        suffix = ".gz" if is_gz else ".txt"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            first_chunk = True
            while chunk := uploaded_file.read(50 * 1024 * 1024):
                if first_chunk:
                    if chunk.startswith(b'\x1f\x8b'):
                        is_gz = True
                    first_chunk = False
                temp_file.write(chunk)
            st.session_state.temp_file_path = temp_file.name
            st.session_state.is_compressed = is_gz

        status_container.info("⚡ Parsing spooled file line-by-line...")
        
        queries = st.session_state.search_strings
        matches = []
        display_matches = []
        
        open_func = gzip.open if st.session_state.is_compressed else open
        mode = 'rt' if st.session_state.is_compressed else 'r'
        
        with open_func(st.session_state.temp_file_path, mode, encoding="utf-8", errors="ignore") as file:
            file_iter = iter(file)
            for line in file_iter:
                if any(obj in line for obj in BLACKLIST): 
                    continue
                
                has_dal = any(t in line for t in TARGETS)
                has_depth = "-->>" in line and "(depth" in line
                matched_q = next((q for q in queries if q in line), None)
                
                show = False
                if queries:
                    if matched_q:
                        if inc_dal and inc_depth: show = (has_dal or has_depth)
                        elif inc_dal: show = True
                        elif inc_depth: show = has_depth
                        else: show = True
                    if not show and inc_dal and has_dal: show = True
                else:
                    if inc_dal and inc_depth: show = (has_dal and has_depth)
                    elif inc_dal: show = has_dal
                    elif inc_depth: show = has_depth

                if show:
                    clean_line = line.strip()
                    matches.append(clean_line) 
                    
                    if "form.text$" in clean_line:
                        try:
                            next_line = next(file_iter).strip()
                            if "3gl call returned:" in next_line:
                                display_matches.append(next_line)
                            else:
                                display_matches.append(clean_line)
                        except StopIteration:
                            display_matches.append(clean_line)
                    else:
                        display_matches.append(clean_line)

                    if len(matches) >= 50000:
                        st.sidebar.warning("⚠️ UI display capped at 50k lines for stability.")
                        break
                        
        st.session_state.analyzed_name = uploaded_file.name
        st.session_state.processed_lines = matches
        st.session_state.display_lines = display_matches
        st.session_state.selected_line = None  
        status_container.success(f"✅ Finished! Found {len(matches)} rows.")
        
    except Exception as e:
        status_container.error(f"Server Processing Error: {e}")

# --- Render Tabs ---
name = st.session_state.get("analyzed_name") if st.session_state.temp_file_path else None
st.markdown(
    '<div class="status-strip"><strong>' + escape(name or "No trace analyzed") +
    f'</strong><span>{len(st.session_state.display_lines):,} matching rows</span>' +
    ('<span>Ready</span>' if name else '<span>Upload a trace to begin</span>') + '</div>',
    unsafe_allow_html=True,
)
tab_titles = ["Search results", "Call stack"]
tab_main, tab_stack = st.tabs(tab_titles)

with tab_main, st.container(key="results_panel"):
    st.subheader("Search results")
    st.caption("Select a row, then open Call stack to inspect its execution path.")

    if st.session_state.display_lines:
        df = pd.DataFrame({"Filtered Trace Output Logs": st.session_state.display_lines})
        selection_event = st.dataframe(df, width="stretch", height=500, on_select="rerun", selection_mode="single-row")
        
        if selection_event and selection_event.selection and selection_event.selection.rows:
            selected_row_idx = selection_event.selection.rows[0]
            chosen_line = st.session_state.processed_lines[selected_row_idx]
            
            if st.session_state.selected_line != chosen_line:
                st.session_state.selected_line = chosen_line
                st.rerun()
    else:
        st.info("Upload a trace dump log into the web browser and click run to trigger extraction.")

with tab_stack:
    if st.session_state.selected_line and st.session_state.temp_file_path:
        selected_line = st.session_state.selected_line
        
        if "(depth" in selected_line:

            
            session_match = re.search(r':::\(\d+\):', selected_line)
            session_id = session_match.group(0) if session_match else None
            
            try:
                target_depth_str = selected_line.split("(depth")[1].split(")")[0].strip()
                target_depth = int(target_depth_str)
            except ValueError:
                target_depth = 0

            process_label = re.search(r"\d+", session_id).group(0) if session_id else "Unknown"
            function_match = re.search(r"\(depth\s+\d+\):\s*([^\(]+)", selected_line)
            function_label = function_match.group(1).strip() if function_match else selected_line
            st.markdown('<div class="focus-card"><strong>Selected call</strong><br>'
                        f'<span class="badge">{escape(function_label)}</span>'
                        f'<span class="badge">Process {escape(process_label)}</span>'
                        f'<span class="badge">Depth {target_depth}</span></div>', unsafe_allow_html=True)

            if target_depth > 0:
                stack_map = {}
                open_func = gzip.open if st.session_state.is_compressed else open
                mode = 'rt' if st.session_state.is_compressed else 'r'
                
                try:
                    # Freshly open the file handle right here during the tab display phase
                    with open_func(st.session_state.temp_file_path, mode, encoding="utf-8", errors="ignore") as file:
                        for line in file:
                            clean_line = line.strip()
                            
                            if session_id and session_id not in clean_line:
                                continue
                                
                            if "-->>" in clean_line and "(depth" in clean_line and "(in object" in clean_line:
                                if not any(obj in clean_line for obj in BLACKLIST):
                                    try:
                                        curr_depth = int(clean_line.split("(depth")[1].split(")")[0].strip())
                                        stack_map[curr_depth] = clean_line
                                    except ValueError:
                                        pass
                            
                            # Break early if we hit the exact line we clicked on
                            if selected_line in clean_line:
                                break
                    
                    valid_depths = sorted([d for d in stack_map.keys() if d <= target_depth])
                    stack_output = []
                    for d in valid_depths:
                        line_text = stack_map[d]
                        if use_ts and "-->>" in line_text:
                            line_text = line_text[line_text.find("-->>"):]
                        stack_output.append(line_text.strip())
                    
                    if stack_output:
                        stack_text = "\n\n".join(stack_output)
                    
                        with st.container(key="stack_panel"):
                            title_col, download_col = st.columns([3, 1], vertical_alignment="center")
                            with title_col:
                                st.subheader("Call stack")
                            with download_col:
                                with st.container(horizontal=True, horizontal_alignment="right"):
                                    st.download_button("Download stack", stack_text, file_name="trace_stack.txt",
                                                       mime="text/plain", on_click="ignore")
                            st.code(stack_text, language=None, line_numbers=False,
                                    wrap_lines=False, height=400)
                            st.caption("Use the copy icon at the top-right of the trace to copy the full stack.")
                    else:
                        st.info("No matching trace tree elements discovered leading up to this point.")
                except Exception as e:
                    st.error(f"Snapshot building error: {e}")
        else:
            st.warning("⚠️ Selected entry line item lacks structured calling depth markers `(depth X)`.")
    else:
        st.info("Select a row in Search results to view its call stack here.")
