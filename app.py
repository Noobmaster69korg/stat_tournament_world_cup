import streamlit as st
import sqlite3
import pandas as pd
import json
import requests
from bs4 import BeautifulSoup
from itertools import combinations
import os
import io
import glob
import subprocess
import re

# --- 1. DATABASE & CONNECTION MANAGER ---
# Scraped datasets are now named (one .db file per name) instead of a single
# shared 'scraped_stats.db'. Each browser tab picks its own "Active Dataset"
# in its own session_state, so two tabs can independently work on e.g. Test
# stats and ODI stats at the same time without stomping on each other.
LOCAL_DB_FILE = 'cricket_stats.db'
RESERVED_NAMES = {"Local"}

def safe_dataset_name(raw):
    """Sanitize a user-typed dataset name into a safe filename stem."""
    name = "".join(c for c in raw.strip() if c.isalnum() or c in ("_", "-"))
    name = name or "scraped_stats"
    if name in RESERVED_NAMES:
        name = f"{name}_data"
    return name

def list_scraped_datasets():
    """All named scraped datasets currently on disk (excludes the local DB)."""
    names = []
    for f in glob.glob("*.db"):
        stem = f[:-3]
        if f == LOCAL_DB_FILE or stem in RESERVED_NAMES:
            continue
        names.append(stem)
    return sorted(names)

def get_db_info():
    """Returns (connection, time_column_name) for THIS tab's active dataset selection."""
    active = st.session_state.get("active_dataset", "Local")
    if active != "Local":
        path = f"{active}.db"
        if os.path.exists(path):
            return sqlite3.connect(path, check_same_thread=False), "Year"
        # Dataset was deleted (e.g. by another tab) since this tab last checked.
        st.session_state.active_dataset = "Local"
    return sqlite3.connect(LOCAL_DB_FILE, check_same_thread=False), "Season"

# --- 1.4 GIT PERSISTENCE HELPERS ---
# Streamlit Cloud's disk is ephemeral: anything written at runtime (a built or
# uploaded .db file) is wiped whenever the app sleeps/restarts/redeploys.
# The only way for a dataset to survive that is to actually be committed into
# the GitHub repo the app deploys from (exactly like cricket_stats.db already
# is). These helpers commit/remove a dataset file via git + push, using a
# GitHub token supplied through Streamlit's secrets (Settings -> Secrets):
#
#   GITHUB_TOKEN = "ghp_xxx..."      # a token with 'repo' write access
#   GITHUB_REPO  = "username/repo"   # the repo this app deploys from
#   GITHUB_BRANCH = "main"           # optional, defaults to "main"
#
# NOTE: pushing a new commit will make Streamlit Cloud auto-redeploy the app
# shortly after (that's how Streamlit Cloud detects repo changes) - the app
# will briefly restart, which is expected.
def _git_creds():
    token = st.secrets.get("GITHUB_TOKEN") if hasattr(st, "secrets") else None
    repo = st.secrets.get("GITHUB_REPO") if hasattr(st, "secrets") else None
    branch = st.secrets.get("GITHUB_BRANCH", "main") if hasattr(st, "secrets") else "main"
    return token, repo, branch

def git_is_tracked(path):
    """True if this file is already committed in the repo (i.e. already permanent)."""
    try:
        result = subprocess.run(["git", "ls-files", "--error-unmatch", path], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def _git_run(args):
    return subprocess.run(["git"] + args, capture_output=True, text=True)

def make_dataset_permanent(path, message):
    """Commits + pushes a dataset file to GitHub so it survives restarts forever."""
    token, repo, branch = _git_creds()
    if not token or not repo:
        return False, "Missing GITHUB_TOKEN / GITHUB_REPO in this app's Secrets (Settings -> Secrets on Streamlit Cloud)."
    try:
        _git_run(["config", "user.email", "app@streamlit.local"])
        _git_run(["config", "user.name", "Cricket Stats App"])
        _git_run(["add", path])
        commit = _git_run(["commit", "-m", message])
        if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr):
            return False, commit.stderr or commit.stdout
        remote_url = f"https://{token}@github.com/{repo}.git"
        push = _git_run(["push", remote_url, f"HEAD:{branch}"])
        if push.returncode != 0:
            return False, push.stderr or push.stdout
        return True, "Committed and pushed. The app will redeploy shortly to reflect this."
    except Exception as e:
        return False, str(e)

def remove_dataset_permanently(path, message):
    """Removes a dataset file from the repo on GitHub (undoes make_dataset_permanent)."""
    token, repo, branch = _git_creds()
    if not token or not repo:
        return False, "Missing GITHUB_TOKEN / GITHUB_REPO in this app's Secrets (Settings -> Secrets on Streamlit Cloud)."
    try:
        _git_run(["config", "user.email", "app@streamlit.local"])
        _git_run(["config", "user.name", "Cricket Stats App"])
        _git_run(["rm", "--cached", path])
        commit = _git_run(["commit", "-m", message])
        if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr):
            return False, commit.stderr or commit.stdout
        remote_url = f"https://{token}@github.com/{repo}.git"
        push = _git_run(["push", remote_url, f"HEAD:{branch}"])
        if push.returncode != 0:
            return False, push.stderr or push.stdout
        return True, "Removed from GitHub and pushed. The app will redeploy shortly."
    except Exception as e:
        return False, str(e)

# --- 1.5 CUSTOMIZABLE METRIC CONFIG ---
# Instead of hardcoding Runs/Ave/SR (batting) and Wkts/Ave/Econ (bowling), the
# user picks any 3 columns per discipline plus a direction for each. Every SQL
# builder below is driven purely by this config.

DEFAULT_BAT_METRICS = [
    {"col": "Runs", "direction": "higher_better"},
    {"col": "Ave", "direction": "higher_better"},
    {"col": "SR", "direction": "higher_better"},
]
DEFAULT_BOWL_METRICS = [
    {"col": "Wkts", "direction": "higher_better"},
    {"col": "Ave", "direction": "lower_better"},
    {"col": "Econ", "direction": "lower_better"},
]
LOWER_BETTER_HINTS = ("ave", "econ", "sr", "rpo", "average", "economy")

def guess_direction(col, discipline):
    """Best-effort default so the UI doesn't start every column as 'higher is
    better'. The user can always override via the radio button."""
    if discipline == "bowling" and any(k in col.lower() for k in LOWER_BETTER_HINTS):
        return "lower_better"
    return "higher_better"

def get_table_columns(conn, table):
    """Numeric-ish columns available in a table, excluding identifiers."""
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except Exception:
        return []
    cols = []
    for r in rows:
        name, decl_type = r[1], (r[2] or "").upper()
        if name in ("Player", "Season", "Year"):
            continue
        if any(t in decl_type for t in ("CHAR", "TEXT", "CLOB")):
            continue
        cols.append(name)
    return cols

def q_col(col):
    """Bracket-quote a column name so odd identifiers (e.g. '4s', '100') are safe in SQL."""
    return f"[{col}]"

def metric_picker(prefix, avail_cols, defaults, discipline_for_guess):
    """Renders 3 (column, direction) pickers and returns the chosen metric config."""
    if len(avail_cols) < 3:
        st.error(f"'{discipline_for_guess}' table needs at least 3 numeric columns to configure metrics. Found: {avail_cols}")
        return defaults
    metrics, chosen_so_far = [], []
    cols_ui = st.columns(3)
    for i in range(3):
        with cols_ui[i]:
            default_col = defaults[i]['col'] if i < len(defaults) and defaults[i]['col'] in avail_cols else avail_cols[i % len(avail_cols)]
            idx = avail_cols.index(default_col) if default_col in avail_cols else 0
            col_choice = st.selectbox(f"Metric {i+1}", avail_cols, index=idx, key=f"{prefix}_col_{i}")
            default_dir = next((d['direction'] for d in defaults if d['col'] == col_choice), None)
            if default_dir is None:
                default_dir = guess_direction(col_choice, discipline_for_guess)
            dir_choice = st.radio(
                "Direction", ["Higher is better", "Lower is better"],
                index=0 if default_dir == "higher_better" else 1,
                key=f"{prefix}_dir_{i}", horizontal=True,
            )
            metrics.append({"col": col_choice, "direction": "higher_better" if dir_choice == "Higher is better" else "lower_better"})
            chosen_so_far.append(col_choice)
    if len(set(chosen_so_far)) < 3:
        st.warning("You've selected the same column more than once — comparisons involving it will be redundant.")
    return metrics

def build_case_sql(metrics, thresholds, op):
    """Generic Wins/Ties/Losses/Meets SQL fragment vs. fixed threshold values.
    op: 'win' (strictly better), 'tie' (exactly equal), 'loss' (strictly worse),
        'meets' (>=/<= threshold, used for 'consistency' style checks)."""
    parts = []
    for m, t in zip(metrics, thresholds):
        col, higher = m['col'], m['direction'] == 'higher_better'
        if op == 'tie':
            cmp = '='
        elif op == 'win':
            cmp = '>' if higher else '<'
        elif op == 'loss':
            cmp = '<' if higher else '>'
        elif op == 'meets':
            cmp = '>=' if higher else '<='
        else:
            raise ValueError(f"Unknown op: {op}")
        parts.append(f"(CASE WHEN {q_col(col)} {cmp} {t} THEN 1 ELSE 0 END)")
    return " + ".join(parts)

def build_pairwise_sql(metrics, alias_a, alias_b, op):
    """Generic row-vs-row (e.g. A.Runs > B.Runs) SQL fragment. op: 'win' or 'loss'."""
    parts = []
    for m in metrics:
        col, higher = m['col'], m['direction'] == 'higher_better'
        cmp = ('>' if higher else '<') if op == 'win' else ('<' if higher else '>')
        parts.append(f"(CASE WHEN {alias_a}.{q_col(col)} {cmp} {alias_b}.{q_col(col)} THEN 1 ELSE 0 END)")
    return "(" + " + ".join(parts) + ")"

def compare_rows(row_a, row_b, metrics):
    """Python-side equivalent of build_pairwise_sql, for the Format Analysis loops."""
    wins = 0
    for m in metrics:
        col, higher = m['col'], m['direction'] == 'higher_better'
        va, vb = row_a[col], row_b[col]
        if (higher and va > vb) or ((not higher) and va < vb):
            wins += 1
    return wins

# --- 1.6 YEAR / COUNTRY FILTERING ---
# Neither table has a dedicated Country column - it's baked into the player
# name as a trailing code (e.g. "SL Malinga SL", "Umar Gul PAK"). We detect it
# heuristically and only surface the country filter when the dataset actually
# looks like it follows that convention.
def extract_year_num(val):
    """Pulls a 4-digit year out of a Season/Year value (handles '2019', '2019/20', etc.)."""
    m = re.search(r"(\d{4})", str(val))
    return int(m.group(1)) if m else None

def extract_country(player_name):
    """Best-effort: the last whitespace-separated token of the player name."""
    if not isinstance(player_name, str) or not player_name.strip():
        return "Unknown"
    tokens = player_name.strip().split()
    return tokens[-1].upper() if tokens else "Unknown"

def country_filter_is_meaningful(all_players, max_distinct=40):
    """If almost every player has a 'unique country', it's not really a country
    code - it's just their surname. Only offer the filter when the number of
    distinct suffixes is small relative to typical country-code counts."""
    if not all_players:
        return False, []
    codes = sorted(set(extract_country(p) for p in all_players))
    return (len(codes) <= max_distinct), codes

def build_filtered_connection(raw_conn, t_col, year_range, countries):
    """Reads batting/bowling from raw_conn, applies year/country filters, and
    returns a NEW in-memory connection with tables of the SAME names
    ('batting'/'bowling') - so every existing query elsewhere in the app keeps
    working unchanged against this filtered view."""
    bat_df = pd.read_sql("SELECT * FROM batting", raw_conn)
    bowl_df = pd.read_sql("SELECT * FROM bowling", raw_conn)

    for df in (bat_df, bowl_df):
        df['__year_num'] = df[t_col].apply(extract_year_num)
        df['__country'] = df['Player'].apply(extract_country)

    y_min, y_max = year_range
    bat_df = bat_df[bat_df['__year_num'].notna() & bat_df['__year_num'].between(y_min, y_max)]
    bowl_df = bowl_df[bowl_df['__year_num'].notna() & bowl_df['__year_num'].between(y_min, y_max)]

    if countries:
        bat_df = bat_df[bat_df['__country'].isin(countries)]
        bowl_df = bowl_df[bowl_df['__country'].isin(countries)]

    bat_df = bat_df.drop(columns=['__year_num', '__country'])
    bowl_df = bowl_df.drop(columns=['__year_num', '__country'])

    mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
    bat_df.to_sql("batting", mem_conn, index=False)
    bowl_df.to_sql("bowling", mem_conn, index=False)
    return mem_conn

# --- 2. ROBUST PAGINATED SCRAPER (Always creates 'Year' column) ---
def scrape_full_cricinfo(base_url, discipline):
    all_data = []
    page = 1
    progress_container = st.sidebar.empty()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    while True:
        url = f"{base_url};page={page}"
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200: break
            tables = pd.read_html(io.StringIO(response.text))
            df_page = None
            for t in tables:
                if 'Player' in t.columns:
                    df_page = t
                    break
            if df_page is None or df_page.empty: break

            if 'Span' in df_page.columns: df_page = df_page.rename(columns={'Span': 'Year'})
            if 'Player' not in df_page.columns or 'Year' not in df_page.columns: break

            # Keep every usable column from the page (not just a fixed subset)
            # so any of them can later be picked as a comparison metric.
            drop_like = [c for c in df_page.columns if str(c).lower().startswith('unnamed')]
            df_final = df_page.drop(columns=drop_like, errors='ignore').copy()
            df_final['Player'] = df_final['Player'].str.replace(r'[^\w\s]', '', regex=True).str.strip()
            all_data.append(df_final)
            progress_container.info(f"Scraped {discipline} Page {page}...")
            if len(df_page) < 50: break
            page += 1
            if page > 40: break
        except Exception:
            break

    if not all_data: return None
    full_df = pd.concat(all_data, ignore_index=True)
    for col in full_df.columns:
        if col in ("Player", "Year"): continue
        full_df[col] = pd.to_numeric(full_df[col], errors='coerce').fillna(0)
    return full_df

# --- 3. GLOBAL HELPERS ---
st.set_page_config(page_title="Cricket Stats Engine", layout="wide")

def fmt(count, total):
    if total <= 0: return "0 (0.0%)"
    perc = (count * 100.0 / total)
    return f"{int(count)} ({perc:.1f}%)"

def get_profile_label(w, t, l):
    if w == 3: return "🏆 Beat all 3 categories"
    if w == 2 and t == 1: return "⭐ Beat 2 categories, Tied 1 category"
    if w == 2 and l == 1: return "✅ Beat 2 categories, Lost 1 category"
    return "Other combinations"

def display_styled_results(df, title_prefix):
    if df is None or df.empty:
        st.warning("No players found matching these criteria.")
        return
    df['Result_Profile'] = df.apply(lambda r: get_profile_label(r['WinsA'], r['TiesA'], r['LossesA']), axis=1)
    st.subheader(f"📊 Summary ({title_prefix})")
    for profile, count in df['Result_Profile'].value_counts().items():
        st.write(f"- **{count}** records: {profile}")
    st.divider()
    st.subheader("📋 Respective Lists")
    for profile in sorted(df['Result_Profile'].unique(), reverse=True):
        cols_to_drop = ['WinsA', 'TiesA', 'LossesA', 'Result_Profile']
        if 'WinsB' in df.columns: cols_to_drop.append('WinsB')
        if 'TiesB' in df.columns: cols_to_drop.append('TiesB')
        st.markdown(f"#### {profile}")
        st.dataframe(df[df['Result_Profile'] == profile].drop(columns=cols_to_drop), use_container_width=True, hide_index=True)

# --- 4. SIDEBAR CONFIG ---
st.sidebar.title("🌐 Live Data Bridge")
if "active_dataset" not in st.session_state: st.session_state.active_dataset = "Local"

dataset_options = ["Local"] + list_scraped_datasets()
if st.session_state.active_dataset not in dataset_options:
    st.session_state.active_dataset = "Local"  # dataset vanished (deleted elsewhere) - fall back safely

st.session_state.active_dataset = st.sidebar.selectbox(
    "📂 Active Dataset (this tab only)",
    dataset_options,
    index=dataset_options.index(st.session_state.active_dataset),
)

if st.session_state.active_dataset == "Local":
    st.sidebar.info("🏠 Active: Local Database (uses 'Season')")
else:
    st.sidebar.success(f"🟢 Active: '{st.session_state.active_dataset}' (uses 'Year')")

st.sidebar.divider()
st.sidebar.caption("Build a new dataset")
b_link = st.sidebar.text_input("ESPN Batting Link")
w_link = st.sidebar.text_input("ESPN Bowling Link")
dataset_name_input = st.sidebar.text_input("Dataset Name", placeholder="e.g. Test_2024, ODI_AUS_series")

if st.sidebar.button("🚀 Build DB"):
    if b_link and w_link:
        safe_name = safe_dataset_name(dataset_name_input)
        with st.spinner(f"Building '{safe_name}'..."):
            b_df = scrape_full_cricinfo(b_link, "batting")
            w_df = scrape_full_cricinfo(w_link, "bowling")
            if b_df is not None and w_df is not None:
                tmp_conn = sqlite3.connect(f"{safe_name}.db")
                b_df.to_sql('batting', tmp_conn, index=False, if_exists='replace')
                w_df.to_sql('bowling', tmp_conn, index=False, if_exists='replace')
                tmp_conn.close()
                st.session_state.active_dataset = safe_name  # this tab switches straight to it
                st.rerun()
            else:
                st.sidebar.error("Scraping failed — check the links and try again.")
    else:
        st.sidebar.warning("Paste both links before building.")

st.sidebar.divider()
active_db_path = LOCAL_DB_FILE if st.session_state.active_dataset == "Local" else f"{st.session_state.active_dataset}.db"
active_is_tracked = st.session_state.active_dataset == "Local" or (os.path.exists(active_db_path) and git_is_tracked(active_db_path))

st.sidebar.caption("📌 Make the active dataset permanent (commits it to GitHub — survives sleeps/restarts forever, until deleted)")
if st.session_state.active_dataset == "Local":
    st.sidebar.caption("Local database is already permanent — it's already in the repo.")
elif not os.path.exists(active_db_path):
    st.sidebar.caption("Nothing built for the active dataset yet.")
elif active_is_tracked:
    st.sidebar.success(f"'{st.session_state.active_dataset}' is already permanent.")
else:
    if st.sidebar.button(f"📌 Make '{st.session_state.active_dataset}' Permanent"):
        ok, msg = make_dataset_permanent(active_db_path, f"Add dataset: {st.session_state.active_dataset}")
        (st.sidebar.success if ok else st.sidebar.error)(msg)

st.sidebar.divider()
st.sidebar.caption("Delete the currently active dataset")
confirm_delete = st.sidebar.checkbox("Confirm delete", key="confirm_delete_active_dataset")
also_remove_github = False
if st.session_state.active_dataset != "Local" and active_is_tracked:
    also_remove_github = st.sidebar.checkbox("Also remove permanently from GitHub (can't be undone)", key="also_remove_github")
if st.sidebar.button("🗑️ Delete Active Dataset"):
    active = st.session_state.active_dataset
    if active == "Local":
        st.sidebar.warning("The Local database can't be deleted here.")
    elif not confirm_delete:
        st.sidebar.warning("Tick 'Confirm delete' first — this removes the file for every tab using it.")
    else:
        path = f"{active}.db"
        if also_remove_github:
            ok, msg = remove_dataset_permanently(path, f"Remove dataset: {active}")
            if not ok:
                st.sidebar.error(msg)
        if os.path.exists(path): os.remove(path)
        st.session_state.active_dataset = "Local"
        st.rerun()

st.sidebar.divider()
st.sidebar.caption("💾 Download a local copy (works with or without GitHub secrets configured)")
if os.path.exists(active_db_path):
    with open(active_db_path, "rb") as _f:
        st.sidebar.download_button(
            f"⬇️ Download '{st.session_state.active_dataset}'",
            data=_f.read(),
            file_name=os.path.basename(active_db_path),
            mime="application/octet-stream",
        )
else:
    st.sidebar.caption("Nothing to download for the active dataset yet.")

st.sidebar.divider()
st.sidebar.caption("⬆️ Restore a dataset you downloaded earlier")
uploaded_db = st.sidebar.file_uploader("Upload a .db file", type=["db"], key="dataset_uploader")
if uploaded_db is not None:
    default_upload_name = os.path.splitext(uploaded_db.name)[0]
    upload_name_input = st.sidebar.text_input("Save as (dataset name)", value=default_upload_name, key="upload_name_input")
    if st.sidebar.button("💾 Save Uploaded Dataset"):
        safe_name = safe_dataset_name(upload_name_input)
        with open(f"{safe_name}.db", "wb") as _f:
            _f.write(uploaded_db.getbuffer())
        st.session_state.active_dataset = safe_name
        st.rerun()

# --- 5. AUTH ---
st.title("🏏 Player Stats & Analytics Engine")
password = st.text_input("Enter Password", type="password")
if password != "qcc_stat_tourno":
    st.error("Access Denied.")
    st.stop()

# --- 6. NAV & STATE ---
if "nav_choice" not in st.session_state: st.session_state.nav_choice = "Batting Milestones"
if "squad_a" not in st.session_state: st.session_state.squad_a, st.session_state.squad_b = [], []
if "bat_metrics" not in st.session_state: st.session_state.bat_metrics = DEFAULT_BAT_METRICS.copy()
if "bowl_metrics" not in st.session_state: st.session_state.bowl_metrics = DEFAULT_BOWL_METRICS.copy()

conn, t_col = get_db_info()  # t_col is either 'Season' or 'Year'
raw_conn = conn  # unfiltered handle - metric config & filter-option detection read from this

with st.expander("⚙️ Configure Comparison Metrics (3 fields per discipline)", expanded=False):
    st.caption("Pick any 3 numeric fields from each table as the comparison criteria, and whether higher or lower is better for each. Everything below (Milestones, Analytics, Squad tools, Format Analysis) uses this config.")
    st.markdown("**Batting**")
    avail_bat_cols = get_table_columns(raw_conn, "batting")
    st.session_state.bat_metrics = metric_picker("bat", avail_bat_cols, st.session_state.bat_metrics, "batting")
    st.markdown("**Bowling**")
    avail_bowl_cols = get_table_columns(raw_conn, "bowling")
    st.session_state.bowl_metrics = metric_picker("bowl", avail_bowl_cols, st.session_state.bowl_metrics, "bowling")

with st.expander("🎯 Filter This Dataset (Year Range & Countries)", expanded=False):
    _all_players_df = pd.read_sql("SELECT Player FROM batting UNION SELECT Player FROM bowling", raw_conn)
    _all_years_bat = pd.read_sql(f"SELECT {t_col} as yr FROM batting", raw_conn)['yr']
    _all_years_bowl = pd.read_sql(f"SELECT {t_col} as yr FROM bowling", raw_conn)['yr']
    _year_nums = pd.concat([_all_years_bat, _all_years_bowl]).apply(extract_year_num).dropna()

    if _year_nums.empty:
        st.caption("Couldn't detect year values in this dataset — year filter unavailable.")
        year_range = (0, 9999)
    else:
        y_lo, y_hi = int(_year_nums.min()), int(_year_nums.max())
        if y_lo == y_hi:
            st.caption(f"This dataset only spans {y_lo} — nothing to range-filter.")
            year_range = (y_lo, y_hi)
        else:
            year_range = st.slider(
                "Year range", min_value=y_lo, max_value=y_hi, value=(y_lo, y_hi),
                key=f"year_range_{st.session_state.active_dataset}",
            )

    show_country_filter, detected_countries = country_filter_is_meaningful(_all_players_df['Player'].tolist())
    if show_country_filter:
        selected_countries = st.multiselect(
            "Countries (leave empty = all)", detected_countries, default=[],
            key=f"country_filter_{st.session_state.active_dataset}",
        )
    else:
        st.caption("Player names in this dataset don't look like they carry a country code, so country filtering isn't available here.")
        selected_countries = []

    filters_active = (_year_nums.empty is False and year_range != (int(_year_nums.min()), int(_year_nums.max()))) or bool(selected_countries)
    if filters_active:
        st.caption(f"✅ Filter active — {year_range[0]}–{year_range[1]}" + (f", countries: {', '.join(selected_countries)}" if selected_countries else ", all countries"))

if not _year_nums.empty:
    conn = build_filtered_connection(raw_conn, t_col, year_range, selected_countries)

nav_options = ["Batting Milestones", "Bowling Milestones", "📈 Player Analytics", "👤 Player Details", "🏟️ Squad Comparison", "🧬 Format Analysis"]
st.session_state.nav_choice = st.radio("Navigate:", nav_options, index=nav_options.index(st.session_state.nav_choice), horizontal=True)
st.divider()

# --- MILESTONES (shared by Batting & Bowling tabs) ---
def render_milestones_tab(conn, t_col, table, metrics):
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True, key=f"{table}_fmode")
    thresholds_key = f"{table}_thresholds"
    metric_cols = {m['col'] for m in metrics}
    if thresholds_key not in st.session_state or set(st.session_state[thresholds_key].keys()) != metric_cols:
        st.session_state[thresholds_key] = {m['col']: 0.0 for m in metrics}

    c1, c2 = st.columns(2)
    thresholds_a, thresholds_b = [], []
    with c1:
        st.caption("Set A")
        for m in metrics:
            label = f"{'Min' if m['direction']=='higher_better' else 'Max'} {m['col']} (A)"
            val = st.number_input(label, value=float(st.session_state[thresholds_key].get(m['col'], 0.0)), key=f"{table}_A_{m['col']}")
            st.session_state[thresholds_key][m['col']] = val
            thresholds_a.append(val)
    with c2:
        st.caption("Set B")
        for m in metrics:
            label = f"{'Min' if m['direction']=='higher_better' else 'Max'} {m['col']} (B)"
            val = st.number_input(label, value=0.0, key=f"{table}_B_{m['col']}")
            thresholds_b.append(val)

    select_cols = ", ".join(q_col(m['col']) for m in metrics)
    wins_a = build_case_sql(metrics, thresholds_a, 'win')
    ties_a = build_case_sql(metrics, thresholds_a, 'tie')
    losses_a = build_case_sql(metrics, thresholds_a, 'loss')
    wins_b = build_case_sql(metrics, thresholds_b, 'win')
    ties_b = build_case_sql(metrics, thresholds_b, 'tie')
    first = metrics[0]
    order_dir = "DESC" if first['direction'] == 'higher_better' else "ASC"
    q = f"""
        WITH Base AS (
            SELECT Player, {t_col} as Year, {select_cols},
                   ({wins_a}) as WinsA, ({ties_a}) as TiesA, ({losses_a}) as LossesA,
                   ({wins_b}) as WinsB, ({ties_b}) as TiesB
            FROM {table}
        )
        SELECT * FROM Base
        WHERE (WinsA + TiesA) >= 2 {"AND (WinsB + TiesB) >= 2" if "BOTH" in f_mode else ""}
        ORDER BY WinsA DESC, {q_col(first['col'])} {order_dir}
    """
    display_styled_results(pd.read_sql(q, conn), table.capitalize())

# --- TAB 1 & 2: MILESTONES ---
if st.session_state.nav_choice == "Batting Milestones":
    render_milestones_tab(conn, t_col, "batting", st.session_state.bat_metrics)

elif st.session_state.nav_choice == "Bowling Milestones":
    render_milestones_tab(conn, t_col, "bowling", st.session_state.bowl_metrics)

# --- TAB 3: ANALYTICS ---
elif st.session_state.nav_choice == "📈 Player Analytics":
    choice = st.radio("Type:", ["Career Consistency", "Global Rankings"], horizontal=True)
    disc = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True).lower()
    metrics = st.session_state.bat_metrics if disc == "batting" else st.session_state.bowl_metrics
    if "Consistency" in choice:
        cols_ui = st.columns(3)
        thresholds = []
        for i, m in enumerate(metrics):
            label = f"{'Min' if m['direction']=='higher_better' else 'Max'} {m['col']}"
            val = cols_ui[i].number_input(label, value=0.0, key=f"cons_{disc}_{m['col']}")
            thresholds.append(val)
        meets_sql = build_case_sql(metrics, thresholds, 'meets')
        q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ({meets_sql}) >= 2 THEN 1 ELSE 0 END) as Successful FROM {disc} GROUP BY Player HAVING Successful > 0"
        df = pd.read_sql(q, conn)
        df['Win %'] = (df['Successful'] * 100 / df['Total']).round(2)
        st.dataframe(df.sort_values("Win %", ascending=False), use_container_width=True, hide_index=True)
    else:
        win = build_pairwise_sql(metrics, "A", "B", "win")
        loss = build_pairwise_sql(metrics, "A", "B", "loss")
        q = f"SELECT A.Player, A.{t_col} as Year, (SELECT COUNT(*) FROM {disc}) as TR, (SELECT COUNT(*) FROM {disc} B WHERE {win} >= 2) as WC, (SELECT COUNT(*) FROM {disc} B WHERE {loss} >= 2) as LC FROM {disc} A"
        df = pd.read_sql(q, conn)
        df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR'] - 1), axis=1)
        df['Losses'] = df.apply(lambda r: fmt(r['LC'], r['TR'] - 1), axis=1)
        df['Ties'] = df.apply(lambda r: fmt(r['TR'] - r['WC'] - r['LC'] - 1, r['TR'] - 1), axis=1)
        st.dataframe(df.sort_values("WC", ascending=False)[['Player', 'Year', 'Wins %', 'Losses', 'Ties']], use_container_width=True, hide_index=True)

# --- TAB 4: DETAILS ---
elif st.session_state.nav_choice == "👤 Player Details":
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    target = st.selectbox("Select Player", all_p)
    if target:
        for t, lab in [("batting", "Batting"), ("bowling", "Bowling")]:
            metrics = st.session_state.bat_metrics if t == "batting" else st.session_state.bowl_metrics
            cols_sql = ", ".join(q_col(m['col']) for m in metrics)
            win = build_pairwise_sql(metrics, "A", "B", "win")
            loss = build_pairwise_sql(metrics, "A", "B", "loss")
            q = f"SELECT A.{t_col} as Year, {cols_sql}, (SELECT COUNT(*) FROM {t}) as TR, (SELECT COUNT(*) FROM {t} B WHERE {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE {loss} >= 2) as LC FROM {t} A WHERE A.Player = '{target}'"
            df = pd.read_sql(q, conn)
            if not df.empty:
                st.subheader(lab)
                df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR'] - 1), axis=1)
                df['Losses %'] = df.apply(lambda r: fmt(r['LC'], r['TR'] - 1), axis=1)
                df['Ties %'] = df.apply(lambda r: fmt(r['TR'] - r['WC'] - r['LC'] - 1, r['TR'] - 1), axis=1)
                evt = st.dataframe(df.drop(columns=['TR', 'WC', 'LC']), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key=f"det_scr_{t}")
                if evt.selection.rows:
                    sel = df.iloc[evt.selection.rows[0]]
                    thresholds_key = f"{t}_thresholds"
                    st.session_state.setdefault(thresholds_key, {})
                    for m in metrics:
                        st.session_state[thresholds_key][m['col']] = sel[m['col']]
                    st.session_state.nav_choice = "Batting Milestones" if t == "batting" else "Bowling Milestones"
                    st.rerun()

# --- TAB 5: SQUAD ---
elif st.session_state.nav_choice == "🏟️ Squad Comparison":
    with st.expander("🛠️ Manage Squads"):
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Clear Squads"): st.session_state.squad_a, st.session_state.squad_b = [], []; st.rerun()
        c2.text_input("📋 Squad Code", value=json.dumps({"a": st.session_state.squad_a, "b": st.session_state.squad_b}))
        load = st.text_input("📥 Paste Code:")
        if st.button("🔄 Execute Load") and load:
            try: d = json.loads(load); st.session_state.squad_a, st.session_state.squad_b = d.get('a', []), d.get('b', []); st.rerun()
            except Exception: st.error("ERR")
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    c1, c2 = st.columns(2)
    with c1:
        n = st.selectbox("Add to A", [""] + all_p, key="sqa"); (st.session_state.squad_a.append(n), st.rerun()) if n and n not in st.session_state.squad_a else None
        st.session_state.squad_a = st.multiselect("Squad A", st.session_state.squad_a, default=st.session_state.squad_a)
    with c2:
        n = st.selectbox("Add to B", [""] + all_p, key="sqb"); (st.session_state.squad_b.append(n), st.rerun()) if n and n not in st.session_state.squad_b else None
        st.session_state.squad_b = st.multiselect("Squad B", st.session_state.squad_b, default=st.session_state.squad_b)

    if st.session_state.squad_a and st.session_state.squad_b:
        sub = st.radio("Mode:", ["Individual Benchmark", "Squad Pairwise"], horizontal=True)
        if sub == "Individual Benchmark":
            d_dir = st.radio("Direction:", ["Squad A ➡️ B", "Squad B ➡️ A"], horizontal=True)
            src, trg = (st.session_state.squad_a, st.session_state.squad_b) if "A ➡️" in d_dir else (st.session_state.squad_b, st.session_state.squad_a)
            p = st.selectbox("Pick Benchmark Player:", src, key=f"sq_p_sel_{d_dir}_{len(src)}")
            if p:
                b_y = pd.read_sql(f"SELECT {t_col} as Year FROM batting WHERE Player='{p}'", conn)['Year'].tolist()
                w_y = pd.read_sql(f"SELECT {t_col} as Year FROM bowling WHERE Player='{p}'", conn)['Year'].tolist()
                disc = st.radio("Type:", (["Batting"] if b_y else []) + (["Bowling"] if w_y else []), horizontal=True)
                y = st.selectbox("Year:", b_y if disc == "Batting" else w_y)
                if y:
                    table = "batting" if disc == "Batting" else "bowling"
                    metrics = st.session_state.bat_metrics if disc == "Batting" else st.session_state.bowl_metrics
                    bench = pd.read_sql(f"SELECT * FROM {table} WHERE Player='{p}' AND {t_col}='{y}'", conn).iloc[0]
                    st.info(f"📍 Benchmark: {p} ({y})")
                    met_cols = st.columns(len(metrics))
                    thresholds = []
                    for i, m in enumerate(metrics):
                        val = bench[m['col']]
                        met_cols[i].metric(m['col'], val)
                        thresholds.append(val)
                    target_str = "('" + "','".join(trg) + "')"
                    select_cols = ", ".join(q_col(m['col']) for m in metrics)
                    wins_a = build_case_sql(metrics, thresholds, 'win')
                    ties_a = build_case_sql(metrics, thresholds, 'tie')
                    losses_a = build_case_sql(metrics, thresholds, 'loss')
                    q = f"""
                        SELECT Player, {t_col} as Year, {select_cols},
                               ({wins_a}) as WinsA, ({ties_a}) as TiesA, ({losses_a}) as LossesA
                        FROM {table} WHERE Player IN {target_str}
                        ORDER BY WinsA DESC
                    """
                    display_styled_results(pd.read_sql(q, conn), f"Against {p}")
        else:
            t_disc = st.radio("Choose Discipline:", ["Batting", "Bowling"], horizontal=True).lower()
            metrics = st.session_state.bat_metrics if t_disc == "batting" else st.session_state.bowl_metrics
            a_l = "('" + "','".join(st.session_state.squad_a) + "')"
            b_l = "('" + "','".join(st.session_state.squad_b) + "')"
            win = build_pairwise_sql(metrics, "A", "B", "win")
            loss = build_pairwise_sql(metrics, "A", "B", "loss")
            c1, c2 = st.columns(2)
            with c1:
                st.write("Squad A vs B")
                q_a = f"SELECT A.Player, A.{t_col} as Year, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_l}) as TR, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_l} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_l} AND {loss} >= 2) as LC FROM {t_disc} A WHERE A.Player IN {a_l}"
                df_a = pd.read_sql(q_a, conn)
                df_a['Wins'] = df_a.apply(lambda r: fmt(r['WC'], r['TR']), axis=1)
                df_a['Losses'] = df_a.apply(lambda r: fmt(r['LC'], r['TR']), axis=1)
                df_a['Ties'] = df_a.apply(lambda r: fmt(r['TR'] - r['WC'] - r['LC'], r['TR']), axis=1)
                st.dataframe(df_a[['Player', 'Year', 'Wins', 'Losses', 'Ties']], hide_index=True)
            with c2:
                st.write("Squad B vs A")
                q_b = f"SELECT A.Player, A.{t_col} as Year, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {a_l}) as TR, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {a_l} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {a_l} AND {loss} >= 2) as LC FROM {t_disc} A WHERE A.Player IN {b_l}"
                df_b = pd.read_sql(q_b, conn)
                df_b['Wins'] = df_b.apply(lambda r: fmt(r['WC'], r['TR']), axis=1)
                df_b['Losses'] = df_b.apply(lambda r: fmt(r['LC'], r['TR']), axis=1)
                df_b['Ties'] = df_b.apply(lambda r: fmt(r['TR'] - r['WC'] - r['LC'], r['TR']), axis=1)
                st.dataframe(df_b[['Player', 'Year', 'Wins', 'Losses', 'Ties']], hide_index=True)

# --- TAB 6: FORMAT ANALYSIS ---
elif st.session_state.nav_choice == "🧬 Format Analysis":
    sub6 = st.radio("Feature:", ["🛡️ Unbeatable", "🔍 Group Killers"], horizontal=True)
    t = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True, key="disc_fa").lower()
    metrics = st.session_state.bat_metrics if t == "batting" else st.session_state.bowl_metrics
    pl = sorted(pd.read_sql(f"SELECT DISTINCT Player FROM {t}", conn)['Player'].tolist())
    if "Unbeatable" in sub6:
        cx1, cx2 = st.columns(2)
        with cx1: o1 = st.multiselect("Omit Pool:", pl, key="om1")
        with cx2: o2 = st.multiselect("Omit Check:", pl, key="om2")
        k_v = st.radio("Size (K):", [1, 2, 3], horizontal=True)
        if st.button("🚀 Find"):
            with st.spinner("Analyzing..."):
                df_f = pd.read_sql(f"SELECT * FROM {t}", conn); df_k = df_f[~df_f['Player'].isin(o2)]; cand = [p for p in pl if p not in o1]
                if not cand: st.error("No players.")
                else:
                    kill_sets = []
                    for _, rx in df_k.iterrows():
                        beaten = set()
                        for pn in cand:
                            py = df_f[df_f['Player'] == pn]; b = 0
                            for _, rp in py.iterrows():
                                if compare_rows(rx, rp, metrics) >= 2: b += 1
                            if b == len(py): beaten.add(pn)
                        kill_sets.append(beaten)
                    res = []
                    for combo in combinations(cand, k_v):
                        cs = set(combo); unb = True
                        for ks in kill_sets:
                            if cs.issubset(ks): unb = False; break
                        if unb: res.append(list(combo))
                    if res: st.dataframe(pd.DataFrame(res, columns=[f"P{i+1}" for i in range(k_v)]), hide_index=True)
                    else: st.error("None found.")
    else:
        target = st.multiselect("Select Group:", pl)
        if st.button("🔎 Find Killers"):
            if target:
                df_full = pd.read_sql(f"SELECT * FROM {t}", conn); kl = []
                for _, rx in df_full.iterrows():
                    e = True
                    for pn in target:
                        py = df_full[df_full['Player'] == pn]; pb = True
                        for _, rp in py.iterrows():
                            if compare_rows(rx, rp, metrics) < 2: pb = False; break
                        if not pb: e = False; break
                    if e: kl.append(rx)
                if kl: st.dataframe(pd.DataFrame(kl).rename(columns={t_col: 'Year'}), hide_index=True)
                else: st.error("No killers.")

conn.close()
if raw_conn is not conn:
    raw_conn.close()
