import streamlit as st
import sqlite3
import pandas as pd
import json
import requests
import io
import time
import os
from itertools import combinations

# --- 1. DATABASE & CONNECTION MANAGER ---
LOCAL_DB_FILE = 'cricket_stats.db'
SCRAPED_DB_FILE = 'scraped_stats.db'

def get_connection():
    """Returns a fresh connection to the active database."""
    if st.session_state.get("use_scraped", False) and os.path.exists(SCRAPED_DB_FILE):
        return sqlite3.connect(SCRAPED_DB_FILE, check_same_thread=False)
    return sqlite3.connect(LOCAL_DB_FILE, check_same_thread=False)

# --- 2. ROBUST PAGINATED SCRAPER (Based on your provided snippet) ---
def fetch_cricinfo_data(base_url, stat_type):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
    all_data = []
    page = 1
    progress_container = st.sidebar.empty()

    while True:
        url = f"{base_url};page={page}"
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200: break
            
            # Use io.StringIO to parse the HTML table safely
            tables = pd.read_html(io.StringIO(response.text), match="Player")
            if not tables: break
            df = tables[0]
            
            # Clean header rows and empty rows
            df = df.dropna(subset=['Player'])
            df = df[df['Player'] != 'Player']
            if df.empty: break
            
            # Standardize columns to match the app's internal naming
            if 'Span' in df.columns: df = df.rename(columns={'Span': 'Season'})
            
            if stat_type == "batting":
                df = df[['Player', 'Season', 'Runs', 'Ave', 'SR']].copy()
            else:
                df = df[['Player', 'Season', 'Wkts', 'Ave', 'Econ']].copy()
            
            # Clean Player names and fix data types
            df['Player'] = df['Player'].str.replace(r'[^\w\s]', '', regex=True).str.strip()
            for col in df.columns[2:]:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            all_data.append(df)
            progress_container.info(f"Scraping {stat_type}: Page {page}...")
            
            if len(df) < 50 or page >= 30: break # Check if last page
            page += 1
            time.sleep(0.2)
        except Exception as e:
            st.sidebar.error(f"Error on page {page}: {e}")
            break

    if not all_data: return None
    return pd.concat(all_data, ignore_index=True)

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
st.sidebar.title("⚙️ Database Controls")
if "use_scraped" not in st.session_state: st.session_state.use_scraped = False

if st.session_state.use_scraped:
    st.sidebar.success("🟢 Status: Live Scraped Data Active")
else:
    st.sidebar.info("🏠 Status: Default Local DB Active")

custom_bat = st.sidebar.text_input("ESPN Batting Link")
custom_bowl = st.sidebar.text_input("ESPN Bowling Link")

c_sb1, c_sb2 = st.sidebar.columns(2)
if c_sb1.button("🚀 Build DB"):
    if custom_bat and custom_bowl:
        with st.spinner("Rebuilding database from links..."):
            b_df = fetch_cricinfo_data(custom_bat, "batting")
            w_df = fetch_cricinfo_data(custom_bowl, "bowling")
            if b_df is not None and w_df is not None:
                tmp = sqlite3.connect(SCRAPED_DB_FILE)
                b_df.to_sql('batting', tmp, index=False, if_exists='replace')
                w_df.to_sql('bowling', tmp, index=False, if_exists='replace')
                tmp.close()
                st.session_state.use_scraped = True
                st.rerun()

if c_sb2.button("🗑️ Reset"):
    st.session_state.use_scraped = False
    st.rerun()

# --- 5. AUTH ---
st.title("🏏 World Cup Player Stats & Analytics")
password = st.text_input("Enter Password", type="password")
if password != "long live martell":
    st.error("Access Denied.")
    st.stop()

# --- 6. NAVIGATION & STATE ---
if "nav_choice" not in st.session_state: st.session_state.nav_choice = "Batting Milestones"
benchmark_keys = ["bat_r", "bat_a", "bat_s", "bowl_w", "bowl_a", "bowl_e"]
for k in benchmark_keys:
    if k not in st.session_state: st.session_state[k] = 300 if "r" in k else 40.0 if "a" in k else 90.0 if "s" in k else 15
if "squad_a" not in st.session_state: st.session_state.squad_a, st.session_state.squad_b = [], []

nav_options = ["Batting Milestones", "Bowling Milestones", "📈 Player Analytics", "👤 Player Details", "🏟️ Squad Comparison", "🧬 Format Analysis"]
st.session_state.nav_choice = st.radio("Navigate:", nav_options, index=nav_options.index(st.session_state.nav_choice), horizontal=True)
st.divider()

conn = get_connection()

# --- TAB 1: BATTING ---
if st.session_state.nav_choice == "Batting Milestones":
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        tr = st.number_input("Min Runs (A)", value=st.session_state.bat_r)
        ta = st.number_input("Min Average (A)", value=st.session_state.bat_a)
        ts = st.number_input("Min SR (A)", value=st.session_state.bat_s)
        st.session_state.bat_r, st.session_state.bat_a, st.session_state.bat_s = tr, ta, ts
    with c2:
        trb, tab, tsb = st.number_input("Min Runs (B)", 500), st.number_input("Min Average (B)", 50.0), st.number_input("Min SR (B)", 100.0)
    q = f"WITH Base AS (SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta} THEN 1 ELSE 0 END + CASE WHEN SR > {ts} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta} THEN 1 ELSE 0 END + CASE WHEN SR = {ts} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta} THEN 1 ELSE 0 END + CASE WHEN SR < {ts} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Runs > {trb} THEN 1 ELSE 0 END + CASE WHEN Ave > {tab} THEN 1 ELSE 0 END + CASE WHEN SR > {tsb} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Runs = {trb} THEN 1 ELSE 0 END + CASE WHEN Ave = {tab} THEN 1 ELSE 0 END + CASE WHEN SR = {tsb} THEN 1 ELSE 0 END) as TiesB FROM batting) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''} ORDER BY WinsA DESC, Runs DESC"
    display_styled_results(pd.read_sql(q, conn), "Batting")

# --- TAB 2: BOWLING ---
elif st.session_state.nav_choice == "Bowling Milestones":
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        tw = st.number_input("Min Wickets (A)", value=st.session_state.bowl_w)
        ta = st.number_input("Max Average (A)", value=st.session_state.bowl_a)
        te = st.number_input("Max Economy (A)", value=st.session_state.bowl_e)
        st.session_state.bowl_w, st.session_state.bowl_a, st.session_state.bowl_e = tw, ta, te
    with c2:
        twb, tab, teb = st.number_input("Min Wickets (B)", 20), st.number_input("Max Avg (B)", 20.0), st.number_input("Max Econ (B)", 4.5)
    q = f"WITH Base AS (SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {tw} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta} THEN 1 ELSE 0 END + CASE WHEN Econ < {te} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {tw} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta} THEN 1 ELSE 0 END + CASE WHEN Econ = {te} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {tw} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta} THEN 1 ELSE 0 END + CASE WHEN Econ > {te} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Wkts > {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Wkts = {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as TiesB FROM bowling) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''} ORDER BY WinsA DESC, Wickets DESC"
    display_styled_results(pd.read_sql(q, conn), "Bowling")

# --- TAB 3: ANALYTICS ---
elif st.session_state.nav_choice == "📈 Player Analytics":
    choice = st.radio("Type:", ["Career Consistency", "Global Rankings"], horizontal=True)
    t = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True).lower()
    if "Consistency" in choice:
        c1, c2, c3 = st.columns(3)
        if t == "batting":
            r, a, s = c1.number_input("Min Runs", 250), c2.number_input("Min Avg", 35.0), c3.number_input("Min SR", 85.0)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Runs >= {r}) + (Ave >= {a}) + (SR >= {s})) >= 2 THEN 1 ELSE 0 END) as Successful FROM batting GROUP BY Player HAVING Successful > 0"
        else:
            w, av, e = c1.number_input("Min Wkts", 12), c2.number_input("Max Avg", 28.0), c3.number_input("Max Econ", 5.5)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Wkts >= {w}) + (Ave <= {av}) + (Econ <= {e})) >= 2 THEN 1 ELSE 0 END) as Successful FROM bowling GROUP BY Player HAVING Successful > 0"
        df = pd.read_sql(q, conn); df['Win %'] = (df['Successful']*100/df['Total']).round(2)
        st.dataframe(df.sort_values("Win %", ascending=False), use_container_width=True, hide_index=True)
    else:
        win = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
        loss = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"
        q = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t}) as TR, (SELECT COUNT(*) FROM {t} B WHERE {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE {loss} >= 2) as LC FROM {t} A"
        df = pd.read_sql(q, conn); df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR']-1), axis=1); df['Losses'] = df.apply(lambda r: fmt(r['LC'], r['TR']-1), axis=1); df['Ties'] = df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC']-1, r['TR']-1), axis=1)
        st.dataframe(df.sort_values("WC", ascending=False)[['Player', 'Season', 'Wins %', 'Losses', 'Ties']], use_container_width=True, hide_index=True)

# --- TAB 4: PLAYER DETAILS ---
elif st.session_state.nav_choice == "👤 Player Details":
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    target = st.selectbox("Select Player", all_p)
    if target:
        for t, lab in [("batting", "Batting"), ("bowling", "Bowling")]:
            cols = "Runs, Ave, SR" if t == "batting" else "Wkts, Ave, Econ"
            win = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
            loss = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"
            q = f"SELECT A.Season, {cols}, (SELECT COUNT(*) FROM {t}) as TR, (SELECT COUNT(*) FROM {t} B WHERE {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE {loss} >= 2) as LC, (SELECT COUNT(*) FROM {t} B WHERE {'B.Runs > A.Runs AND B.Ave > A.Ave AND B.SR > A.SR' if t=='batting' else 'B.Wkts > A.Wkts AND B.Ave < A.Ave AND B.Econ < A.Econ'}) as CL FROM {t} A WHERE A.Player = '{target}'"
            df = pd.read_sql(q, conn)
            if not df.empty:
                st.subheader(lab); df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR']-1), axis=1); df['Losses %'] = df.apply(lambda r: fmt(r['LC'], r['TR']-1), axis=1); df['Ties %'] = df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC']-1, r['TR']-1), axis=1)
                evt = st.dataframe(df.drop(columns=['TR','WC','LC']), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key=f"det_{t}")
                if evt.selection.rows:
                    sel = df.iloc[evt.selection.rows[0]]
                    if t == "batting": st.session_state.bat_r, st.session_state.bat_a, st.session_state.bat_s, st.session_state.nav_choice = sel['Runs'], sel['Ave'], sel['SR'], "Batting Milestones"
                    else: st.session_state.bowl_w, st.session_state.bowl_a, st.session_state.bowl_e, st.session_state.nav_choice = sel['Wkts'], sel['Ave'], sel['Econ'], "Bowling Milestones"
                    st.rerun()

# --- TAB 5: SQUAD ---
elif st.session_state.nav_choice == "🏟️ Squad Comparison":
    with st.expander("🛠️ Manage Squads"):
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Clear Squads"): st.session_state.squad_a, st.session_state.squad_b = [], []; st.rerun()
        c2.text_input("📋 Squad Code", value=json.dumps({"a": st.session_state.squad_a, "b": st.session_state.squad_b}))
        load = st.text_input("📥 Load Code:"); ( (d := json.loads(load)), st.session_state.__setitem__('squad_a', d.get('a', [])), st.session_state.__setitem__('squad_b', d.get('b', [])), st.rerun() ) if st.button("🔄 Go") and load else None
    
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    c1, c2 = st.columns(2)
    with c1:
        n = st.selectbox("Add Player to A", [""]+all_p, key="sqa_a"); (st.session_state.squad_a.append(n), st.rerun()) if n and n not in st.session_state.squad_a else None
        st.session_state.squad_a = st.multiselect("Squad A", st.session_state.squad_a, default=st.session_state.squad_a)
    with c2:
        n = st.selectbox("Add Player to B", [""]+all_p, key="sqb_b"); (st.session_state.squad_b.append(n), st.rerun()) if n and n not in st.session_state.squad_b else None
        st.session_state.squad_b = st.multiselect("Squad B", st.session_state.squad_b, default=st.session_state.squad_b)

    if st.session_state.squad_a and st.session_state.squad_b:
        sub = st.radio("Mode:", ["Individual Benchmark", "Squad Standings"], horizontal=True)
        if sub == "Individual Benchmark":
            d_dir = st.radio("Direction:", ["Squad A Benchmark ➡️ B", "Squad B Benchmark ➡️ A"], horizontal=True)
            src, trg = (st.session_state.squad_a, st.session_state.squad_b) if "A Benchmark" in d_dir else (st.session_state.squad_b, st.session_state.squad_a)
            p = st.selectbox("Pick Benchmark Player:", src, key=f"sq_p_sel_{d_dir}_{len(src)}")
            if p:
                b_y, w_y = pd.read_sql(f"SELECT Season FROM batting WHERE Player='{p}'", conn)['Season'].tolist(), pd.read_sql(f"SELECT Season FROM bowling WHERE Player='{p}'", conn)['Season'].tolist()
                disc = st.radio("Type:", (["Batting"] if b_y else []) + (["Bowling"] if w_y else []), horizontal=True)
                y = st.selectbox("Year:", b_y if disc == "Batting" else w_y)
                if y:
                    bench = pd.read_sql(f"SELECT * FROM {'batting' if disc=='Batting' else 'bowling'} WHERE Player='{p}' AND Season='{y}'", conn).iloc[0]
                    st.info(f"📍 Benchmark Details: {p} ({y})")
                    met = st.columns(3)
                    if disc == "Batting":
                        tr, ta, ts = bench['Runs'], bench['Ave'], bench['SR']
                        met[0].metric("Runs", tr); met[1].metric("Avg", ta); met[2].metric("SR", ts)
                        q = f"SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta} THEN 1 ELSE 0 END + CASE WHEN SR > {ts} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta} THEN 1 ELSE 0 END + CASE WHEN SR = {ts} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta} THEN 1 ELSE 0 END + CASE WHEN SR < {ts} THEN 1 ELSE 0 END) as LossesA FROM batting WHERE Player IN ('" + "','".join(trg) + "') ORDER BY WinsA DESC"
                    else:
                        tw, tav, te = bench['Wkts'], bench['Ave'], bench['Econ']
                        met[0].metric("Wkts", tw); met[1].metric("Avg", tav); met[2].metric("Econ", te)
                        q = f"SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {tw} THEN 1 ELSE 0 END + CASE WHEN Ave < {tav} THEN 1 ELSE 0 END + CASE WHEN Econ < {te} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {tw} THEN 1 ELSE 0 END + CASE WHEN Ave < {tav} THEN 1 ELSE 0 END + CASE WHEN Econ = {te} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {tw} THEN 1 ELSE 0 END + CASE WHEN Ave > {tav} THEN 1 ELSE 0 END + CASE WHEN Econ > {te} THEN 1 ELSE 0 END) as LossesA FROM bowling WHERE Player IN ('" + "','".join(trg) + "') ORDER BY WinsA DESC"
                    display_styled_results(pd.read_sql(q, conn), f"Against {p}")
        else:
            t_disc = st.radio("Choose Discipline:", ["Batting", "Bowling"], horizontal=True).lower()
            a_l = "('" + "','".join(st.session_state.squad_a) + "')"; b_l = "('" + "','".join(st.session_state.squad_b) + "')"
            win_l = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if t_disc == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
            loss_l = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if t_disc == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"
            c1, c2 = st.columns(2)
            with c1:
                st.write("Squad A vs B")
                q_a = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_l}) as TR, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_l} AND {win_l} >= 2) as WC, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_l} AND {loss_l} >= 2) as LC FROM {t_disc} A WHERE A.Player IN {a_l}"
                df_a = pd.read_sql(q_a, conn); df_a['Wins'], df_a['Losses'], df_a['Ties'] = df_a.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df_a.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df_a.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                st.dataframe(df_a[['Player', 'Season', 'Wins', 'Losses', 'Ties']], hide_index=True)
            with c2:
                st.write("Squad B vs A")
                q_b = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {a_l}) as TR, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_l} AND {win_l} >= 2) as WC, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {a_l} AND {loss_l} >= 2) as LC FROM {t_disc} A WHERE A.Player IN {b_l}"
                df_b = pd.read_sql(q_b, conn); df_b['Wins'], df_b['Losses'], df_b['Ties'] = df_b.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df_b.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df_b.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                st.dataframe(df_b[['Player', 'Season', 'Wins', 'Losses', 'Ties']], hide_index=True)

# --- TAB 6: FORMAT ANALYSIS ---
elif st.session_state.nav_choice == "🧬 Format Analysis":
    sub6 = st.radio("Feature:", ["🛡️ Unbeatable Combinations", "🔍 Group Killers"], horizontal=True)
    t = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True, key="disc_fa_u").lower()
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
                            py = df_f[df_f['Player']==pn]; b = 0
                            for _, rp in py.iterrows():
                                if t=="batting": w = int(rx['Runs']>rp['Runs'])+int(rx['Ave']>rp['Ave'])+int(rx['SR']>rp['SR'])
                                else: w = int(rx['Wkts']>rp['Wkts'])+int(rx['Ave']<rp['Ave'])+int(rx['Econ']<rp['Econ'])
                                if w >= 2: b += 1
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
        if st.button("🔎 Find Group Killers"):
            if target:
                df_full = pd.read_sql(f"SELECT * FROM {t}", conn); kl = []
                for _, rx in df_full.iterrows():
                    e = True
                    for pn in target:
                        py = df_full[df_full['Player']==pn]; pb = True
                        for _, rp in py.iterrows():
                            if t=="batting": w = int(rx['Runs']>rp['Runs'])+int(rx['Ave']>rp['Ave'])+int(rx['SR']>rp['SR'])
                            else: w = int(rx['Wkts']>rp['Wkts'])+int(rx['Ave']<rp['Ave'])+int(rx['Econ']<rp['Econ'])
                            if w < 2: pb = False; break
                        if not pb: e = False; break
                    if e: kl.append(rx)
                if kl: st.dataframe(pd.DataFrame(kl), use_container_width=True, hide_index=True)
                else: st.error("No killers found.")

conn.close()
