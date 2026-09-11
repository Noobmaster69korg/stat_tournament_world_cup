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
    return name or "scraped_stats"

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
st.sidebar.caption("Delete the currently active dataset")
confirm_delete = st.sidebar.checkbox("Confirm delete", key="confirm_delete_active_dataset")
if st.sidebar.button("🗑️ Delete Active Dataset"):
    active = st.session_state.active_dataset
    if active == "Local":
        st.sidebar.warning("The Local database can't be deleted here.")
    elif not confirm_delete:
        st.sidebar.warning("Tick 'Confirm delete' first — this removes the file for every tab using it.")
    else:
        path = f"{active}.db"
        if os.path.exists(path): os.remove(path)
        st.session_state.active_dataset = "Local"
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

with st.expander("⚙️ Configure Comparison Metrics (3 fields per discipline)", expanded=False):
    st.caption("Pick any 3 numeric fields from each table as the comparison criteria, and whether higher or lower is better for each. Everything below (Milestones, Analytics, Squad tools, Format Analysis) uses this config.")
    st.markdown("**Batting**")
    avail_bat_cols = get_table_columns(conn, "batting")
    st.session_state.bat_metrics = metric_picker("bat", avail_bat_cols, st.session_state.bat_metrics, "batting")
    st.markdown("**Bowling**")
    avail_bowl_cols = get_table_columns(conn, "bowling")
    st.session_state.bowl_metrics = metric_picker("bowl", avail_bowl_cols, st.session_state.bowl_metrics, "bowling")

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
