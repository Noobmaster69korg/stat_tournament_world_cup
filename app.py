import streamlit as st
import sqlite3
import pandas as pd

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

# Initialize Benchmark values in session state
if "bat_runs_a" not in st.session_state: st.session_state.bat_runs_a = 300
if "bat_avg_a" not in st.session_state: st.session_state.bat_avg_a = 40.0
if "bat_sr_a" not in st.session_state: st.session_state.bat_sr_a = 90.0
if "bowl_w_a" not in st.session_state: st.session_state.bowl_w_a = 15
if "bowl_a_a" not in st.session_state: st.session_state.bowl_a_a = 25.0
if "bowl_e_a" not in st.session_state: st.session_state.bowl_e_a = 5.0

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
        sub_df = df[df['Result_Profile'] == profile].drop(columns=['WinsA', 'TiesA', 'LossesA', 'Result_Profile', 'WinsB', 'TiesB'])
        st.markdown(f"#### {profile} ({len(sub_df)} records)")
        st.dataframe(sub_df, use_container_width=True, hide_index=True)

# --- NAVIGATION MENU ---
nav_options = ["Batting Milestones", "Bowling Milestones", "📈 Player Analytics", "👤 Player Details"]
st.session_state.nav_choice = st.radio("Select Section:", nav_options, index=nav_options.index(st.session_state.nav_choice), horizontal=True)
st.divider()

# --- TAB 1: BATTING ---
if st.session_state.nav_choice == "Batting Milestones":
    st.header("🏏 Batting Milestones")
    filter_mode_bat = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Set A (Primary)")
        tr1a = st.number_input("Min Runs (A)", value=st.session_state.bat_runs_a)
        ta1a = st.number_input("Min Average (A)", value=st.session_state.bat_avg_a)
        ts1a = st.number_input("Min Strike Rate (A)", value=st.session_state.bat_sr_a)
        st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = tr1a, ta1a, ts1a
    with col_b:
        st.subheader("Set B (Secondary)")
        tr1b, ta1b, ts1b = st.number_input("Min Runs (B)", 500), st.number_input("Min Average (B)", 50.0), st.number_input("Min Strike Rate (B)", 100.0)
    
    bat_query = f"WITH Base AS (SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1a} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1a} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR < {ts1a} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Runs > {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1b} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Runs = {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1b} THEN 1 ELSE 0 END) as TiesB FROM batting) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in filter_mode_bat else ''} ORDER BY WinsA DESC, TiesA DESC, Runs DESC"
    display_styled_results(pd.read_sql(bat_query, conn), "Batting")

# --- TAB 2: BOWLING ---
elif st.session_state.nav_choice == "Bowling Milestones":
    st.header("⚽ Bowling Milestones")
    filter_mode_bowl = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("Set A (Primary)")
        twa = st.number_input("Min Wickets (A)", value=st.session_state.bowl_w_a)
        taa = st.number_input("Max Average (A)", value=st.session_state.bowl_a_a)
        tea = st.number_input("Max Economy (A)", value=st.session_state.bowl_e_a)
        st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = twa, taa, tea
    with col_d:
        st.subheader("Set B (Secondary)")
        twb, tab, teb = st.number_input("Min Wickets (B)", 20), st.number_input("Max Average (B)", 20.0), st.number_input("Max Economy (B)", 4.5)
    
    bowl_query = f"WITH Base AS (SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {twa} THEN 1 ELSE 0 END + CASE WHEN Ave < {taa} THEN 1 ELSE 0 END + CASE WHEN Econ < {tea} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {twa} THEN 1 ELSE 0 END + CASE WHEN Ave = {taa} THEN 1 ELSE 0 END + CASE WHEN Econ = {tea} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {twa} THEN 1 ELSE 0 END + CASE WHEN Ave > {taa} THEN 1 ELSE 0 END + CASE WHEN Econ > {tea} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Wkts > {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Wkts = {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as TiesB FROM bowling) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in filter_mode_bowl else ''} ORDER BY WinsA DESC, TiesA DESC, Wickets DESC"
    display_styled_results(pd.read_sql(bowl_query, conn), "Bowling")

# --- TAB 3: ANALYTICS ---
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
        f_view = ['Player', 'Season', 'Wins (Percentile)', 'Losses', 'Ties', 'Clean_Loss'] + (['Runs', 'Ave', 'SR'] if disc_p == "Batting" else ['Wkts', 'Ave', 'Econ'])
        st.dataframe(df_p.sort_values("sort_val", ascending=False)[f_view], use_container_width=True, hide_index=True)

# --- TAB 4: PLAYER DETAILS ---
elif st.session_state.nav_choice == "👤 Player Details":
    st.header("👤 Player Profile Search")
    st.info("💡 Click a row to set those stats as benchmarks and jump to Milestones.")
    p_names = sorted(list(set(pd.read_sql("SELECT DISTINCT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT DISTINCT Player FROM bowling", conn)['Player'])))
    target_player = st.selectbox("Select Player Name", p_names)
    if target_player:
        # Batting
        st.subheader(f"🏏 Batting Career: {target_player}")
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
        # Bowling
        st.subheader(f"⚽ Bowling Career: {target_player}")
        w_q = f"SELECT A.Season, A.Wkts, A.Ave, A.Econ, (SELECT COUNT(*) FROM bowling) as Total_Raw, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM bowling B WHERE B.Wkts > A.Wkts AND B.Ave < A.Ave AND B.Econ < A.Econ) as Clean_Loss FROM bowling A WHERE A.Player = '{target_player}'"
        df_w = pd.read_sql(w_q, conn)
        if not df_w.empty:
            df_w['Total_Opp'] = df_w['Total_Raw'] - 1
            df_w['Tie_C'] = (df_w['Total_Raw'] - df_w['Win_C'] - df_w['Loss_C']) - 1
            df_w['Wins %'] = df_w.apply(lambda r: fmt(r['Win_C'], r['Total_Opp']), axis=1)
            df_w['Losses %'] = df_w.apply(lambda r: fmt(r['Loss_C'], r['Total_Opp']), axis=1)
            df_w['Ties %'] = df_w.apply(lambda r: fmt(r['Tie_C'], r['Total_Opp']), axis=1)
            evt_w = st.dataframe(df_w[['Season', 'Wkts', 'Ave', 'Econ', 'Wins %', 'Losses %', 'Ties %', 'Clean_Loss']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="sel_w")
            if evt_w.selection.rows:
                sel = df_w.iloc[evt_w.selection.rows[0]]
                st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = sel['Wkts'], sel['Ave'], sel['Econ']
                st.session_state.nav_choice = "Bowling Milestones"
                st.rerun()

conn.close()
