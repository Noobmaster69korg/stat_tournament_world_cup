import streamlit as st
import sqlite3
import pandas as pd
import json
import requests
from itertools import combinations

# --- 1. SCRAPER LOGIC (Isolated) ---
def scrape_cricinfo(url, discipline):
    try:
        html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
        tables = pd.read_html(html)
        df = None
        for t in tables:
            if 'Player' in t.columns:
                df = t
                break
        if df is None: return None
        
        if discipline == "batting":
            df = df.rename(columns={'Span': 'Season', 'SR': 'SR', 'Ave': 'Ave', 'Runs': 'Runs'})
            for col in ['Runs', 'Ave', 'SR']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df[['Player', 'Season', 'Runs', 'Ave', 'SR']]
        else:
            df = df.rename(columns={'Span': 'Season', 'Wkts': 'Wkts', 'Ave': 'Ave', 'Econ': 'Econ'})
            for col in ['Wkts', 'Ave', 'Econ']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df[['Player', 'Season', 'Wkts', 'Ave', 'Econ']]
    except Exception as e:
        st.sidebar.error(f"Scrape Error: {e}")
        return None

# --- 2. APP CONFIG & GLOBAL HELPERS ---
st.set_page_config(page_title="Cricket Stats Engine", layout="wide")

def fmt(count, total):
    if total <= 0: return "0 (0.0%)"
    perc = (count * 100.0 / total)
    return f"{int(count)} ({perc:.1f}%)"

def get_profile_label(w, t, l):
    if w == 3: return "🏆 Beat all 3 categories"
    if w == 2 and t == 1: return "⭐ Beat 2 categories, Tied 1 category"
    if w == 2 and l == 1: return "✅ Beat 2 categories, Lost 1 category"
    if w == 1 and t == 2: return "⚠️ Beat 1 category, Tied 2 categories"
    if w == 1 and t == 1 and l == 1: return "⚖️ Beat 1 category, Tied 1, Lost 1 (Tie Case)"
    if w == 0 and t == 3: return "🎯 Tied all 3 categories"
    if w == 0 and t == 2 and l == 1: return "🤏 Tied 2 categories, Lost 1 category"
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
        st.markdown(f"#### {profile} ({len(df[df['Result_Profile'] == profile])} records)")
        st.dataframe(df[df['Result_Profile'] == profile].drop(columns=cols_to_drop), use_container_width=True, hide_index=True)

# --- 3. DATABASE HANDLER ---
st.sidebar.title("🌐 Live Data Scraper")
bat_url = st.sidebar.text_input("ESPN Batting Link (Year View)")
bowl_url = st.sidebar.text_input("ESPN Bowling Link (Year View)")

if "scraped_db" not in st.session_state: st.session_state.scraped_db = None

if st.sidebar.button("🚀 Build Database from Links"):
    if bat_url and bowl_url:
        with st.spinner("Scraping..."):
            b_df, w_df = scrape_cricinfo(bat_url, "batting"), scrape_cricinfo(bowl_url, "bowling")
            if b_df is not None and w_df is not None:
                tmp_conn = sqlite3.connect(':memory:', check_same_thread=False)
                b_df.to_sql('batting', tmp_conn, index=False)
                w_df.to_sql('bowling', tmp_conn, index=False)
                st.session_state.scraped_db = tmp_conn
                st.sidebar.success("Database Built!")
            else: st.sidebar.error("Failed to parse links.")

conn = st.session_state.scraped_db if st.session_state.scraped_db else sqlite3.connect('cricket_stats.db', check_same_thread=False)
st.sidebar.write("Status: " + ("🟢 Live Scraped" if st.session_state.scraped_db else "🏠 Local DB"))

# --- 4. ACCESS CONTROL ---
st.title("🏏 World Cup Player Stats & Analytics")
password = st.text_input("Enter Password to Access", type="password")
if password != "long live martell":
    st.error("Access Denied.")
    st.stop()

# --- 5. SESSION STATE INITIALIZATION ---
if "nav_choice" not in st.session_state: st.session_state.nav_choice = "Batting Milestones"
for k, v in {"bat_runs_a":300, "bat_avg_a":40.0, "bat_sr_a":90.0, "bowl_w_a":15, "bowl_a_a":25.0, "bowl_e_a":5.0}.items():
    if k not in st.session_state: st.session_state[k] = v
if "squad_a" not in st.session_state: st.session_state.squad_a, st.session_state.squad_b = [], []

# --- 6. NAVIGATION MENU ---
nav_options = ["Batting Milestones", "Bowling Milestones", "📈 Player Analytics", "👤 Player Details", "🏟️ Squad Comparison", "🧬 Format Analysis"]
st.session_state.nav_choice = st.radio("Select Section:", nav_options, index=nav_options.index(st.session_state.nav_choice), horizontal=True)
st.divider()

# --- TAB 1: BATTING ---
if st.session_state.nav_choice == "Batting Milestones":
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        tr1a = st.number_input("Min Runs (A)", value=st.session_state.bat_runs_a)
        ta1a = st.number_input("Min Average (A)", value=st.session_state.bat_avg_a)
        ts1a = st.number_input("Min Strike Rate (A)", value=st.session_state.bat_sr_a)
        st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = tr1a, ta1a, ts1a
    with c2:
        tr1b, ta1b, ts1b = st.number_input("Min Runs (B)", 500), st.number_input("Min Average (B)", 50.0), st.number_input("Min Strike Rate (B)", 100.0)
    q = f"WITH Base AS (SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1a} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1a} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR < {ts1a} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Runs > {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1b} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Runs = {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1b} THEN 1 ELSE 0 END) as TiesB FROM batting) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''} ORDER BY WinsA DESC, Runs DESC"
    display_styled_results(pd.read_sql(q, conn), "Batting")

# --- TAB 2: BOWLING ---
elif st.session_state.nav_choice == "Bowling Milestones":
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        twa = st.number_input("Min Wickets (A)", value=st.session_state.bowl_w_a)
        taa = st.number_input("Max Average (A)", value=st.session_state.bowl_a_a)
        tea = st.number_input("Max Economy (A)", value=st.session_state.bowl_e_a)
        st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = twa, taa, tea
    with c2:
        twb, tab, teb = st.number_input("Min Wickets (B)", 20), st.number_input("Max Average (B)", 20.0), st.number_input("Max Economy (B)", 4.5)
    q = f"WITH Base AS (SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {twa} THEN 1 ELSE 0 END + CASE WHEN Ave < {taa} THEN 1 ELSE 0 END + CASE WHEN Econ < {tea} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {twa} THEN 1 ELSE 0 END + CASE WHEN Ave = {taa} THEN 1 ELSE 0 END + CASE WHEN Econ = {tea} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {twa} THEN 1 ELSE 0 END + CASE WHEN Ave > {taa} THEN 1 ELSE 0 END + CASE WHEN Econ > {tea} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Wkts > {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Wkts = {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as TiesB FROM bowling) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''} ORDER BY WinsA DESC, Wickets DESC"
    display_styled_results(pd.read_sql(q, conn), "Bowling")

# --- TAB 3: ANALYTICS ---
elif st.session_state.nav_choice == "📈 Player Analytics":
    choice = st.radio("Type:", ["Career Consistency", "Global Rankings"], horizontal=True)
    if "Consistency" in choice:
        disc = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True)
        c1, c2, c3 = st.columns(3)
        if disc == "Batting":
            r, a, s = c1.number_input("Min Runs", 250), c2.number_input("Min Avg", 35.0), c3.number_input("Min SR", 85.0)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Runs >= {r}) + (Ave >= {a}) + (SR >= {s})) >= 2 THEN 1 ELSE 0 END) as Successful FROM batting GROUP BY Player HAVING Successful > 0"
        else:
            w, av, e = c1.number_input("Min Wkts", 12), c2.number_input("Max Avg", 28.0), c3.number_input("Max Econ", 5.5)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Wkts >= {w}) + (Ave <= {av}) + (Econ <= {e})) >= 2 THEN 1 ELSE 0 END) as Successful FROM bowling GROUP BY Player HAVING Successful > 0"
        df = pd.read_sql(q, conn); df['Win %'] = (df['Successful']*100/df['Total']).round(2)
        st.dataframe(df.sort_values("Win %", ascending=False), use_container_width=True, hide_index=True)
    else:
        disc = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True)
        t = disc.lower()
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
            cl = "B.Runs > A.Runs AND B.Ave > A.Ave AND B.SR > A.SR" if t == "batting" else "B.Wkts > A.Wkts AND B.Ave < A.Ave AND B.Econ < A.Econ"
            q = f"SELECT A.Season, {cols}, (SELECT COUNT(*) FROM {t}) as TR, (SELECT COUNT(*) FROM {t} B WHERE {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE {loss} >= 2) as LC, (SELECT COUNT(*) FROM {t} B WHERE {cl}) as CL FROM {t} A WHERE A.Player = '{target}'"
            df = pd.read_sql(q, conn)
            if not df.empty:
                st.subheader(f"{lab} Career")
                df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR']-1), axis=1); df['Losses %'] = df.apply(lambda r: fmt(r['LC'], r['TR']-1), axis=1); df['Ties %'] = df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC']-1, r['TR']-1), axis=1)
                evt = st.dataframe(df.drop(columns=['TR','WC','LC']), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key=f"det_{t}")
                if evt.selection.rows:
                    sel = df.iloc[evt.selection.rows[0]]
                    if t == "batting": 
                        st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a, st.session_state.nav_choice = sel['Runs'], sel['Ave'], sel['SR'], "Batting Milestones"
                    else: 
                        st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a, st.session_state.nav_choice = sel['Wkts'], sel['Ave'], sel['Econ'], "Bowling Milestones"
                    st.rerun()

# --- TAB 5: SQUAD COMPARISON ---
elif st.session_state.nav_choice == "🏟️ Squad Comparison":
    with st.expander("🛠️ Manage Squads"):
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Clear Squads"): st.session_state.squad_a, st.session_state.squad_b = [], []; st.rerun()
        c2.text_input("📋 Squad Code", value=json.dumps({"a": st.session_state.squad_a, "b": st.session_state.squad_b}))
        load = st.text_input("📥 Paste Code:")
        if st.button("🔄 Execute Load"):
            try: 
                d = json.loads(load)
                st.session_state.squad_a, st.session_state.squad_b = d.get('a', []), d.get('b', [])
                st.rerun()
            except: st.error("Invalid Code")

    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    c1, c2 = st.columns(2)
    with c1:
        n = st.selectbox("Add to A", [""]+all_p, key="sqa_a"); (st.session_state.squad_a.append(n), st.rerun()) if n and n not in st.session_state.squad_a else None
        st.session_state.squad_a = st.multiselect("Squad A", st.session_state.squad_a, default=st.session_state.squad_a)
    with c2:
        n = st.selectbox("Add to B", [""]+all_p, key="sqb_b"); (st.session_state.squad_b.append(n), st.rerun()) if n and n not in st.session_state.squad_b else None
        st.session_state.squad_b = st.multiselect("Squad B", st.session_state.squad_b, default=st.session_state.squad_b)

    if st.session_state.squad_a and st.session_state.squad_b:
        mode = st.radio("Sub-Mode:", ["Individual Benchmarking", "Squad Standings"], horizontal=True)
        if mode == "Individual Benchmarking":
            d_dir = st.radio("Direction:", ["A Benchmark ➡️ B", "B Benchmark ➡️ A"], horizontal=True)
            src, trg = (st.session_state.squad_a, st.session_state.squad_b) if "A Benchmark" in d_dir else (st.session_state.squad_b, st.session_state.squad_a)
            p = st.selectbox("Benchmark Player:", src, key=f"sq_p_{d_dir}")
            if p:
                b_y, w_y = pd.read_sql(f"SELECT Season FROM batting WHERE Player='{p}'", conn)['Season'].tolist(), pd.read_sql(f"SELECT Season FROM bowling WHERE Player='{p}'", conn)['Season'].tolist()
                disc = st.radio("Type:", (["Batting"] if b_y else []) + (["Bowling"] if w_y else []), horizontal=True)
                y = st.selectbox("Year:", b_y if disc == "Batting" else w_y)
                if y:
                    bench = pd.read_sql(f"SELECT * FROM {'batting' if disc=='Batting' else 'bowling'} WHERE Player='{p}' AND Season='{y}'", conn).iloc[0]
                    # RESTORED: BENCHMARK DISPLAY
                    st.info(f"📍 Benchmark Details: {p} ({y})")
                    met = st.columns(3)
                    if disc == "Batting":
                        tr, ta, ts = bench['Runs'], bench['Ave'], bench['SR']
                        met[0].metric("Runs", tr); met[1].metric("Avg", ta); met[2].metric("SR", ts)
                        q = f"SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta} THEN 1 ELSE 0 END + CASE WHEN SR > {ts} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta} THEN 1 ELSE 0 END + CASE WHEN SR = {ts} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta} THEN 1 ELSE 0 END + CASE WHEN SR < {ts} THEN 1 ELSE 0 END) as LossesA FROM batting WHERE Player IN ('" + "','".join(trg) + "') ORDER BY WinsA DESC"
                    else:
                        tw, tav, te = bench['Wkts'], bench['Ave'], bench['Econ']
                        met[0].metric("Wkts", tw); met[1].metric("Avg", tav); met[2].metric("Econ", te)
                        q = f"SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {tw} THEN 1 ELSE 0 END + CASE WHEN Ave < {tav} THEN 1 ELSE 0 END + CASE WHEN Econ < {te} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {tw} THEN 1 ELSE 0 END + CASE WHEN Ave = {tav} THEN 1 ELSE 0 END + CASE WHEN Econ = {te} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {tw} THEN 1 ELSE 0 END + CASE WHEN Ave > {tav} THEN 1 ELSE 0 END + CASE WHEN Econ > {te} THEN 1 ELSE 0 END) as LossesA FROM bowling WHERE Player IN ('" + "','".join(trg) + "') ORDER BY WinsA DESC"
                    display_styled_results(pd.read_sql(q, conn), f"Against {p}")
        else:
            disc_st = st.radio("Choose Discipline:", ["Batting", "Bowling"], horizontal=True)
            t = disc_st.lower()
            a_l = "('" + "','".join(st.session_state.squad_a) + "')"
            b_l = "('" + "','".join(st.session_state.squad_b) + "')"
            win = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
            loss = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"
            
            c_a, c_b = st.columns(2)
            # FIXED STANDINGS LOGIC (No NameError)
            with c_a:
                st.write("Squad A Performance vs B")
                q_a = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {b_l}) as TR, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {b_l} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {b_l} AND {loss} >= 2) as LC FROM {t} A WHERE A.Player IN {a_l}"
                df_a = pd.read_sql(q_a, conn)
                if not df_a.empty:
                    df_a['Wins'], df_a['Losses'], df_a['Ties'] = df_a.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df_a.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df_a.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                    st.dataframe(df_a[['Player', 'Season', 'Wins', 'Losses', 'Ties']], use_container_width=True, hide_index=True)
            with c_b:
                st.write("Squad B Performance vs A")
                q_b = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {a_l}) as TR, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {a_l} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {a_l} AND {loss} >= 2) as LC FROM {t} A WHERE A.Player IN {b_l}"
                df_b = pd.read_sql(q_b, conn)
                if not df_b.empty:
                    df_b['Wins'], df_b['Losses'], df_b['Ties'] = df_b.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df_b.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df_b.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                    st.dataframe(df_b[['Player', 'Season', 'Wins', 'Losses', 'Ties']], use_container_width=True, hide_index=True)

# --- TAB 6: FORMAT ANALYSIS ---
elif st.session_state.nav_choice == "🧬 Format Analysis":
    sub6 = st.radio("Feature:", ["🛡️ Unbeatable Combinations", "🔍 Group Killers"], horizontal=True)
    df_f = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True)
    t = df_f.lower(); pl = sorted(pd.read_sql(f"SELECT DISTINCT Player FROM {t}", conn)['Player'].tolist())
    if "Unbeatable" in sub6:
        cx1, cx2 = st.columns(2)
        with cx1: omit_cand = st.multiselect("Omit from combination pool:", pl, key="omit1")
        with cx2: omit_kill = st.multiselect("Omit from 'Killers' check:", pl, key="omit2")
        k_v = st.radio("Size (K):", [1, 2, 3], horizontal=True)
        if st.button("🚀 Find Combinations"):
            with st.spinner("Analyzing..."):
                df_all = pd.read_sql(f"SELECT * FROM {t}", conn); df_k = df_all[~df_all['Player'].isin(omit_kill)]; cand = [p for p in pl if p not in omit_cand]
                kill_sets = []
                for _, rx in df_k.iterrows():
                    beaten = set()
                    for p_n in cand:
                        py = df_all[df_all['Player']==p_n]; b = 0
                        for _, rp in py.iterrows():
                            if t=="batting": w = int(rx['Runs']>rp['Runs'])+int(rx['Ave']>rp['Ave'])+int(rx['SR']>rp['SR'])
                            else: w = int(rx['Wkts']>rp['Wkts'])+int(rx['Ave']<rp['Ave'])+int(rx['Econ']<rp['Econ'])
                            if w >= 2: b += 1
                        if b == len(py): beaten.add(p_n)
                    kill_sets.append(beaten)
                res = []
                for combo in combinations(cand, k_v):
                    cs = set(combo); unb = True
                    for ks in kill_sets:
                        if cs.issubset(ks): unb = False; break
                    if unb: res.append(list(combo))
                if res: st.dataframe(pd.DataFrame(res, columns=[f"P{i+1}" for i in range(k_v)]), hide_index=True)
    else:
        target = st.multiselect("Select Group:", pl)
        if st.button("🔎 Find Killer Years"):
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

conn.close()
