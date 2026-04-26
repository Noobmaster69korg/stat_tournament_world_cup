import streamlit as st
import sqlite3
import pandas as pd
import json

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
if "nav_choice" not in st.session_state: st.session_state.nav_choice = "Batting Milestones"
if "bat_runs_a" not in st.session_state: st.session_state.bat_runs_a = 300
if "bat_avg_a" not in st.session_state: st.session_state.bat_avg_a = 40.0
if "bat_sr_a" not in st.session_state: st.session_state.bat_sr_a = 90.0
if "bowl_w_a" not in st.session_state: st.session_state.bowl_w_a = 15
if "bowl_a_a" not in st.session_state: st.session_state.bowl_a_a = 25.0
if "bowl_e_a" not in st.session_state: st.session_state.bowl_e_a = 5.0
if "squad_a" not in st.session_state: st.session_state.squad_a = []
if "squad_b" not in st.session_state: st.session_state.squad_b = []

# --- GLOBAL HELPER FUNCTIONS ---
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
nav_options = ["Batting Milestones", "Bowling Milestones", "📈 Player Analytics", "👤 Player Details", "🏟️ Squad Comparison"]
st.session_state.nav_choice = st.radio("Select Section:", nav_options, index=nav_options.index(st.session_state.nav_choice), horizontal=True)
st.divider()

# --- SECTION 1: BATTING MILESTONES ---
if st.session_state.nav_choice == "Batting Milestones":
    st.header("🏏 Batting Milestones")
    filter_mode_bat = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Set A (Primary)")
        tr1a = st.number_input("Min Runs (A)", value=st.session_state.bat_runs_a, key="br_a")
        ta1a = st.number_input("Min Avg (A)", value=st.session_state.bat_avg_a, key="ba_a")
        ts1a = st.number_input("Min SR (A)", value=st.session_state.bat_sr_a, key="bs_a")
        st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = tr1a, ta1a, ts1a
    with col_b:
        st.subheader("Set B (Secondary)")
        tr1b = st.number_input("Min Runs (B)", value=500, key="br_b")
        ta1b = st.number_input("Min Avg (B)", value=50, key="ba_b")
        ts1b = st.number_input("Min SR (B)", value=110, key="bs_b")

    bat_query = f"""
    WITH Base AS (
        SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate,
        (CASE WHEN Runs > {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1a} THEN 1 ELSE 0 END) as WinsA,
        (CASE WHEN Runs = {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1a} THEN 1 ELSE 0 END) as TiesA,
        (CASE WHEN Runs < {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR < {ts1a} THEN 1 ELSE 0 END) as LossesA,
        (CASE WHEN Runs > {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1b} THEN 1 ELSE 0 END) as WinsB,
        (CASE WHEN Runs = {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1b} THEN 1 ELSE 0 END) as TiesB
        FROM batting
    )
    SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 
    {"AND (WinsB + TiesB) >= 2" if "BOTH" in filter_mode_bat else ""}
    ORDER BY WinsA DESC, TiesA DESC, Runs DESC
    """
    display_styled_results(pd.read_sql(bat_query, conn), "Batting")

# --- SECTION 2: BOWLING MILESTONES ---
elif st.session_state.nav_choice == "Bowling Milestones":
    st.header("⚽ Bowling Milestones")
    filter_mode_bowl = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("Set A (Primary)")
        twa = st.number_input("Min Wickets (A)", value=st.session_state.bowl_w_a, key="bw_a")
        taa = st.number_input("Max Avg (A)", value=st.session_state.bowl_a_a, key="bav_a")
        tea = st.number_input("Max Econ (A)", value=st.session_state.bowl_e_a, key="be_a")
        st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = twa, taa, tea
    with col_d:
        st.subheader("Set B (Secondary)")
        twb = st.number_input("Min Wickets (B)", value=20, key="bw_b")
        tab = st.number_input("Max Avg (B)", value=20.0, key="bav_b")
        teb = st.number_input("Max Econ (B)", value=4.5, key="be_b")

    bowl_query = f"""
    WITH Base AS (
        SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy,
        (CASE WHEN Wkts > {twa} THEN 1 ELSE 0 END + CASE WHEN Ave < {taa} THEN 1 ELSE 0 END + CASE WHEN Econ < {tea} THEN 1 ELSE 0 END) as WinsA,
        (CASE WHEN Wkts = {twa} THEN 1 ELSE 0 END + CASE WHEN Ave = {taa} THEN 1 ELSE 0 END + CASE WHEN Econ = {tea} THEN 1 ELSE 0 END) as TiesA,
        (CASE WHEN Wkts < {twa} THEN 1 ELSE 0 END + CASE WHEN Ave > {taa} THEN 1 ELSE 0 END + CASE WHEN Econ > {tea} THEN 1 ELSE 0 END) as LossesA,
        (CASE WHEN Wkts > {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as WinsB,
        (CASE WHEN Wkts = {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as TiesB
        FROM bowling
    )
    SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 
    {"AND (WinsB + TiesB) >= 2" if "BOTH" in filter_mode_bowl else ""}
    ORDER BY WinsA DESC, TiesA DESC, Wickets DESC
    """
    display_styled_results(pd.read_sql(bowl_query, conn), "Bowling")

# --- SECTION 3: ANALYTICS ---
elif st.session_state.nav_choice == "📈 Player Analytics":
    st.header("📈 Advanced Analytics")
    ana_choice = st.radio("Choose Analysis Type:", ["Career Consistency", "Global Season Ranking"], horizontal=True)
    if ana_choice == "Career Consistency":
        disc_cons = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True, key="dc_c")
        c1, c2, c3 = st.columns(3)
        if disc_cons == "Batting":
            r_c, a_c, s_c = c1.number_input("Min Runs", 150), c2.number_input("Min Avg", 20), c3.number_input("Min SR", 55.0)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Runs >= {r_c}) + (Ave >= {a_c}) + (SR >= {s_c})) >= 2 THEN 1 ELSE 0 END) as Successful FROM batting GROUP BY Player HAVING Successful > 0"
        else:
            w_c, av_c, e_c = c1.number_input("Min Wkts", 7), c2.number_input("Max Avg", 2), c3.number_input("Max Econ", 1.0)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Wkts >= {w_c}) + (Ave <= {av_c}) + (Econ <= {e_c})) >= 2 THEN 1 ELSE 0 END) as Successful FROM bowling GROUP BY Player HAVING Successful > 0"
        df_c = pd.read_sql(q, conn)
        df_c['Win %'] = (df_c['Successful'] * 100.0 / df_c['Total']).round(2)
        st.dataframe(df_c.sort_values("Win %", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.subheader("🏆 Global Pairwise Rankings")
        disc_p = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True, key="dp_rank")
        if disc_p == "Batting":
            p_q = f"SELECT A.Player, A.Season, A.Runs, A.Ave, A.SR, (SELECT COUNT(*) FROM batting) as Total_Raw, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM batting B WHERE B.Runs > A.Runs AND B.Ave > A.Ave AND B.SR > A.SR) as Clean_Loss FROM batting A"
        else:
            p_q = f"SELECT A.Player, A.Season, A.Wkts, A.Ave, A.Econ, (SELECT COUNT(*) FROM bowling) as Total_Raw, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM bowling B WHERE B.Wkts > A.Wkts AND B.Ave < A.Ave AND B.Econ < A.Econ) as Clean_Loss FROM bowling A"
        df_p = pd.read_sql(p_q, conn)
        df_p['Total_Opp'] = df_p['Total_Raw'] - 1
        df_p['Tie_C'] = (df_p['Total_Raw'] - df_p['Win_C'] - df_p['Loss_C']) - 1
        df_p['Wins (Percentile)'] = df_p.apply(lambda r: fmt(r['Win_C'], r['Total_Opp']), axis=1)
        df_p['Losses'] = df_p.apply(lambda r: fmt(r['Loss_C'], r['Total_Opp']), axis=1)
        df_p['Ties'] = df_p.apply(lambda r: fmt(r['Tie_C'], r['Total_Opp']), axis=1)
        df_p['sort_val'] = df_p['Win_C'] * 100.0 / df_p['Total_Opp']
        cols = ['Player', 'Season', 'Wins (Percentile)', 'Losses', 'Ties', 'Clean_Loss'] + (['Runs', 'Ave', 'SR'] if disc_p == "Batting" else ['Wkts', 'Ave', 'Econ'])
        st.dataframe(df_p.sort_values("sort_val", ascending=False)[cols], use_container_width=True, hide_index=True)

# --- SECTION 4: PLAYER DETAILS ---
elif st.session_state.nav_choice == "👤 Player Details":
    st.header("👤 Player Profile Search")
    p_names = sorted(list(set(pd.read_sql("SELECT DISTINCT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT DISTINCT Player FROM bowling", conn)['Player'])))
    target_player = st.selectbox("Select Player Name", p_names)
    if target_player:
        st.subheader(f"🏏 Batting Career: {target_player}")
        b_q = f"SELECT A.Season, A.Runs, A.Ave, A.SR, (SELECT COUNT(*) FROM batting) as Total_Raw, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM batting B WHERE B.Runs > A.Runs AND B.Ave > A.Ave AND B.SR > A.SR) as Clean_Loss FROM batting A WHERE A.Player = '{target_player}'"
        df_b = pd.read_sql(b_q, conn)
        if not df_b.empty:
            df_b['Total_Opp'] = df_b['Total_Raw'] - 1
            df_b['Tie_C'] = (df_b['Total_Raw'] - df_b['Win_C'] - df_b['Loss_C']) - 1
            df_b['Wins %'] = df_b.apply(lambda r: fmt(r['Win_C'], r['Total_Opp']), axis=1)
            df_b['Losses %'] = df_b.apply(lambda r: fmt(r['Loss_C'], r['Total_Opp']), axis=1)
            df_b['Ties %'] = df_b.apply(lambda r: fmt(r['Tie_C'], r['Total_Opp']), axis=1)
            evt_b = st.dataframe(df_b[['Season', 'Runs', 'Ave', 'SR', 'Wins %', 'Losses %', 'Ties %', 'Clean_Loss']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="sel_b_det")
            if evt_b.selection.rows:
                sel = df_b.iloc[evt_b.selection.rows[0]]
                st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = sel['Runs'], sel['Ave'], sel['SR']
                st.session_state.nav_choice = "Batting Milestones"; st.rerun()

        st.subheader(f"⚽ Bowling Career: {target_player}")
        w_q = f"SELECT A.Season, A.Wkts, A.Ave, A.Econ, (SELECT COUNT(*) FROM bowling) as Total_Raw, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM bowling B WHERE B.Wkts > A.Wkts AND B.Ave < A.Ave AND B.Econ < A.Econ) as Clean_Loss FROM bowling A WHERE A.Player = '{target_player}'"
        df_w = pd.read_sql(w_q, conn)
        if not df_w.empty:
            df_w['Total_Opp'] = df_w['Total_Raw'] - 1
            df_w['Tie_C'] = (df_w['Total_Raw'] - df_w['Win_C'] - df_w['Loss_C']) - 1
            df_w['Wins %'] = df_w.apply(lambda r: fmt(r['Win_C'], r['Total_Opp']), axis=1)
            df_w['Losses %'] = df_w.apply(lambda r: fmt(r['Loss_C'], r['Total_Opp']), axis=1)
            df_w['Ties %'] = df_w.apply(lambda r: fmt(r['Tie_C'], r['Total_Opp']), axis=1)
            evt_w = st.dataframe(df_w[['Season', 'Wkts', 'Ave', 'Econ', 'Wins %', 'Losses %', 'Ties %', 'Clean_Loss']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="sel_w_det")
            if evt_w.selection.rows:
                sel = df_w.iloc[evt_w.selection.rows[0]]
                st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = sel['Wkts'], sel['Ave'], sel['Econ']
                st.session_state.nav_choice = "Bowling Milestones"; st.rerun()

# --- SECTION 5: SQUAD COMPARISON ---
elif st.session_state.nav_choice == "🏟️ Squad Comparison":
    st.header("🏟️ Squad Comparison")
    with st.expander("🛠️ Manage Squad Codes (Save/Load/Clear)"):
        col_m1, col_m2 = st.columns(2)
        if col_m1.button("🗑️ Clear All Squads"): st.session_state.squad_a, st.session_state.squad_b = [], []; st.rerun()
        squad_data = {"a": st.session_state.squad_a, "b": st.session_state.squad_b}
        col_m2.text_input("📋 Your Squad Code", value=json.dumps(squad_data))
        load_code = st.text_input("📥 Paste Squad Code to load:")
        if st.button("🔄 Load Squads"):
            try: loaded = json.loads(load_code); st.session_state.squad_a, st.session_state.squad_b = loaded['a'], loaded['b']; st.rerun()
            except: st.error("Invalid Code")

    c1, c2 = st.columns(2)
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    with c1:
        new_a = st.selectbox("Add Player to A", [""] + all_p, key="sq_a")
        if new_a and new_a not in st.session_state.squad_a and len(st.session_state.squad_a) < 25: st.session_state.squad_a.append(new_a); st.rerun()
        st.session_state.squad_a = st.multiselect("Manage Squad A", st.session_state.squad_a, default=st.session_state.squad_a)
    with c2:
        new_b = st.selectbox("Add Player to B", [""] + all_p, key="sq_b")
        if new_b and new_b not in st.session_state.squad_b and len(st.session_state.squad_b) < 25: st.session_state.squad_b.append(new_b); st.rerun()
        st.session_state.squad_b = st.multiselect("Manage Squad B", st.session_state.squad_b, default=st.session_state.squad_b)

    if st.session_state.squad_a and st.session_state.squad_b:
        st.divider()
        dir_choice = st.radio("Comparison Direction:", ["Squad A is Benchmark", "Squad B is Benchmark"], horizontal=True)
        source, target = (st.session_state.squad_a, st.session_state.squad_b) if "A" in dir_choice else (st.session_state.squad_b, st.session_state.squad_a)
        comp_p = st.selectbox("Pick Benchmark Player:", source, key=f"bench_{dir_choice}")
        if comp_p:
            b_y, w_y = pd.read_sql(f"SELECT Season FROM batting WHERE Player='{comp_p}'", conn)['Season'].tolist(), pd.read_sql(f"SELECT Season FROM bowling WHERE Player='{comp_p}'", conn)['Season'].tolist()
            opts = (["Batting"] if b_y else []) + (["Bowling"] if w_y else [])
            disc = st.radio("Benchmark Type:", opts, horizontal=True)
            y = b_y if disc == "Batting" else w_y
            t_y = st.selectbox("Pick Benchmark Year:", y)
            if t_y:
                tbl = "batting" if disc == "Batting" else "bowling"
                bench = pd.read_sql(f"SELECT * FROM {tbl} WHERE Player='{comp_p}' AND Season='{t_y}'", conn).iloc[0]
                st.info(f"📍 **Benchmark Details:** {comp_p} ({t_y})")
                cols = st.columns(3)
                if disc == "Batting":
                    tr, ta, ts = bench['Runs'], bench['Ave'], bench['SR']
                    cols[0].metric("Runs", tr); cols[1].metric("Avg", ta); cols[2].metric("SR", ts)
                    q = f"SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta} THEN 1 ELSE 0 END + CASE WHEN SR > {ts} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta} THEN 1 ELSE 0 END + CASE WHEN SR = {ts} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta} THEN 1 ELSE 0 END + CASE WHEN SR < {ts} THEN 1 ELSE 0 END) as LossesA FROM batting WHERE Player IN ('" + "','".join(target) + "') ORDER BY WinsA DESC, Runs DESC"
                else:
                    tw, tav, te = bench['Wkts'], bench['Ave'], bench['Econ']
                    cols[0].metric("Wkts", tw); cols[1].metric("Avg", tav); cols[2].metric("Econ", te)
                    q = f"SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {tw} THEN 1 ELSE 0 END + CASE WHEN Ave < {tav} THEN 1 ELSE 0 END + CASE WHEN Econ < {te} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {tw} THEN 1 ELSE 0 END + CASE WHEN Ave = {tav} THEN 1 ELSE 0 END + CASE WHEN Econ = {te} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {tw} THEN 1 ELSE 0 END + CASE WHEN Ave > {tav} THEN 1 ELSE 0 END + CASE WHEN Econ > {te} THEN 1 ELSE 0 END) as LossesA FROM bowling WHERE Player IN ('" + "','".join(target) + "') ORDER BY WinsA DESC, Wickets DESC"
                display_styled_results(pd.read_sql(q, conn), f"Squad Comparison ({comp_p})")
conn.close()
