import streamlit as st
import gzip
import os
import tempfile
import pandas as pd
import re

# --- Page Configuration & Theme Styling ---
st.set_page_config(
    page_title="Infor LN Enterprise Trace Debugger",
    page_icon="🔍",
    layout="wide"
)

st.markdown("""
    <style>
    [data-testid="stDataFrame"] td {
        font-family: 'Consolas', 'Courier New', monospace !important;
        font-size: 13px !important;
        white-space: pre !important;
    }
    .stTextArea textarea {
        font-family: 'Consolas', 'Courier New', monospace !important;
        font-size: 13px !important;
        white-space: pre !important;
        overflow-x: auto !important;
    }
    [data-testid="stDataFrame"] tr:hover {
        cursor: pointer;
    }
    </style>
""", unsafe_allow_html=True)

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
    st.header("Public Server Engine")
    st.caption("Processes heavy trace dumps safely using temporary local disk spooling.")
    st.markdown("---")
    
    st.subheader("1. Data Source")
    uploaded_file = st.file_uploader("Upload Heavy Trace File (.txt, .gz)", type=["txt", "gz"])
    
    st.markdown("---")
    st.subheader("2. Search Configuration")
    st.text_input("Add keyword or pattern:", key="keyword_input", on_change=add_keyword)
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        st.button("Add String", on_click=add_keyword, width="stretch")
    with col_btn2:
        st.button("Clear Keywords", on_click=clear_keywords, width="stretch")
        
    if st.session_state.search_strings:
        st.write("**Active Rules:**")
        st.info(" | ".join(st.session_state.search_strings))

    st.markdown("---")
    st.subheader("3. Core Filters")
    inc_dal = st.checkbox("DAL Filter", value=True)
    inc_depth = st.checkbox("Depth Filter", value=False)
    use_ts = st.checkbox("Has Timestamps (Truncate in Stack)", value=True)

    st.button("🔴 Clear Session Data (Delete File)", on_click=clear_full_session, width="stretch")
    st.markdown("---")
    analyze_clicked = st.button("⚡ Run Web Stream Processor", type="primary", width="stretch")

# --- Memory-Safe Disk Spooling Engine ---
if uploaded_file is not None and analyze_clicked:
    status_container = st.sidebar.empty()
    status_container.info("⏳ Spooling file to temporary server storage...")
    
    try:
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
                        
        st.session_state.processed_lines = matches
        st.session_state.display_lines = display_matches
        st.session_state.selected_line = None  
        status_container.success(f"✅ Finished! Found {len(matches)} rows.")
        
    except Exception as e:
        status_container.error(f"Server Processing Error: {e}")

# --- Render Tabs ---
tab_titles = ["📋 Main Search Results", "🥞 Reconstructed Stack Trace"]
tab_main, tab_stack = st.tabs(tab_titles)

with tab_main:
    st.title("Infor LN Trace Engine")
    st.markdown("---")

    if st.session_state.display_lines:
        df = pd.DataFrame({"Filtered Trace Output Logs": st.session_state.display_lines})
        selection_event = st.dataframe(df, width="stretch", height=500, on_select="rerun", selection_mode="single-row")
        
        if selection_event and selection_event.selection and selection_event.selection.rows:
            selected_row_idx = selection_event.selection.rows[0]
            chosen_line = st.session_state.processed_lines[selected_row_idx]
            
            if st.session_state.selected_line != chosen_line:
                st.session_state.selected_line = chosen_line
                st.markdown('<script>window.parent.document.querySelectorAll("[data-baseweb=\'tab\']")[1].click();</script>', unsafe_allow_html=True)
                st.rerun()
    else:
        st.info("Upload a trace dump log into the web browser and click run to trigger extraction.")

with tab_stack:
    if st.session_state.selected_line and st.session_state.temp_file_path:
        selected_line = st.session_state.selected_line
        
        if "(depth" in selected_line:
            st.markdown(f"### 🥞 Session-Isolated Call Path Map")
            st.warning(f"📍 **Focused Log Target:** {selected_line}")
            
            session_match = re.search(r':::\(\d+\):', selected_line)
            session_id = session_match.group(0) if session_match else None
            
            try:
                target_depth_str = selected_line.split("(depth")[1].split(")")[0].strip()
                target_depth = int(target_depth_str)
            except ValueError:
                target_depth = 0

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
                        st.text_area("Reconstructed Trace Call Sequence Output", value="\n\n".join(stack_output), height=550)
                    else:
                        st.info("No matching trace tree elements discovered leading up to this point.")
                except Exception as e:
                    st.error(f"Snapshot building error: {e}")
        else:
            st.warning("⚠️ Selected entry line item lacks structured calling depth markers `(depth X)`.")
    else:
        st.info("Go to 'Main Search Results' and click directly on a trace line item log row to view its tree hierarchy.")
