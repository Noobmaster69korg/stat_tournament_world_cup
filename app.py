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
        sub_df = df[df['Result_Profile'] == profile].drop(columns=cols_to_drop)
        st.markdown(f"#### {profile} ({len(sub_df)} records)")
        st.dataframe(sub_df, use_container_width=True, hide_index=True)

# --- NAVIGATION MENU ---
nav_options = ["Batting Milestones", "Bowling Milestones", "📈 Player Analytics", "👤 Player Details", "🏟️ Squad Comparison"]
st.session_state.nav_choice = st.radio("Select Section:", nav_options, index=nav_options.index(st.session_state.nav_choice), horizontal=True)
st.divider()

# --- BATTING/BOWLING/ANALYTICS/DETAILS (Tabs 1-4 Logic) ---
if st.session_state.nav_choice == "Batting Milestones":
    st.header("🏏 Batting Milestones")
    tr1a = st.number_input("Min Runs (A)", value=st.session_state.bat_runs_a)
    ta1a = st.number_input("Min Average (A)", value=st.session_state.bat_avg_a)
    ts1a = st.number_input("Min Strike Rate (A)", value=st.session_state.bat_sr_a)
    st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = tr1a, ta1a, ts1a
    bat_query = f"WITH Base AS (SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1a} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1a} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR < {ts1a} THEN 1 ELSE 0 END) as LossesA FROM batting) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 ORDER BY WinsA DESC, Runs DESC"
    display_styled_results(pd.read_sql(bat_query, conn), "Batting")

elif st.session_state.nav_choice == "Bowling Milestones":
    st.header("⚽ Bowling Milestones")
    twa = st.number_input("Min Wickets (A)", value=st.session_state.bowl_w_a)
    taa = st.number_input("Max Average (A)", value=st.session_state.bowl_a_a)
    tea = st.number_input("Max Economy (A)", value=st.session_state.bowl_e_a)
    st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = twa, taa, tea
    bowl_query = f"WITH Base AS (SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {twa} THEN 1 ELSE 0 END + CASE WHEN Ave < {taa} THEN 1 ELSE 0 END + CASE WHEN Econ < {tea} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {twa} THEN 1 ELSE 0 END + CASE WHEN Ave = {taa} THEN 1 ELSE 0 END + CASE WHEN Econ = {tea} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {twa} THEN 1 ELSE 0 END + CASE WHEN Ave > {taa} THEN 1 ELSE 0 END + CASE WHEN Econ > {tea} THEN 1 ELSE 0 END) as LossesA FROM bowling) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 ORDER BY WinsA DESC, Wickets DESC"
    display_styled_results(pd.read_sql(bowl_query, conn), "Bowling")

elif st.session_state.nav_choice == "📈 Player Analytics":
    st.header("📈 Advanced Analytics")
    ana_choice = st.radio("Choose Analysis:", ["Career Consistency", "Global Season Ranking"], horizontal=True)
    if ana_choice == "Career Consistency":
        disc_cons = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True, key="dc")
        c1, c2, c3 = st.columns(3)
        if disc_cons == "Batting":
            r_c, a_c, s_c = c1.number_input("Min Runs", 250), c2.number_input("Min Avg", 35.0), c3.number_input("Min SR", 85.0)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Runs >= {r_c}) + (Ave >= {a_c}) + (SR >= {s_c})) >= 2 THEN 1 ELSE 0 END) as Successful FROM batting GROUP BY Player HAVING Successful > 0"
        else:
            w_c, av_c, e_c = c1.number_input("Min Wkts", 12), c2.number_input("Max Avg", 28.0), c3.number_input("Max Econ", 5.5)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Wkts >= {w_c}) + (Ave <= {av_c}) + (Econ <= {e_c})) >= 2 THEN 1 ELSE 0 END) as Successful FROM bowling GROUP BY Player HAVING Successful > 0"
        df_c = pd.read_sql(q, conn)
        df_c['Win %'] = (df_c['Successful'] * 100.0 / df_c['Total']).round(2)
        st.dataframe(df_c.sort_values("Win %", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.subheader("🏆 Global Pairwise Rankings")
        disc_p = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True, key="dp")
        p_q = f"SELECT A.Player, A.Season, A.Runs, A.Ave, A.SR, (SELECT COUNT(*) FROM batting) as Total_Raw, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM batting B WHERE B.Runs > A.Runs AND B.Ave > A.Ave AND B.SR > A.SR) as Clean_Loss FROM batting A" if disc_p == "Batting" else f"SELECT A.Player, A.Season, A.Wkts, A.Ave, A.Econ, (SELECT COUNT(*) FROM bowling) as Total_Raw, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM bowling B WHERE B.Wkts > A.Wkts AND B.Ave < A.Ave AND B.Econ < A.Econ) as Clean_Loss FROM bowling A"
        df_p = pd.read_sql(p_q, conn)
        df_p['Total_Opp'] = df_p['Total_Raw'] - 1
        df_p['Tie_C'] = (df_p['Total_Raw'] - df_p['Win_C'] - df_p['Loss_C']) - 1
        df_p['Wins (Percentile)'] = df_p.apply(lambda r: fmt(r['Win_C'], r['Total_Opp']), axis=1)
        df_p['Losses'] = df_p.apply(lambda r: fmt(r['Loss_C'], r['Total_Opp']), axis=1)
        df_p['Ties'] = df_p.apply(lambda r: fmt(r['Tie_C'], r['Total_Opp']), axis=1)
        df_p['sort_val'] = df_p['Win_C'] * 100.0 / df_p['Total_Opp']
        st.dataframe(df_p.sort_values("sort_val", ascending=False)[['Player', 'Season', 'Wins (Percentile)', 'Losses', 'Ties', 'Clean_Loss', 'Runs', 'Ave', 'SR']], use_container_width=True, hide_index=True)

elif st.session_state.nav_choice == "👤 Player Details":
    p_names = sorted(list(set(pd.read_sql("SELECT DISTINCT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT DISTINCT Player FROM bowling", conn)['Player'])))
    target_player = st.selectbox("Select Player Name", p_names)
    if target_player:
        b_q = f"SELECT A.Season, A.Runs, A.Ave, A.SR, (SELECT COUNT(*) FROM batting) as Total_Raw, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM batting B WHERE B.Runs > A.Runs AND B.Ave > A.Ave AND B.SR > A.SR) as Clean_Loss FROM batting A WHERE A.Player = '{target_player}'"
        df_b = pd.read_sql(b_q, conn)
        if not df_b.empty:
            df_b['Total_Opp'] = df_b['Total_Raw'] - 1
            df_b['Tie_C'] = (df_b['Total_Raw'] - df_b['Win_C'] - df_b['Loss_C']) - 1
            df_b['Wins %'] = df_b.apply(lambda r: fmt(r['Win_C'], r['Total_Opp']), axis=1)
            df_b['Losses %'] = df_b.apply(lambda r: fmt(r['Loss_C'], r['Total_Opp']), axis=1)
            df_b['Ties %'] = df_b.apply(lambda r: fmt(r['Tie_C'], r['Total_Opp']), axis=1)
            evt_b = st.dataframe(df_b[['Season', 'Runs', 'Ave', 'SR', 'Wins %', 'Losses %', 'Ties %', 'Clean_Loss']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="sel_b")
            if evt_b.selection.rows:
                sel = df_b.iloc[evt_b.selection.rows[0]]
                st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = sel['Runs'], sel['Ave'], sel['SR']
                st.session_state.nav_choice = "Batting Milestones"
                st.rerun()

# --- SECTION 5: SQUAD COMPARISON ---
elif st.session_state.nav_choice == "🏟️ Squad Comparison":
    st.header("🏟️ Squad Comparison")
    
    with st.expander("🛠️ Manage Squad Codes (Save/Load/Clear)"):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("🗑️ Clear All Squads"):
                st.session_state.squad_a, st.session_state.squad_b = [], []
                st.rerun()
        with col_m2:
            squad_data = {"a": st.session_state.squad_a, "b": st.session_state.squad_b}
            st.text_input("📋 Your Squad Code", value=json.dumps(squad_data))
        load_code = st.text_input("📥 Paste Squad Code to load:")
        if st.button("🔄 Load Squads"):
            try:
                loaded = json.loads(load_code)
                st.session_state.squad_a, st.session_state.squad_b = loaded['a'], loaded['b']
                st.rerun()
            except: st.error("Invalid Code")

    col_build1, col_build2 = st.columns(2)
    all_players = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    
    with col_build1:
        st.subheader(f"Squad A ({len(st.session_state.squad_a)}/25)")
        new_p_a = st.selectbox("Add Player to A", [""] + all_players, key="add_a")
        if new_p_a and new_p_a not in st.session_state.squad_a and len(st.session_state.squad_a) < 25:
            st.session_state.squad_a.append(new_p_a); st.rerun()
        st.session_state.squad_a = st.multiselect("Manage Squad A", st.session_state.squad_a, default=st.session_state.squad_a)

    with col_build2:
        st.subheader(f"Squad B ({len(st.session_state.squad_b)}/25)")
        new_p_b = st.selectbox("Add Player to B", [""] + all_players, key="add_b")
        if new_p_b and new_p_b not in st.session_state.squad_b and len(st.session_state.squad_b) < 25:
            st.session_state.squad_b.append(new_p_b); st.rerun()
        st.session_state.squad_b = st.multiselect("Manage Squad B", st.session_state.squad_b, default=st.session_state.squad_b)

    st.divider()

    if st.session_state.squad_a and st.session_state.squad_b:
        direction = st.radio("Comparison Direction:", ["Benchmark from Squad A vs Squad B", "Benchmark from Squad B vs Squad A"], horizontal=True)
        
        # Determine source and target squads based on toggle
        source_squad = st.session_state.squad_a if "A vs B" in direction else st.session_state.squad_b
        target_squad = st.session_state.squad_b if "A vs B" in direction else st.session_state.squad_a
        
        # Bench Selection (Unique key ensures refresh on toggle)
        comp_player = st.selectbox("Pick Benchmark Player:", source_squad, key=f"bench_player_{direction}")
        
        if comp_player:
            b_years = pd.read_sql(f"SELECT Season FROM batting WHERE Player='{comp_player}'", conn)['Season'].tolist()
            w_years = pd.read_sql(f"SELECT Season FROM bowling WHERE Player='{comp_player}'", conn)['Season'].tolist()
            opts = (["Batting"] if b_years else []) + (["Bowling"] if w_years else [])
            discipline = st.radio("Benchmark Type:", opts, horizontal=True)
            years = b_years if discipline == "Batting" else w_years
            target_year = st.selectbox("Pick Benchmark Year:", years)
            
            if target_year:
                table = "batting" if discipline == "Batting" else "bowling"
                bench = pd.read_sql(f"SELECT * FROM {table} WHERE Player='{comp_player}' AND Season='{target_year}'", conn).iloc[0]
                
                # --- NEW: DISPLAY BENCHMARK STATS ---
                st.success(f"**Benchmark Set:** {comp_player} ({target_year})")
                b_cols = st.columns(3)
                if discipline == "Batting":
                    tr, ta, ts = bench['Runs'], bench['Ave'], bench['SR']
                    b_cols[0].metric("Runs", tr); b_cols[1].metric("Average", ta); b_cols[2].metric("Strike Rate", ts)
                else:
                    tw, tav, te = bench['Wkts'], bench['Ave'], bench['Econ']
                    b_cols[0].metric("Wickets", tw); b_cols[1].metric("Average", tav); b_cols[2].metric("Economy", te)
                
                # Comparison Query
                target_str = "('" + "','".join(target_squad) + "')"
                if discipline == "Batting":
                    q = f"SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta} THEN 1 ELSE 0 END + CASE WHEN SR > {ts} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta} THEN 1 ELSE 0 END + CASE WHEN SR = {ts} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta} THEN 1 ELSE 0 END + CASE WHEN SR < {ts} THEN 1 ELSE 0 END) as LossesA FROM batting WHERE Player IN {target_str} ORDER BY WinsA DESC, Runs DESC"
                else:
                    q = f"SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {tw} THEN 1 ELSE 0 END + CASE WHEN Ave < {tav} THEN 1 ELSE 0 END + CASE WHEN Econ < {te} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {tw} THEN 1 ELSE 0 END + CASE WHEN Ave = {tav} THEN 1 ELSE 0 END + CASE WHEN Econ = {te} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {tw} THEN 1 ELSE 0 END + CASE WHEN Ave > {tav} THEN 1 ELSE 0 END + CASE WHEN Econ > {te} THEN 1 ELSE 0 END) as LossesA FROM bowling WHERE Player IN {target_str} ORDER BY WinsA DESC, Wickets DESC"
                
                display_styled_results(pd.read_sql(q, conn), f"Against {comp_player} ({target_year})")
    else:
        st.info("Add players to both squads to begin.")

conn.close()
