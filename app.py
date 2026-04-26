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
if "nav_choice" not in st.session_state: st.session_state.nav_choice = "Batting Milestones"
# Benchmark defaults
for k, v in {"bat_runs_a":300, "bat_avg_a":40.0, "bat_sr_a":90.0, "bowl_w_a":15, "bowl_a_a":25.0, "bowl_e_a":5.0}.items():
    if k not in st.session_state: st.session_state[k] = v
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
nav_options = ["Batting Milestones", "Bowling Milestones", "📈 Player Analytics", "👤 Player Details", "🏟️ Squad Comparison", "🧬 Format Analysis"]
st.session_state.nav_choice = st.radio("Select Section:", nav_options, index=nav_options.index(st.session_state.nav_choice), horizontal=True)
st.divider()

# --- TABS 1-5 (LOGIC PRESERVED) ---
if st.session_state.nav_choice == "Batting Milestones":
    st.header("🏏 Batting Milestones")
    tr1a = st.number_input("Min Runs (A)", value=st.session_state.bat_runs_a, key="bat_r")
    ta1a = st.number_input("Min Avg (A)", value=st.session_state.bat_avg_a, key="bat_a")
    ts1a = st.number_input("Min SR (A)", value=st.session_state.bat_sr_a, key="bat_s")
    st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = tr1a, ta1a, ts1a
    bat_query = f"WITH Base AS (SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1a} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1a} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR < {ts1a} THEN 1 ELSE 0 END) as LossesA FROM batting) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 ORDER BY WinsA DESC, Runs DESC"
    display_styled_results(pd.read_sql(bat_query, conn), "Batting")

elif st.session_state.nav_choice == "Bowling Milestones":
    st.header("⚽ Bowling Milestones")
    twa = st.number_input("Min Wickets (A)", value=st.session_state.bowl_w_a, key="bowl_w")
    taa = st.number_input("Max Avg (A)", value=st.session_state.bowl_a_a, key="bowl_a")
    tea = st.number_input("Max Econ (A)", value=st.session_state.bowl_e_a, key="bowl_e")
    st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = twa, taa, tea
    bowl_query = f"WITH Base AS (SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {twa} THEN 1 ELSE 0 END + CASE WHEN Ave < {taa} THEN 1 ELSE 0 END + CASE WHEN Econ < {tea} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {twa} THEN 1 ELSE 0 END + CASE WHEN Ave = {taa} THEN 1 ELSE 0 END + CASE WHEN Econ = {tea} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {twa} THEN 1 ELSE 0 END + CASE WHEN Ave > {taa} THEN 1 ELSE 0 END + CASE WHEN Econ > {tea} THEN 1 ELSE 0 END) as LossesA FROM bowling) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 ORDER BY WinsA DESC, Wickets DESC"
    display_styled_results(pd.read_sql(bowl_query, conn), "Bowling")

elif st.session_state.nav_choice == "📈 Player Analytics":
    st.header("📈 Advanced Analytics")
    ana_choice = st.radio("Choose Analysis:", ["Career Consistency", "Global Season Ranking"], horizontal=True)
    if ana_choice == "Career Consistency":
        disc_cons = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True, key="dc_tab3")
        c1, c2, c3 = st.columns(3)
        if disc_cons == "Batting":
            r_c, a_c, s_c = c1.number_input("Min Runs", 250), c2.number_input("Min Avg", 35.0), c3.number_input("Min SR", 85.0)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Runs >= {r_c}) + (Ave >= {a_c}) + (SR >= {s_c})) >= 2 THEN 1 ELSE 0 END) as Successful FROM batting GROUP BY Player HAVING Successful > 0"
        else:
            w_c, av_c, e_c = c1.number_input("Min Wkts", 12), c2.number_input("Max Avg", 28.0), c3.number_input("Max Econ", 5.5)
            q = f"SELECT Player, COUNT(*) as Total, SUM(CASE WHEN ((Wkts >= {w_c}) + (Ave <= {av_c}) + (Econ <= {e_c})) >= 2 THEN 1 ELSE 0 END) as Successful FROM bowling GROUP BY Player HAVING Successful > 0"
        df_c = pd.read_sql(q, conn); df_c['Win %'] = (df_c['Successful'] * 100.0 / df_c['Total']).round(2)
        st.dataframe(df_c.sort_values("Win %", ascending=False), use_container_width=True, hide_index=True)
    else:
        disc_p = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True, key="dp_tab3")
        p_q = f"SELECT A.Player, A.Season, A.Runs, A.Ave, A.SR, (SELECT COUNT(*) FROM batting) as Total_Raw, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM batting B WHERE ((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM batting B WHERE B.Runs > A.Runs AND B.Ave > A.Ave AND B.SR > A.SR) as Clean_Loss FROM batting A" if disc_p == "Batting" else f"SELECT A.Player, A.Season, A.Wkts, A.Ave, A.Econ, (SELECT COUNT(*) FROM bowling) as Total_Raw, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END)) >= 2) as Win_C, (SELECT COUNT(*) FROM bowling B WHERE ((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END)) >= 2) as Loss_C, (SELECT COUNT(*) FROM bowling B WHERE B.Wkts > A.Wkts AND B.Ave < A.Ave AND B.Econ < A.Econ) as Clean_Loss FROM bowling A"
        df_p = pd.read_sql(p_q, conn); df_p['Total_Opp'] = df_p['Total_Raw'] - 1; df_p['Tie_C'] = (df_p['Total_Raw'] - df_p['Win_C'] - df_p['Loss_C']) - 1
        df_p['Wins %'] = df_p.apply(lambda r: fmt(r['Win_C'], r['Total_Opp']), axis=1); df_p['Losses'] = df_p.apply(lambda r: fmt(r['Loss_C'], r['Total_Opp']), axis=1); df_p['Ties'] = df_p.apply(lambda r: fmt(r['Tie_C'], r['Total_Opp']), axis=1)
        st.dataframe(df_p.sort_values("Win_C", ascending=False)[['Player', 'Season', 'Wins %', 'Losses', 'Ties', 'Clean_Loss']], use_container_width=True, hide_index=True)

elif st.session_state.nav_choice == "👤 Player Details":
    p_names = sorted(list(set(pd.read_sql("SELECT DISTINCT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT DISTINCT Player FROM bowling", conn)['Player'])))
    target_player = st.selectbox("Select Player", p_names)
    if target_player:
        for t, lab in [("batting", "Batting"), ("bowling", "Bowling")]:
            cols = "Runs, Ave, SR" if t == "batting" else "Wkts, Ave, Econ"
            q = f"SELECT A.Season, {cols}, (SELECT COUNT(*) FROM {t}) as TR, (SELECT COUNT(*) FROM {t} B WHERE {'((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))' if t=='batting' else '((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))'} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE {'((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))' if t=='batting' else '((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))'} >= 2) as LC, (SELECT COUNT(*) FROM {t} B WHERE {'B.Runs > A.Runs AND B.Ave > A.Ave AND B.SR > A.SR' if t=='batting' else 'B.Wkts > A.Wkts AND B.Ave < A.Ave AND B.Econ < A.Econ'}) as CL FROM {t} A WHERE A.Player = '{target_player}'"
            df = pd.read_sql(q, conn)
            if not df.empty:
                st.subheader(f"{lab} Career")
                df['Ties %'] = df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC']-1, r['TR']-1), axis=1)
                df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR']-1), axis=1)
                df['Losses %'] = df.apply(lambda r: fmt(r['LC'], r['TR']-1), axis=1)
                evt = st.dataframe(df.drop(columns=['TR','WC','LC']), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key=f"sel_{t}")
                if evt.selection.rows:
                    sel = df.iloc[evt.selection.rows[0]]
                    if t == "batting": 
                        st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = sel['Runs'], sel['Ave'], sel['SR']
                        st.session_state.nav_choice = "Batting Milestones"
                    else:
                        st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = sel['Wkts'], sel['Ave'], sel['Econ']
                        st.session_state.nav_choice = "Bowling Milestones"
                    st.rerun()

elif st.session_state.nav_choice == "🏟️ Squad Comparison":
    st.header("🏟️ Squad Comparison")
    with st.expander("🛠️ Squad Management"):
        c_m1, c_m2 = st.columns(2)
        if c_m1.button("🗑️ Clear"): st.session_state.squad_a, st.session_state.squad_b = [], []; st.rerun()
        c_m2.text_input("📋 Squad Code", value=json.dumps({"a": st.session_state.squad_a, "b": st.session_state.squad_b}))
        load = st.text_input("📥 Load Code:")
        if st.button("🔄 Load"):
            try: d = json.loads(load); st.session_state.squad_a, st.session_state.squad_b = d['a'], d['b']; st.rerun()
            except: st.error("Error")
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    c1, c2 = st.columns(2)
    with c1:
        new_a = st.selectbox("Add to A", [""]+all_p, key="a_add")
        if new_a and new_a not in st.session_state.squad_a: st.session_state.squad_a.append(new_a); st.rerun()
        st.session_state.squad_a = st.multiselect("Squad A", st.session_state.squad_a, default=st.session_state.squad_a)
    with c2:
        new_b = st.selectbox("Add to B", [""]+all_p, key="b_add")
        if new_b and new_b not in st.session_state.squad_b: st.session_state.squad_b.append(new_b); st.rerun()
        st.session_state.squad_b = st.multiselect("Squad B", st.session_state.squad_b, default=st.session_state.squad_b)
    if st.session_state.squad_a and st.session_state.squad_b:
        mode = st.radio("Direction:", ["A Benchmark", "B Benchmark"], horizontal=True)
        src, trg = (st.session_state.squad_a, st.session_state.squad_b) if "A" in mode else (st.session_state.squad_b, st.session_state.squad_a)
        p = st.selectbox("Benchmark Player:", src)
        if p:
            b_y, w_y = pd.read_sql(f"SELECT Season FROM batting WHERE Player='{p}'", conn)['Season'].tolist(), pd.read_sql(f"SELECT Season FROM bowling WHERE Player='{p}'", conn)['Season'].tolist()
            disc = st.radio("Type:", (["Batting"] if b_y else []) + (["Bowling"] if w_y else []), horizontal=True)
            y = st.selectbox("Year:", b_y if disc == "Batting" else w_y)
            if y:
                bench = pd.read_sql(f"SELECT * FROM {'batting' if disc == 'Batting' else 'bowling'} WHERE Player='{p}' AND Season='{y}'", conn).iloc[0]
                st.info(f"📍 Benchmark: {p} ({y})")
                if disc == "Batting":
                    tr, ta, ts = bench['Runs'], bench['Ave'], bench['SR']
                    q = f"SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta} THEN 1 ELSE 0 END + CASE WHEN SR > {ts} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta} THEN 1 ELSE 0 END + CASE WHEN SR = {ts} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta} THEN 1 ELSE 0 END + CASE WHEN SR < {ts} THEN 1 ELSE 0 END) as LossesA FROM batting WHERE Player IN ('" + "','".join(trg) + "') ORDER BY WinsA DESC"
                else:
                    tw, tav, te = bench['Wkts'], bench['Ave'], bench['Econ']
                    q = f"SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {tw} THEN 1 ELSE 0 END + CASE WHEN Ave < {tav} THEN 1 ELSE 0 END + CASE WHEN Econ < {te} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {tw} THEN 1 ELSE 0 END + CASE WHEN Ave = {tav} THEN 1 ELSE 0 END + CASE WHEN Econ = {te} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {tw} THEN 1 ELSE 0 END + CASE WHEN Ave > {tav} THEN 1 ELSE 0 END + CASE WHEN Econ > {te} THEN 1 ELSE 0 END) as LossesA FROM bowling WHERE Player IN ('" + "','".join(trg) + "') ORDER BY WinsA DESC"
                display_styled_results(pd.read_sql(q, conn), f"Squad vs {p}")

# --- NEW SECTION 6: FORMAT ANALYSIS ---
elif st.session_state.nav_choice == "🧬 Format Analysis":
    st.header("🧬 Format Analysis")
    st.write("Find combinations of players that are **Unbeatable Together**. A combination is unbeatable if no single year in the database can defeat all years of every player in that group.")
    
    disc_f = st.radio("Discipline:", ["Batting", "Bowling"], horizontal=True)
    k_val = st.number_input("Combination Size (K)", min_value=1, max_value=3, value=1)
    
    if st.button("🚀 Calculate Unbeatable Combinations"):
        with st.spinner("Analyzing all player-year interactions..."):
            # 1. Get Data
            table = disc_f.lower()
            df_all = pd.read_sql(f"SELECT * FROM {table}", conn)
            players = df_all['Player'].unique().tolist()
            
            # 2. Build Beat Matrix (Which Year beats which Player)
            # A year beats a player IF it beats ALL of that player's years.
            beat_matrix = {} # {year_id: set of players it defeats}
            
            for idx, row_x in df_all.iterrows():
                year_id = f"{row_x['Player']} {row_x['Season']}"
                beaten_players = set()
                
                for p in players:
                    p_years = df_all[df_all['Player'] == p]
                    defeated_count = 0
                    for _, row_p in p_years.iterrows():
                        if table == "batting":
                            wins = (int(row_x['Runs'] > row_p['Runs']) + int(row_x['Ave'] > row_p['Ave']) + int(row_x['SR'] > row_p['SR']))
                        else:
                            wins = (int(row_x['Wkts'] > row_p['Wkts']) + int(row_x['Ave'] < row_p['Ave']) + int(row_x['Econ'] < row_p['Econ']))
                        
                        if wins >= 2: defeated_count += 1
                    
                    # Year X beats Player P only if it beats ALL of P's seasons
                    if defeated_count == len(p_years):
                        beaten_players.add(p)
                
                beat_matrix[year_id] = beaten_players

            # 3. Find Combinations
            unbeatable_combos = []
            all_years = list(beat_matrix.keys())
            
            # To speed up, we only check players who are 'Hard to beat'
            # (i.e., those not beaten by almost everyone)
            for combo in combinations(players, k_val):
                is_beatable = False
                for year in all_years:
                    # If this year beats ALL players in the combo, the combo is beatable
                    if all(p in beat_matrix[year] for p in combo):
                        is_beatable = True
                        break
                
                if not is_beatable:
                    unbeatable_combos.append(list(combo))
            
            # 4. Display
            st.subheader(f"🏆 Results: Found {len(unbeatable_combos)} Unbeatable Sets")
            if unbeatable_combos:
                res_df = pd.DataFrame(unbeatable_combos, columns=[f"Player {i+1}" for i in range(k_val)])
                st.dataframe(res_df, use_container_width=True, hide_index=True)
            else:
                st.error("No combination of this size is unbeatable against the entire database.")

conn.close()
