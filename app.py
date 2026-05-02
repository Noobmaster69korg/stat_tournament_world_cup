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
        # Determine columns to drop safely
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
        (CASE WHEN Wkts = {twb} THEN 1 ELSE 0 END + CASE WHEN Ave = {tab} THEN 1 ELSE 0 END + CASE WHEN Econ = {teb} THEN 1 ELSE 0 END) as TiesB
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
            clean_logic = "B.Runs > A.Runs AND B.Ave > A.Ave AND B.SR > A.SR" if t == "batting" else "B.Wkts > A.Wkts AND B.Ave < A.Ave AND B.Econ < A.Econ"
            q = f"SELECT A.Season, {cols}, (SELECT COUNT(*) FROM {t}) as TR, (SELECT COUNT(*) FROM {t} B WHERE {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE {loss} >= 2) as LC, (SELECT COUNT(*) FROM {t} B WHERE {clean_logic}) as CL FROM {t} A WHERE A.Player = '{target}'"
            df = pd.read_sql(q, conn)
            if not df.empty:
                st.subheader(f"{lab} Career")
                df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR']-1), axis=1)
                df['Losses %'] = df.apply(lambda r: fmt(r['LC'], r['TR']-1), axis=1)
                df['Ties %'] = df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC']-1, r['TR']-1), axis=1)
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
    
    # Restored Robust Loading Feature
    with st.expander("🛠️ Manage Squads (Save/Load/Clear)"):
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑️ Clear Squads"): 
                st.session_state.squad_a, st.session_state.squad_b = [], []
                st.rerun()
        with c2:
            s_data = {"a": st.session_state.squad_a, "b": st.session_state.squad_b}
            st.text_input("📋 Squad Code (Copy this)", value=json.dumps(s_data))
        
        load_inp = st.text_input("📥 Paste Squad Code to load:")
        if st.button("🔄 Execute Load"):
            try:
                d = json.loads(load_inp)
                st.session_state.squad_a = d.get('a', [])
                st.session_state.squad_b = d.get('b', [])
                st.success("Squads updated successfully!")
                st.rerun()
            except: st.error("Invalid Code Format")

    # Builder UI
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    col1, col2 = st.columns(2)
    with col1:
        n_a = st.selectbox("Add to A", [""]+all_p, key="add_sq_a")
        if n_a and n_a not in st.session_state.squad_a: st.session_state.squad_a.append(n_a); st.rerun()
        st.session_state.squad_a = st.multiselect("Squad A Players", st.session_state.squad_a, default=st.session_state.squad_a)
    with col2:
        n_b = st.selectbox("Add to B", [""]+all_p, key="add_sq_b")
        if n_b and n_b not in st.session_state.squad_b: st.session_state.squad_b.append(n_b); st.rerun()
        st.session_state.squad_b = st.multiselect("Squad B Players", st.session_state.squad_b, default=st.session_state.squad_b)

    if st.session_state.squad_a and st.session_state.squad_b:
        sub_mode = st.radio("View:", ["Individual Benchmarking", "Squad Pairwise Standings"], horizontal=True)
        if sub_mode == "Individual Benchmarking":
            d_dir = st.radio("Direction:", ["A is Benchmark", "B is Benchmark"], horizontal=True)
            src, trg = (st.session_state.squad_a, st.session_state.squad_b) if "A" in d_dir else (st.session_state.squad_b, st.session_state.squad_a)
            p = st.selectbox("Pick Benchmark Player", src, key=f"sq_comp_p_{d_dir}")
            if p:
                b_y = pd.read_sql(f"SELECT Season FROM batting WHERE Player='{p}'", conn)['Season'].tolist()
                w_y = pd.read_sql(f"SELECT Season FROM bowling WHERE Player='{p}'", conn)['Season'].tolist()
                disc = st.radio("Disc:", (["Batting"] if b_y else []) + (["Bowling"] if w_y else []), horizontal=True)
                y = st.selectbox("Year:", b_y if disc=="Batting" else w_y)
                if y:
                    bench = pd.read_sql(f"SELECT * FROM {'batting' if disc=='Batting' else 'bowling'} WHERE Player='{p}' AND Season='{y}'", conn).iloc[0]
                    st.info(f"📍 Benchmarking against {p} ({y})")
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
            # Standings logic
            disc_st = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True)
            tbl = disc_st.lower()
            a_l = "('" + "','".join(st.session_state.squad_a) + "')"
            b_l = "('" + "','".join(st.session_state.squad_b) + "')"
            win = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if tbl == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
            loss = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if tbl == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"
            
            c_a, c_b = st.columns(2)
            with c_a:
                st.write("Squad A vs B")
                q_a = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {tbl} B WHERE B.Player IN {b_l}) as TR, (SELECT COUNT(*) FROM {tbl} B WHERE B.Player IN {b_l} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {tbl} B WHERE B.Player IN {b_l} AND {loss} >= 2) as LC FROM {tbl} A WHERE A.Player IN {a_l}"
                df_a = pd.read_sql(q_a, conn); df_a['Wins'], df_a['Losses'], df_a['Ties'] = df_a.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df_a.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df_a.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                st.dataframe(df_a[['Player', 'Season', 'Wins', 'Losses', 'Ties']], hide_index=True)
            with c_b:
                st.write("Squad B vs A")
                q_b = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {tbl} B WHERE B.Player IN {a_l}) as TR, (SELECT COUNT(*) FROM {tbl} B WHERE B.Player IN {a_l} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {tbl} B WHERE B.Player IN {a_l} AND {loss} >= 2) as LC FROM {tbl} A WHERE A.Player IN {b_l}"
                df_b = pd.read_sql(q_b, conn); df_b['Wins'], df_b['Losses'], df_b['Ties'] = df_b.apply(lambda r: fmt(r['WC'], r['TR']), axis=1), df_b.apply(lambda r: fmt(r['LC'], r['TR']), axis=1), df_b.apply(lambda r: fmt(r['TR']-r['WC']-r['LC'], r['TR']), axis=1)
                st.dataframe(df_b[['Player', 'Season', 'Wins', 'Losses', 'Ties']], hide_index=True)

# --- 6: FORMAT ANALYSIS ---
elif st.session_state.nav_choice == "🧬 Format Analysis":
    st.header("🧬 Format Analysis: Unbeatable Combinations")
    disc_f = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True)
    table = disc_f.lower()
    raw_p = sorted(pd.read_sql(f"SELECT DISTINCT Player FROM {table}", conn)['Player'].tolist())
    cx1, cx2 = st.columns(2)
    with cx1: omit_cand = st.multiselect("Omit from combination pool:", raw_p)
    with cx2: omit_kill = st.multiselect("Omit from 'Killers' database:", raw_p)
    k_v = st.radio("K:", [1, 2, 3], horizontal=True)
    if st.button("🚀 Find Unbeatable"):
        with st.spinner("Processing..."):
            df_full = pd.read_sql(f"SELECT * FROM {table}", conn)
            df_killers = df_full[~df_full['Player'].isin(omit_kill)]
            candidates = [p for p in raw_p if p not in omit_cand]
            kill_sets = []
            for _, rx in df_killers.iterrows():
                beaten = set()
                for p_n in candidates:
                    p_yrs = df_full[df_full['Player']==p_n]; all_b = True
                    for _, rp in p_yrs.iterrows():
                        if table=="batting": w = int(rx['Runs']>rp['Runs'])+int(rx['Ave']>rp['Ave'])+int(rx['SR']>rp['SR'])
                        else: w = int(rx['Wkts']>rp['Wkts'])+int(rx['Ave']<rp['Ave'])+int(rx['Econ']<rp['Econ'])
                        if w < 2: all_b = False; break
                    if all_b: beaten.add(p_n)
                kill_sets.append(beaten)
            res = []
            for combo in combinations(candidates, k_v):
                cs = set(combo); unbeatable = True
                for ks in kill_sets:
                    if cs.issubset(ks): unbeatable = False; break
                if unbeatable: res.append(list(combo))
            st.subheader(f"Found {len(res)} sets")
            if res: st.dataframe(pd.DataFrame(res, columns=[f"P{i+1}" for i in range(k_v)]), hide_index=True)

conn.close()
