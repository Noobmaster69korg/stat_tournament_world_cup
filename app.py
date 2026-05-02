import streamlit as st
import sqlite3
import pandas as pd
import json
import requests
from bs4 import BeautifulSoup
from itertools import combinations

# --- 1. ISOLATED SCRAPER LOGIC ---
def scrape_cricinfo_to_df(url, discipline):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Cricinfo stats engine tables use class 'engineTable'
        table = soup.find_all('table', class_='engineTable')
        
        target_table = None
        for t in table:
            if 'Player' in t.get_text():
                target_table = t
                break
        if not target_table:
            return None

        rows = []
        # Target rows with class 'data1' (standard stats rows)
        for tr in target_table.find_all('tr', class_='data1'):
            cells = tr.find_all('td')
            if len(cells) > 10:
                rows.append([c.get_text().strip() for c in cells])
        
        raw_df = pd.DataFrame(rows)
        
        # Cricinfo Table Indices for view=year:
        # 0: Player, 1: Span (Year), 5: Runs/Wkts, 7/8: Ave, 9: SR/Econ
        if discipline == "batting":
            df = raw_df[[0, 1, 5, 7, 9]].copy()
            df.columns = ['Player', 'Season', 'Runs', 'Ave', 'SR']
        else:
            df = raw_df[[0, 1, 6, 8, 9]].copy()
            df.columns = ['Player', 'Season', 'Wkts', 'Ave', 'Econ']
            
        # Cleanup: Remove symbols from names, convert numbers
        df['Player'] = df['Player'].str.replace(r'[^\w\s]', '', regex=True).str.strip()
        for col in df.columns[2:]:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        return df
    except Exception as e:
        st.sidebar.error(f"Scraper Error: {e}")
        return None

# --- 2. GLOBAL CONFIG & HELPERS ---
st.set_page_config(page_title="Cricket Stats Engine", layout="wide")

def fmt(count, total):
    if total <= 0: return "0 (0.0%)"
    perc = (count * 100.0 / total)
    return f"{int(count)} ({perc:.1f}%)"

def get_profile_label(w, t, l):
    if w == 3: return "🏆 Beat all 3 categories"
    if w == 2 and t == 1: return "⭐ Beat 2 categories, Tied 1 category"
    if w == 2 and l == 1: return "✅ Beat 2 categories, Lost 1 category"
    return "Other"

def display_styled_results(df, title_prefix):
    if df.empty:
        st.warning("No players found matching these criteria.")
        return
    df['Result_Profile'] = df.apply(lambda row: get_profile_label(row['WinsA'], row['TiesA'], row['LossesA']), axis=1)
    st.subheader(f"📊 Summary of Milestones ({title_prefix})")
    for profile, count in df['Result_Profile'].value_counts().items():
        st.write(f"- **{count}** records: {profile}")
    st.divider()
    st.subheader("📋 Respective Lists by Category")
    for profile in sorted(df['Result_Profile'].unique(), reverse=True):
        cols_to_drop = ['WinsA', 'TiesA', 'LossesA', 'Result_Profile']
        if 'WinsB' in df.columns: cols_to_drop.append('WinsB')
        if 'TiesB' in df.columns: cols_to_drop.append('TiesB')
        st.markdown(f"#### {profile}")
        st.dataframe(df[df['Result_Profile'] == profile].drop(columns=cols_to_drop), use_container_width=True, hide_index=True)

# --- 3. DYNAMIC DATABASE ENGINE (SEGREGATED) ---
if "use_custom" not in st.session_state: st.session_state.use_custom = False

st.sidebar.title("🌐 Live Data Bridge")
st.sidebar.info("Paste ESPN links to temporarily override the database.")
custom_bat_url = st.sidebar.text_input("Batting Link")
custom_bowl_url = st.sidebar.text_input("Bowling Link")

col_s1, col_s2 = st.sidebar.columns(2)
if col_s1.button("🚀 Build Engine"):
    if custom_bat_url and custom_bowl_url:
        with st.spinner("Processing Scrape..."):
            b_df = scrape_cricinfo_to_df(custom_bat_url, "batting")
            w_df = scrape_cricinfo_to_df(custom_bowl_url, "bowling")
            if b_df is not None and w_df is not None:
                # Create a persistent in-memory DB for the session
                tmp_conn = sqlite3.connect(':memory:', check_same_thread=False)
                b_df.to_sql('batting', tmp_conn, index=False)
                w_df.to_sql('bowling', tmp_conn, index=False)
                st.session_state.custom_conn = tmp_conn
                st.session_state.use_custom = True
                st.sidebar.success("Custom DB Ready!")
                st.rerun()

if col_s2.button("🏠 Restore Default"):
    st.session_state.use_custom = False
    st.sidebar.info("Reverted to Local DB")
    st.rerun()

# Determine active connection
if st.session_state.use_custom:
    conn = st.session_state.custom_conn
    st.sidebar.write("Status: 🟢 **Scraped Data Active**")
else:
    conn = sqlite3.connect('cricket_stats.db', check_same_thread=False)
    st.sidebar.write("Status: 🏠 **Local Database Active**")

# --- 4. EXISTING APP FEATURES (UNTOUCHED) ---
st.title("🏏 Player Stats & Analytics")
password = st.text_input("Enter Password to Access", type="password")
if password != "long live martell":
    st.error("Access Denied.")
    st.stop()

if "nav_choice" not in st.session_state: st.session_state.nav_choice = "Batting Milestones"
benchmark_keys = ["bat_runs_a", "bat_avg_a", "bat_sr_a", "bowl_w_a", "bowl_a_a", "bowl_e_a"]
for k in benchmark_keys:
    if k not in st.session_state: st.session_state[k] = 300 if "runs" in k else 40.0 if "avg" in k else 90.0 if "sr" in k else 15 if "w" in k else 25.0 if "a_a" in k else 5.0
if "squad_a" not in st.session_state: st.session_state.squad_a, st.session_state.squad_b = [], []

nav_options = ["Batting Milestones", "Bowling Milestones", "📈 Player Analytics", "👤 Player Details", "🏟️ Squad Comparison", "🧬 Format Analysis"]
st.session_state.nav_choice = st.radio("Navigate:", nav_options, index=nav_options.index(st.session_state.nav_choice), horizontal=True)
st.divider()

# TAB 1: BATTING
if st.session_state.nav_choice == "Batting Milestones":
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        tr1a = st.number_input("Min Runs (A)", value=st.session_state.bat_runs_a)
        ta1a = st.number_input("Min Average (A)", value=st.session_state.bat_avg_a)
        ts1a = st.number_input("Min SR (A)", value=st.session_state.bat_sr_a)
        st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = tr1a, ta1a, ts1a
    with c2:
        tr1b, ta1b, ts1b = st.number_input("Min Runs (B)", 500), st.number_input("Min Average (B)", 50.0), st.number_input("Min Strike Rate (B)", 100.0)
    q = f"WITH Base AS (SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1a} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1a} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR < {ts1a} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Runs > {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1b} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Runs = {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1b} THEN 1 ELSE 0 END) as TiesB FROM batting) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''} ORDER BY WinsA DESC, Runs DESC"
    display_styled_results(pd.read_sql(q, conn), "Batting")

# TAB 2: BOWLING
elif st.session_state.nav_choice == "Bowling Milestones":
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        twa = st.number_input("Min Wickets (A)", value=st.session_state.bowl_w_a)
        taa = st.number_input("Max Average (A)", value=st.session_state.bowl_a_a)
        tea = st.number_input("Max Economy (A)", value=st.session_state.bowl_e_a)
        st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = twa, taa, tea
    with c2:
        twb, tab, teb = st.number_input("Min Wkts (B)", 20), st.number_input("Max Average (B)", 20.0), st.number_input("Max Economy (B)", 4.5)
    q = f"WITH Base AS (SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {twa} THEN 1 ELSE 0 END + CASE WHEN Ave < {taa} THEN 1 ELSE 0 END + CASE WHEN Econ < {tea} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {twa} THEN 1 ELSE 0 END + CASE WHEN Ave = {taa} THEN 1 ELSE 0 END + CASE WHEN Econ = {tea} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {twa} THEN 1 ELSE 0 END + CASE WHEN Ave > {taa} THEN 1 ELSE 0 END + CASE WHEN Econ > {tea} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Wkts > {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Wkts = {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as TiesB FROM bowling) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''} ORDER BY WinsA DESC, Wickets DESC"
    display_styled_results(pd.read_sql(q, conn), "Bowling")

# TAB 3: ANALYTICS
elif st.session_state.nav_choice == "📈 Player Analytics":
    choice = st.radio("Type:", ["Career Consistency", "Global Rankings"], horizontal=True)
    t = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True).lower()
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

# TAB 4: PLAYER DETAILS
elif st.session_state.nav_choice == "👤 Player Details":
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    target = st.selectbox("Select Player", all_p)
    if target:
        for t, lab in [("batting", "Batting"), ("bowling", "Bowling")]:
            cols = "Runs, Ave, SR" if t == "batting" else "Wkts, Ave, Econ"
            win = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
            loss = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"
            q = f"SELECT A.Season, {cols}, (SELECT COUNT(*) FROM {t}) as TR, (SELECT COUNT(*) FROM {t} B WHERE {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE {loss} >= 2) as LC FROM {t} A WHERE A.Player = '{target}'"
            df = pd.read_sql(q, conn)
            if not df.empty:
                st.subheader(lab); df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR']-1), axis=1); df['Losses %'] = df.apply(lambda r: fmt(r['LC'], r['TR']-1), axis=1); df['Ties %'] = df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC']-1, r['TR']-1), axis=1)
                evt = st.dataframe(df.drop(columns=['TR','WC','LC']), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key=f"det_{t}")
                if evt.selection.rows:
                    sel = df.iloc[evt.selection.rows[0]]
                    if t == "batting": st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a, st.session_state.nav_choice = sel['Runs'], sel['Ave'], sel['SR'], "Batting Milestones"
                    else: st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a, st.session_state.nav_choice = sel['Wkts'], sel['Ave'], sel['Econ'], "Bowling Milestones"
                    st.rerun()

# TAB 5: SQUAD COMPARISON
elif st.session_state.nav_choice == "🏟️ Squad Comparison":
    with st.expander("🛠️ Manage Squads"):
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Clear Squads"): st.session_state.squad_a, st.session_state.squad_b = [], []; st.rerun()
        c2.text_input("📋 Code", value=json.dumps({"a": st.session_state.squad_a, "b": st.session_state.squad_b}))
        load = st.text_input("📥 Load Code:"); ( (d := json.loads(load)), st.session_state.__setitem__('squad_a', d.get('a', [])), st.session_state.__setitem__('squad_b', d.get('b', [])), st.rerun() ) if st.button("🔄 Go") and load else None
    
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    c1, c2 = st.columns(2)
    with c1:
        n = st.selectbox("Add to A", [""]+all_p, key="sqa_a"); (st.session_state.squad_a.append(n), st.rerun()) if n and n not in st.session_state.squad_a else None
        st.session_state.squad_a = st.multiselect("Squad A", st.session_state.squad_a, default=st.session_state.squad_a)
    with c2:
        n = st.selectbox("Add to B", [""]+all_p, key="sqb_b"); (st.session_state.squad_b.append(n), st.rerun()) if n and n not in st.session_state.squad_b else None
        st.session_state.squad_b = st.multiselect("Squad B", st.session_state.squad_b, default=st.session_state.squad_b)

    if st.session_state.squad_a and st.session_state.squad_b:
        sub = st.radio("Mode:", ["Individual Benchmarking", "Squad Standings"], horizontal=True)
        if sub == "Individual Benchmarking":
            d_dir = st.radio("Direction:", ["A Benchmark ➡️ B", "B Benchmark ➡️ A"], horizontal=True)
            src, trg = (st.session_state.squad_a, st.session_state.squad_b) if "A Benchmark" in d_dir else (st.session_state.squad_b, st.session_state.squad_a)
            p = st.selectbox("Pick Benchmark Player:", src, key=f"sq_p_select_{d_dir}")
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
            t = st.radio("Choose Discipline:", ["Batting", "Bowling"], horizontal=True).lower()
            a_l = "('" + "','".join(st.session_state.squad_a) + "')"; b_l = "('" + "','".join(st.session_state.squad_b) + "')"
            win = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
            loss = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"
            c1, c2 = st.columns(2)
            with c1:
                st.write("A vs B")
                q = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {b_l}) as TR, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {b_l} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {b_l} AND {loss} >= 2) as LC FROM {t} A WHERE A.Player IN {a_l}"
                df = pd.read_sql(q, conn); df['Wins'], df['Losses'], df['Ties'] = df.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                st.dataframe(df[['Player', 'Season', 'Wins', 'Losses', 'Ties']], hide_index=True)
            with c2:
                st.write("B vs A")
                q = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {a_l}) as TR, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {a_l} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {a_l} AND {loss} >= 2) as LC FROM {t} A WHERE A.Player IN {b_l}"
                df = pd.read_sql(q, conn); df['Wins'], df['Losses'], df['Ties'] = df.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                st.dataframe(df[['Player', 'Season', 'Wins', 'Losses', 'Ties']], hide_index=True)

# TAB 6: FORMAT ANALYSIS
elif st.session_state.nav_choice == "🧬 Format Analysis":
    sub6 = st.radio("Feature:", ["🛡️ Unbeatable", "🔍 Group Killers"], horizontal=True)
    t = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True, key="disc_fa").lower()
    pl = sorted(pd.read_sql(f"SELECT DISTINCT Player FROM {t}", conn)['Player'].tolist())
    if "Unbeatable" in sub6:
        cx1, cx2 = st.columns(2)
        with cx1: o1 = st.multiselect("Omit Pool:", pl); with cx2: o2 = st.multiselect("Omit Check:", pl)
        k_v = st.radio("Size (K):", [1, 2, 3], horizontal=True)
        if st.button("🚀 Find"):
            with st.spinner("Analyzing..."):
                df_f = pd.read_sql(f"SELECT * FROM {t}", conn); df_k = df_f[~df_f['Player'].isin(o2)]; cand = [p for p in pl if p not in o1]
                if not cand: st.error("No players left.")
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
        if st.button("🔎 Find Killers"):
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
