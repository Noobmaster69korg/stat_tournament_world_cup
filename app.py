import streamlit as st
import sqlite3
import pandas as pd

# Connect to the database
conn = sqlite3.connect('cricket_stats.db')

st.set_page_config(page_title="World Cup Stats Tracker", layout="wide")

# --- PASSWORD PROTECTION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pw = st.text_input("Enter Password to Access", type="password")
    if pw == "your_secret_password": # Change this to your actual password
        st.session_state.authenticated = True
        st.rerun()
    else:
        if pw: st.error("Access Denied")
        st.stop()

# --- INITIALIZE SESSION STATE FOR NAVIGATION AND INPUTS ---
if "nav_tab" not in st.session_state:
    st.session_state.nav_tab = "👤 Player Details"

# Default values for inputs
defaults = {
    "tr1a": 300, "ta1a": 40.0, "ts1a": 90.0,
    "twa": 15, "taa": 25.0, "tea": 5.0
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- GLOBAL HELPER FUNCTIONS ---
def fmt(count, total):
    if total <= 0: return "0 (0.0%)"
    perc = (count * 100.0 / total)
    return f"{int(count)} ({perc:.1f}%)"

def get_profile_label(w, t, l):
    if w == 3: return "🏆 Beat all 3 categories"
    if w == 2 and t == 1: return "⭐ Beat 2 categories, Tied 1 category"
    if w == 2 and l == 1: return "✅ Beat 2 categories, Lost 1 category"
    return "Other/Ties"

def display_styled_results(df, title_prefix):
    if df.empty:
        st.warning(f"No players found matching these criteria.")
        return
    df['Result_Profile'] = df.apply(lambda row: get_profile_label(row['WinsA'], row['TiesA'], row['LossesA']), axis=1)
    st.subheader(f"📊 Summary ({title_prefix})")
    for profile, count in df['Result_Profile'].value_counts().items():
        st.write(f"- **{count}** records: {profile}")
    st.divider()
    for profile in sorted(df['Result_Profile'].unique(), reverse=True):
        sub_df = df[df['Result_Profile'] == profile].drop(columns=['WinsA', 'TiesA', 'LossesA', 'Result_Profile', 'WinsB', 'TiesB'])
        st.markdown(f"#### {profile} ({len(sub_df)} records)")
        st.dataframe(sub_df, use_container_width=True, hide_index=True)

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("Navigation")
# If a jump happened, the radio will sync with st.session_state.nav_tab
choice = st.sidebar.radio("Go to:", ["👤 Player Details", "Batting Milestones", "Bowling Milestones", "📈 Player Analytics"], key="nav_radio", index=["👤 Player Details", "Batting Milestones", "Bowling Milestones", "📈 Player Analytics"].index(st.session_state.nav_tab))
st.session_state.nav_tab = choice

# --- PAGE LOGIC ---

if st.session_state.nav_tab == "Batting Milestones":
    st.header("🏏 Batting Milestones")
    filter_mode_bat = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Set A (Primary)")
        tr1a = st.number_input("Min Runs (A)", value=st.session_state.tr1a, key="tr1a_input")
        ta1a = st.number_input("Min Avg (A)", value=st.session_state.ta1a, key="ta1a_input")
        ts1a = st.number_input("Min SR (A)", value=st.session_state.ts1a, key="ts1a_input")
        # Update session state if user manually changes inputs
        st.session_state.tr1a, st.session_state.ta1a, st.session_state.ts1a = tr1a, ta1a, ts1a
    with col_b:
        st.subheader("Set B (Secondary)")
        tr1b, ta1b, ts1b = st.number_input("Min Runs (B)", 500), st.number_input("Min Avg (B)", 50.0), st.number_input("Min SR (B)", 100.0)
    
    q = f"WITH Base AS (SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1a} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1a} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR < {ts1a} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Runs > {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1b} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Runs = {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1b} THEN 1 ELSE 0 END) as TiesB FROM batting) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in filter_mode_bat else ''} ORDER BY WinsA DESC, Runs DESC"
    display_styled_results(pd.read_sql(q, conn), "Batting")

elif st.session_state.nav_tab == "Bowling Milestones":
    st.header("⚽ Bowling Milestones")
    filter_mode_bowl = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("Set A (Primary)")
        twa = st.number_input("Min Wickets (A)", value=st.session_state.twa, key="twa_input")
        taa = st.number_input("Max Avg (A)", value=st.session_state.taa, key="taa_input")
        tea = st.number_input("Max Econ (A)", value=st.session_state.tea, key="tea_input")
        st.session_state.twa, st.session_state.taa, st.session_state.tea = twa, taa, tea
    with col_d:
        st.subheader("Set B (Secondary)")
        twb, tab, teb = st.number_input("Min Wickets (B)", 20), st.number_input("Max Avg (B)", 20.0), st.number_input("Max Econ (B)", 4.5)
    
    q = f"WITH Base AS (SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {twa} THEN 1 ELSE 0 END + CASE WHEN Ave < {taa} THEN 1 ELSE 0 END + CASE WHEN Econ < {tea} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {twa} THEN 1 ELSE 0 END + CASE WHEN Ave = {taa} THEN 1 ELSE 0 END + CASE WHEN Econ = {tea} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {twa} THEN 1 ELSE 0 END + CASE WHEN Ave > {taa} THEN 1 ELSE 0 END + CASE WHEN Econ > {tea} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Wkts > {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Wkts = {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as TiesB FROM bowling) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in filter_mode_bowl else ''} ORDER BY WinsA DESC, Wickets DESC"
    display_styled_results(pd.read_sql(q, conn), "Bowling")

elif st.session_state.nav_tab == "📈 Player Analytics":
    st.header("📈 Advanced Analytics")
    # ... (Keep previous Consistency and Pairwise Rankings logic here) ...
    st.info("Pairwise rankings and Career Consistency features are active.")
    # [Insert Tab 3 logic from previous code here]

elif st.session_state.nav_tab == "👤 Player Details":
    st.header("👤 Player Profile Search")
    st.info("💡 **Tip:** Click a row to automatically set those stats as benchmarks and jump to the Milestones tab.")
    
    all_players = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    target_player = st.selectbox("Select Player", all_players)

    if target_player:
        # --- BATTING DETAILS ---
        st.subheader(f"🏏 Batting Career: {target_player}")
        b_q = f"SELECT A.Season, A.Runs, A.Ave, A.SR, (SELECT COUNT(*) FROM batting) as Total_Raw, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END)) >= 2) as Loss_C FROM batting A WHERE A.Player = '{target_player}'"
        df_b = pd.read_sql(b_q, conn)
        if not df_b.empty:
            df_b['Total_Opp'] = df_b['Total_Raw'] - 1
            df_b['Ties_C'] = (df_b['Total_Raw'] - df_b['Win_C'] - df_b['Loss_C']) - 1
            df_b['Wins (Percentile)'] = df_b.apply(lambda r: fmt(r['Win_C'], r['Total_Opp']), axis=1)
            
            # Interactive Selection for Batting
            event_b = st.dataframe(df_b[['Season', 'Runs', 'Ave', 'SR', 'Wins (Percentile)']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single_row")
            
            if event_b.selection.rows:
                selected_index = event_b.selection.rows[0]
                row = df_b.iloc[selected_index]
                # Update Session State
                st.session_state.tr1a, st.session_state.ta1a, st.session_state.ts1a = row['Runs'], row['Ave'], row['SR']
                st.session_state.nav_tab = "Batting Milestones"
                st.rerun()

        # --- BOWLING DETAILS ---
        st.subheader(f"⚽ Bowling Career: {target_player}")
        w_q = f"SELECT A.Season, A.Wkts, A.Ave, A.Econ, (SELECT COUNT(*) FROM bowling) as Total_Raw, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END)) >= 2) as Loss_C FROM bowling A WHERE A.Player = '{target_player}'"
        df_w = pd.read_sql(w_q, conn)
        if not df_w.empty:
            df_w['Total_Opp'] = df_w['Total_Raw'] - 1
            df_w['Ties_C'] = (df_w['Total_Raw'] - df_w['Win_C'] - df_w['Loss_C']) - 1
            df_w['Wins (Percentile)'] = df_w.apply(lambda r: fmt(r['Win_C'], r['Total_Opp']), axis=1)
            
            # Interactive Selection for Bowling
            event_w = st.dataframe(df_w[['Season', 'Wkts', 'Ave', 'Econ', 'Wins (Percentile)']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single_row")
            
            if event_w.selection.rows:
                selected_index = event_w.selection.rows[0]
                row = df_w.iloc[selected_index]
                # Update Session State
                st.session_state.twa, st.session_state.taa, st.session_state.tea = row['Wkts'], row['Ave'], row['Econ']
                st.session_state.nav_tab = "Bowling Milestones"
                st.rerun()

conn.close()
