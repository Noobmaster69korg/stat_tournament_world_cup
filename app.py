import streamlit as st
import sqlite3
import pandas as pd
import json
from itertools import combinations

# Connect to the database
conn = sqlite3.connect('cricket_stats.db')

st.set_page_config(page_title="World Cup Stats Tracker", layout="wide")

st.title("🏏 World Cup Player Stats & Analytics")

# --- PASSWORD PROTECTION ---
password = st.text_input("Enter Password to Access", type="password")
if password != "long live martell":
    st.error("Access Denied. Please enter the correct password.")
    st.stop()

# --- INITIALIZE SESSION STATE ---
if "nav_choice" not in st.session_state: 
    st.session_state.nav_choice = "Batting Milestones"

# Benchmark defaults for auto-fill and jumps
if "bat_runs_a" not in st.session_state: st.session_state.bat_runs_a = 300
if "bat_avg_a" not in st.session_state: st.session_state.bat_avg_a = 40.0
if "bat_sr_a" not in st.session_state: st.session_state.bat_sr_a = 90.0
if "bowl_w_a" not in st.session_state: st.session_state.bowl_w_a = 15
if "bowl_a_a" not in st.session_state: st.session_state.bowl_a_a = 25.0
if "bowl_e_a" not in st.session_state: st.session_state.bowl_e_a = 5.0

# Squad Data
if "squad_a" not in st.session_state: st.session_state.squad_a = []
if "squad_b" not in st.session_state: st.session_state.squad_b = []

# --- GLOBAL HELPER FUNCTIONS ---
def fmt(count, total):
    """Formats count and percentage into a string: '10 (5.0%)'"""
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
        st.warning(f"No players found matching these criteria.")
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
        
        sub_df = df[df['Result_Profile'] == profile].drop(columns=cols_to_drop)
        st.markdown(f"#### {profile} ({len(sub_df)} records)")
        st.dataframe(sub_df, use_container_width=True, hide_index=True)

# --- NAVIGATION MENU ---
nav_options = ["Batting Milestones", "Bowling Milestones", "📈 Player Analytics", "👤 Player Details", "🏟️ Squad Comparison", "🧬 Format Analysis"]
st.session_state.nav_choice = st.radio("Select Section:", nav_options, index=nav_options.index(st.session_state.nav_choice), horizontal=True)
st.divider()

# --- 1: BATTING MILESTONES ---
if st.session_state.nav_choice == "Batting Milestones":
    st.header("Batting Filter")
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Set A (Primary)")
        tr1a = st.number_input("Min Runs (A)", value=st.session_state.bat_runs_a, key="bat_r_in")
        ta1a = st.number_input("Min Average (A)", value=st.session_state.bat_avg_a, key="bat_a_in")
        ts1a = st.number_input("Min SR (A)", value=st.session_state.bat_sr_a, key="bat_s_in")
        st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = tr1a, ta1a, ts1a
    with c2:
        st.subheader("Set B (Secondary)")
        tr1b = st.number_input("Min Runs (B)", 500, key="bat_r_in_b")
        ta1b = st.number_input("Min Avg (B)", 50.0, key="bat_a_in_b")
        ts1b = st.number_input("Min SR (B)", 100.0, key="bat_s_in_b")
    
    q = f"""
    WITH Base AS (
        SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate,
        (CASE WHEN Runs > {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1a} THEN 1 ELSE 0 END) as WinsA,
        (CASE WHEN Runs = {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1a} THEN 1 ELSE 0 END) as TiesA,
        (CASE WHEN Runs < {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR < {ts1a} THEN 1 ELSE 0 END) as LossesA,
        (CASE WHEN Runs > {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1b} THEN 1 ELSE 0 END) as WinsB,
        (CASE WHEN Runs = {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1b} THEN 1 ELSE 0 END) as TiesB
        FROM batting
    )
    SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''}
    ORDER BY WinsA DESC, Runs DESC
    """
    display_styled_results(pd.read_sql(q, conn), "Batting")

# --- 2: BOWLING MILESTONES ---
elif st.session_state.nav_choice == "Bowling Milestones":
    st.header("Bowling Filter")
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Set A (Primary)")
        twa = st.number_input("Min Wickets (A)", value=st.session_state.bowl_w_a, key="bowl_w_in")
        taa = st.number_input("Max Avg (A)", value=st.session_state.bowl_a_a, key="bowl_a_in")
        tea = st.number_input("Max Econ (A)", value=st.session_state.bowl_e_a, key="bowl_e_in")
        st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = twa, taa, tea
    with c2:
        st.subheader("Set B (Secondary)")
        twb = st.number_input("Min Wkts (B)", 20, key="bowl_w_in_b")
        tab = st.number_input("Max Avg (B)", 20.0, key="bowl_a_in_b")
        teb = st.number_input("Max Econ (B)", 4.5, key="bowl_e_in_b")

    q = f"""
    WITH Base AS (
        SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy,
        (CASE WHEN Wkts > {twa} THEN 1 ELSE 0 END + CASE WHEN Ave < {taa} THEN 1 ELSE 0 END + CASE WHEN Econ < {tea} THEN 1 ELSE 0 END) as WinsA,
        (CASE WHEN Wkts = {twa} THEN 1 ELSE 0 END + CASE WHEN Ave = {taa} THEN 1 ELSE 0 END + CASE WHEN Econ = {tea} THEN 1 ELSE 0 END) as TiesA,
        (CASE WHEN Wkts < {twa} THEN 1 ELSE 0 END + CASE WHEN Ave > {taa} THEN 1 ELSE 0 END + CASE WHEN Econ > {tea} THEN 1 ELSE 0 END) as LossesA,
        (CASE WHEN Wkts > {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as WinsB,
        (CASE WHEN Wkts = {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as TiesB
        FROM bowling
    )
    SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''}
    ORDER BY WinsA DESC, Wickets DESC
    """
    display_styled_results(pd.read_sql(q, conn), "Bowling")

# --- 3: PLAYER ANALYTICS ---
elif st.session_state.nav_choice == "📈 Player Analytics":
    st.header("📈 Advanced Analytics")
    choice = st.radio("Type:", ["Career Consistency", "Global Rankings"], horizontal=True)
    if "Consistency" in choice:
        disc = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True, key="dc_t3")
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
        disc = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True, key="dp_t3")
        t = "batting" if disc == "Batting" else "bowling"
        win = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
        loss = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"
        q = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t}) as TR, (SELECT COUNT(*) FROM {t} B WHERE {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE {loss} >= 2) as LC FROM {t} A"
        df = pd.read_sql(q, conn); df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR']-1), axis=1); df['Losses'] = df.apply(lambda r: fmt(r['LC'], r['TR']-1), axis=1); df['Ties'] = df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC']-1, r['TR']-1), axis=1)
        st.dataframe(df.sort_values("WC", ascending=False)[['Player', 'Season', 'Wins %', 'Losses', 'Ties']], use_container_width=True, hide_index=True)

# --- 4: PLAYER DETAILS ---
elif st.session_state.nav_choice == "👤 Player Details":
    st.header("👤 Player Profile Search")
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
                st.subheader(lab); df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR']-1), axis=1); df['Losses %'] = df.apply(lambda r: fmt(r['LC'], r['TR']-1), axis=1); df['Ties %'] = df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC']-1, r['TR']-1), axis=1)
                evt = st.dataframe(df.drop(columns=['TR','WC','LC']), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key=f"det_scr_{t}")
                if evt.selection.rows:
                    sel = df.iloc[evt.selection.rows[0]]
                    if t == "batting": 
                        st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = sel['Runs'], sel['Ave'], sel['SR']
                        st.session_state.nav_choice = "Batting Milestones"
                    else: 
                        st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = sel['Wkts'], sel['Ave'], sel['Econ']
                        st.session_state.nav_choice = "Bowling Milestones"
                    st.rerun()

# --- 5: SQUAD COMPARISON ---
elif st.session_state.nav_choice == "🏟️ Squad Comparison":
    st.header("🏟️ Squad Comparison")
    with st.expander("🛠️ Manage Squads"):
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Clear Squads"): st.session_state.squad_a, st.session_state.squad_b = [], []; st.rerun()
        c2.text_input("📋 Squad Code", value=json.dumps({"a": st.session_state.squad_a, "b": st.session_state.squad_b}))
        load = st.text_input("📥 Load Code:")
        if st.button("🔄 Execute Load") and load:
            try: d = json.loads(load); st.session_state.squad_a, st.session_state.squad_b = d.get('a', []), d.get('b', []); st.rerun()
            except: st.error("ERR")
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    c1, c2 = st.columns(2)
    with c1:
        n = st.selectbox("Add Player to A", [""]+all_p, key="sqa_a"); (st.session_state.squad_a.append(n), st.rerun()) if n and n not in st.session_state.squad_a else None
        st.session_state.squad_a = st.multiselect("Squad A", st.session_state.squad_a, default=st.session_state.squad_a)
    with c2:
        n = st.selectbox("Add Player to B", [""]+all_p, key="sqb_b"); (st.session_state.squad_b.append(n), st.rerun()) if n and n not in st.session_state.squad_b else None
        st.session_state.squad_b = st.multiselect("Squad B", st.session_state.squad_b, default=st.session_state.squad_b)
    
    if st.session_state.squad_a and st.session_state.squad_b:
        sub = st.radio("Mode:", ["Individual Benchmarking", "Squad Standings"], horizontal=True)
        if sub == "Individual Benchmarking":
            d_dir = st.radio("Direction:", ["A Benchmark ➡️ B", "B Benchmark ➡️ A"], horizontal=True)
            src, trg = (st.session_state.squad_a, st.session_state.squad_b) if "A Benchmark" in d_dir else (st.session_state.squad_b, st.session_state.squad_a)
            # Use unique key for the selectbox to ensure it updates when toggle changes
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
            t_disc = st.radio("Choose Discipline:", ["Batting", "Bowling"], horizontal=True).lower()
            a_list_str = "('" + "','".join(st.session_state.squad_a) + "')"
            b_list_str = "('" + "','".join(st.session_state.squad_b) + "')"
            win_l = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if t_disc == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
            loss_l = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if t_disc == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"
            
            c_a, c_b = st.columns(2)
            with c_a:
                st.write("Squad A Performance vs B")
                q_a = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_list_str}) as TR, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_list_str} AND {win_l} >= 2) as WC, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {b_list_str} AND {loss_l} >= 2) as LC FROM {t_disc} A WHERE A.Player IN {a_list_str}"
                df_a = pd.read_sql(q_a, conn)
                if not df_a.empty:
                    df_a['Wins'], df_a['Losses'], df_a['Ties'] = df_a.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df_a.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df_a.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                    st.dataframe(df_a[['Player', 'Season', 'Wins', 'Losses', 'Ties']], hide_index=True)
            with c_b:
                st.write("Squad B Performance vs A")
                q_b = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {a_list_str}) as TR, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {a_list_str} AND {win_l} >= 2) as WC, (SELECT COUNT(*) FROM {t_disc} B WHERE B.Player IN {a_list_str} AND {loss_l} >= 2) as LC FROM {t_disc} A WHERE A.Player IN {b_list_str}"
                df_b = pd.read_sql(q_b, conn)
                if not df_b.empty:
                    df_b['Wins'], df_b['Losses'], df_b['Ties'] = df_b.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df_b.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df_b.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                    st.dataframe(df_b[['Player', 'Season', 'Wins', 'Losses', 'Ties']], hide_index=True)

# --- 6: FORMAT ANALYSIS ---
elif st.session_state.nav_choice == "🧬 Format Analysis":
    st.header("🧬 Format Analysis")
    sub_tab_6 = st.radio("Select Feature:", ["🛡️ Find Unbeatable Combinations", "🔍 Find Group Killers"], horizontal=True)
    disc_f = st.radio("Choose Discipline:", ["Batting", "Bowling"], horizontal=True, key="disc_fa_main").lower()
    raw_p = sorted(pd.read_sql(f"SELECT DISTINCT Player FROM {disc_f}", conn)['Player'].tolist())

    if "Unbeatable" in sub_tab_6:
        cx1, cx2 = st.columns(2)
        with cx1: omit_cand = st.multiselect("Omit from combination pool:", raw_p, key="om1")
        with cx2: omit_kill = st.multiselect("Omit from 'Killers' database:", raw_p, key="om2")
        k_v = st.radio("Combination Size (K):", [1, 2, 3], horizontal=True)
        if st.button("🚀 Find Combinations"):
            with st.spinner("Analyzing..."):
                df_f = pd.read_sql(f"SELECT * FROM {disc_f}", conn); df_k = df_f[~df_f['Player'].isin(omit_kill)]; cand = [p for p in raw_p if p not in omit_cand]
                if not cand: st.error("No players left.")
                else:
                    kill_sets = []
                    for _, rx in df_k.iterrows():
                        beaten = set()
                        for p_n in cand:
                            py = df_f[df_f['Player']==p_n]; b = 0
                            for _, rp in py.iterrows():
                                if disc_f=="batting": w = int(rx['Runs']>rp['Runs'])+int(rx['Ave']>rp['Ave'])+int(rx['SR']>rp['SR'])
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
                    if res:
                        st.subheader(f"Found {len(res)} sets")
                        st.dataframe(pd.DataFrame(res, columns=[f"P{i+1}" for i in range(k_v)]), hide_index=True)
                    else: st.error("No unbeatable combination found.")
    else:
        target = st.multiselect("Select Group:", raw_p)
        if st.button("🔎 Find Group Killers"):
            if target:
                df_full = pd.read_sql(f"SELECT * FROM {disc_f}", conn); kl = []
                for _, rx in df_full.iterrows():
                    e = True
                    for pn in target:
                        py = df_full[df_full['Player']==pn]; pb = True
                        for _, rp in py.iterrows():
                            if disc_f=="batting": w = int(rx['Runs']>rp['Runs'])+int(rx['Ave']>rp['Ave'])+int(rx['SR']>rp['SR'])
                            else: w = int(rx['Wkts']>rp['Wkts'])+int(rx['Ave']<rp['Ave'])+int(rx['Econ']<rp['Econ'])
                            if w < 2: pb = False; break
                        if not pb: e = False; break
                    if e: kl.append(rx)
                if kl:
                    st.success(f"Found {len(kl)} seasons!"); st.dataframe(pd.DataFrame(kl), use_container_width=True, hide_index=True)
                else: st.error("No single year beats this entire group.")

conn.close()
