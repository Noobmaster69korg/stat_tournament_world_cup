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

# --- 1: BATTING MILESTONES ---
if st.session_state.nav_choice == "Batting Milestones":
    st.header("Batting Filter")
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Set A")
        tr1a, ta1a, ts1a = st.number_input("Min Runs (A)", value=st.session_state.bat_runs_a), st.number_input("Min Avg (A)", value=st.session_state.bat_avg_a), st.number_input("Min SR (A)", value=st.session_state.bat_sr_a)
        st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a = tr1a, ta1a, ts1a
    with c2:
        st.subheader("Set B")
        tr1b, ta1b, ts1b = st.number_input("Min Runs (B)", 500), st.number_input("Min Avg (B)", 50.0), st.number_input("Min SR (B)", 100.0)
    q = f"WITH Base AS (SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1a} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1a} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr1a} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta1a} THEN 1 ELSE 0 END + CASE WHEN SR < {ts1a} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Runs > {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR > {ts1b} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Runs = {tr1b} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta1b} THEN 1 ELSE 0 END + CASE WHEN SR = {ts1b} THEN 1 ELSE 0 END) as TiesB FROM batting) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''} ORDER BY WinsA DESC, Runs DESC"
    display_styled_results(pd.read_sql(q, conn), "Batting")

# --- 2: BOWLING MILESTONES ---
elif st.session_state.nav_choice == "Bowling Milestones":
    st.header("Bowling Filter")
    f_mode = st.radio("Display Mode:", ["Meet Set A Only", "Meet BOTH Set A and Set B"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Set A")
        twa, taa, tea = st.number_input("Min Wickets (A)", value=st.session_state.bowl_w_a), st.number_input("Max Avg (A)", value=st.session_state.bowl_a_a), st.number_input("Max Econ (A)", value=st.session_state.bowl_e_a)
        st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a = twa, taa, tea
    with c2:
        st.subheader("Set B")
        twb, tab, teb = st.number_input("Min Wkts (B)", 20), st.number_input("Max Avg (B)", 20.0), st.number_input("Max Econ (B)", 4.5)
    q = f"WITH Base AS (SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {twa} THEN 1 ELSE 0 END + CASE WHEN Ave < {taa} THEN 1 ELSE 0 END + CASE WHEN Econ < {tea} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {twa} THEN 1 ELSE 0 END + CASE WHEN Ave = {taa} THEN 1 ELSE 0 END + CASE WHEN Econ = {tea} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {twa} THEN 1 ELSE 0 END + CASE WHEN Ave > {taa} THEN 1 ELSE 0 END + CASE WHEN Econ > {tea} THEN 1 ELSE 0 END) as LossesA, (CASE WHEN Wkts > {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as WinsB, (CASE WHEN Wkts = {twb} THEN 1 ELSE 0 END + CASE WHEN Ave < {tab} THEN 1 ELSE 0 END + CASE WHEN Econ < {teb} THEN 1 ELSE 0 END) as TiesB FROM bowling) SELECT * FROM Base WHERE (WinsA + TiesA) >= 2 {'AND (WinsB + TiesB) >= 2' if 'BOTH' in f_mode else ''} ORDER BY WinsA DESC, Wickets DESC"
    display_styled_results(pd.read_sql(q, conn), "Bowling")

# --- 3: PLAYER ANALYTICS ---
elif st.session_state.nav_choice == "📈 Player Analytics":
    st.header("📈 Advanced Analytics")
    choice = st.radio("Type:", ["Career Consistency", "Global Rankings"], horizontal=True)
    if "Consistency" in choice:
        disc = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True, key="dc_t3")
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
                st.subheader(f"{lab} Career")
                df['Wins %'] = df.apply(lambda r: fmt(r['WC'], r['TR']-1), axis=1); df['Losses %'] = df.apply(lambda r: fmt(r['LC'], r['TR']-1), axis=1); df['Ties %'] = df.apply(lambda r: fmt(r['TR']-r['WC']-r['LC']-1, r['TR']-1), axis=1)
                evt = st.dataframe(df.drop(columns=['TR','WC','LC']), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key=f"d_{t}")
                if evt.selection.rows:
                    sel = df.iloc[evt.selection.rows[0]]
                    if t == "batting": st.session_state.bat_runs_a, st.session_state.bat_avg_a, st.session_state.bat_sr_a, st.session_state.nav_choice = sel['Runs'], sel['Ave'], sel['SR'], "Batting Milestones"
                    else: st.session_state.bowl_w_a, st.session_state.bowl_a_a, st.session_state.bowl_e_a, st.session_state.nav_choice = sel['Wkts'], sel['Ave'], sel['Econ'], "Bowling Milestones"
                    st.rerun()

# --- 5: SQUAD COMPARISON ---
elif st.session_state.nav_choice == "🏟️ Squad Comparison":
    st.header("🏟️ Squad Comparison")
    with st.expander("🛠️ Squad Management"):
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Clear Squads"): st.session_state.squad_a, st.session_state.squad_b = [], []; st.rerun()
        c2.text_input("📋 Code", value=json.dumps({"a": st.session_state.squad_a, "b": st.session_state.squad_b}))
        load = st.text_input("📥 Load Code:")
        if st.button("🔄 Go"):
            try: d = json.loads(load); st.session_state.squad_a, st.session_state.squad_b = d['a'], d['b']; st.rerun()
            except: st.error("ERR")
    
    all_p = sorted(list(set(pd.read_sql("SELECT Player FROM batting", conn)['Player']) | set(pd.read_sql("SELECT Player FROM bowling", conn)['Player'])))
    c1, c2 = st.columns(2)
    with c1:
        n = st.selectbox("Add Player to Squad A", [""]+all_p, key="sq_a_add")
        if n and n not in st.session_state.squad_a: st.session_state.squad_a.append(n); st.rerun()
        st.session_state.squad_a = st.multiselect("Manage Squad A", st.session_state.squad_a, default=st.session_state.squad_a)
    with c2:
        n = st.selectbox("Add Player to Squad B", [""]+all_p, key="sq_b_add")
        if n and n not in st.session_state.squad_b: st.session_state.squad_b.append(n); st.rerun()
        st.session_state.squad_b = st.multiselect("Manage Squad B", st.session_state.squad_b, default=st.session_state.squad_b)

    if st.session_state.squad_a and st.session_state.squad_b:
        sub_tab = st.radio("Choose Mode:", ["🎯 Individual Year Comparison", "📊 Squad Pairwise Standings"], horizontal=True)
        
        if sub_tab == "🎯 Individual Year Comparison":
            mode = st.radio("Benchmark Direction:", ["Squad A ➡️ Squad B", "Squad B ➡️ Squad A"], horizontal=True)
            src, trg = (st.session_state.squad_a, st.session_state.squad_b) if "A ➡️" in mode else (st.session_state.squad_b, st.session_state.squad_a)
            
            p = st.selectbox("Pick Player:", src, key=f"bench_p_{mode}")
            if p:
                b_y, w_y = pd.read_sql(f"SELECT Season FROM batting WHERE Player='{p}'", conn)['Season'].tolist(), pd.read_sql(f"SELECT Season FROM bowling WHERE Player='{p}'", conn)['Season'].tolist()
                disc = st.radio("Type:", (["Batting"] if b_y else []) + (["Bowling"] if w_y else []), horizontal=True)
                y = st.selectbox("Year:", b_y if disc == "Batting" else w_y)
                
                if y:
                    bench = pd.read_sql(f"SELECT * FROM {'batting' if disc == 'Batting' else 'bowling'} WHERE Player='{p}' AND Season='{y}'", conn).iloc[0]
                    # RE-ADDED: DISPLAY STATS
                    st.info(f"📍 **Benchmark Stats:** {p} ({y})")
                    met1, met2, met3 = st.columns(3)
                    if disc == "Batting":
                        tr, ta, ts = bench['Runs'], bench['Ave'], bench['SR']
                        met1.metric("Runs", tr); met2.metric("Average", ta); met3.metric("Strike Rate", ts)
                        q = f"SELECT Player, Season as Year, Runs, Ave as Average, SR as Strike_Rate, (CASE WHEN Runs > {tr} THEN 1 ELSE 0 END + CASE WHEN Ave > {ta} THEN 1 ELSE 0 END + CASE WHEN SR > {ts} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Runs = {tr} THEN 1 ELSE 0 END + CASE WHEN Ave = {ta} THEN 1 ELSE 0 END + CASE WHEN SR = {ts} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Runs < {tr} THEN 1 ELSE 0 END + CASE WHEN Ave < {ta} THEN 1 ELSE 0 END + CASE WHEN SR < {ts} THEN 1 ELSE 0 END) as LossesA FROM batting WHERE Player IN ('" + "','".join(trg) + "') ORDER BY WinsA DESC"
                    else:
                        tw, tav, te = bench['Wkts'], bench['Ave'], bench['Econ']
                        met1.metric("Wickets", tw); met2.metric("Average", tav); met3.metric("Economy", te)
                        q = f"SELECT Player, Season as Year, Wkts as Wickets, Ave as Average, Econ as Economy, (CASE WHEN Wkts > {tw} THEN 1 ELSE 0 END + CASE WHEN Ave < {tav} THEN 1 ELSE 0 END + CASE WHEN Econ < {te} THEN 1 ELSE 0 END) as WinsA, (CASE WHEN Wkts = {tw} THEN 1 ELSE 0 END + CASE WHEN Ave = {tav} THEN 1 ELSE 0 END + CASE WHEN Econ = {te} THEN 1 ELSE 0 END) as TiesA, (CASE WHEN Wkts < {tw} THEN 1 ELSE 0 END + CASE WHEN Ave > {tav} THEN 1 ELSE 0 END + CASE WHEN Econ > {te} THEN 1 ELSE 0 END) as LossesA FROM bowling WHERE Player IN ('" + "','".join(trg) + "') ORDER BY WinsA DESC"
                    display_styled_results(pd.read_sql(q, conn), f"Against {p}")
        
        else:
            # NEW: SQUAD PAIRWISE STANDINGS
            disc = st.radio("Choose Discipline to Rank:", ["Batting", "Bowling"], horizontal=True)
            t = disc.lower()
            a_list = "('" + "','".join(st.session_state.squad_a) + "')"
            b_list = "('" + "','".join(st.session_state.squad_b) + "')"
            
            win = "((CASE WHEN A.Runs > B.Runs THEN 1 ELSE 0 END) + (CASE WHEN A.Ave > B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.SR > B.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN A.Wkts > B.Wkts THEN 1 ELSE 0 END) + (CASE WHEN A.Ave < B.Ave THEN 1 ELSE 0 END) + (CASE WHEN A.Econ < B.Econ THEN 1 ELSE 0 END))"
            loss = "((CASE WHEN B.Runs > A.Runs THEN 1 ELSE 0 END) + (CASE WHEN B.Ave > A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.SR > A.SR THEN 1 ELSE 0 END))" if t == "batting" else "((CASE WHEN B.Wkts > A.Wkts THEN 1 ELSE 0 END) + (CASE WHEN B.Ave < A.Ave THEN 1 ELSE 0 END) + (CASE WHEN B.Econ < A.Econ THEN 1 ELSE 0 END))"

            st.subheader(f"🏆 {disc} Head-to-Head: Squad A vs Squad B")
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("### Squad A Performance")
                q_a = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {b_list}) as TR, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {b_list} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {b_list} AND {loss} >= 2) as LC FROM {t} A WHERE A.Player IN {a_list}"
                df_a = pd.read_sql(q_a, conn)
                if not df_a.empty:
                    df_a['Wins vs B %'] = df_a.apply(lambda r: fmt(r['WC'], r['TR']), axis=1)
                    st.dataframe(df_a.sort_values("WC", ascending=False)[['Player', 'Season', 'Wins vs B %']], use_container_width=True, hide_index=True)
            
            with col_b:
                st.markdown("### Squad B Performance")
                q_b = f"SELECT A.Player, A.Season, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {a_list}) as TR, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {a_list} AND {win} >= 2) as WC, (SELECT COUNT(*) FROM {t} B WHERE B.Player IN {a_list} AND {loss} >= 2) as LC FROM {t} A WHERE A.Player IN {b_list}"
                df_b = pd.read_sql(q_b, conn)
                if not df_b.empty:
                    df_b['Wins vs A %'] = df_b.apply(lambda r: fmt(r['WC'], r['TR']), axis=1)
                    st.dataframe(df_b.sort_values("WC", ascending=False)[['Player', 'Season', 'Wins vs A %']], use_container_width=True, hide_index=True)
    else:
        st.info("Add players to both squads to begin.")

# --- 6: FORMAT ANALYSIS ---
elif st.session_state.nav_choice == "🧬 Format Analysis":
    st.header("🧬 Format Analysis: Unbeatable Combinations")
    df_f, k_val = st.radio("Disc:", ["Batting", "Bowling"], horizontal=True, key="disc_fa"), st.radio("Size (K):", [1, 2, 3], horizontal=True, key="k_fa")
    if st.button("🚀 Find"):
        with st.spinner("Analyzing..."):
            tbl = df_f.lower(); df = pd.read_sql(f"SELECT * FROM {tbl}", conn); pl = df['Player'].unique().tolist()
            kill_sets = []
            for _, rx in df.iterrows():
                beat = set()
                for p in pl:
                    py = df[df['Player']==p]; beaten = 0
                    for _, rp in py.iterrows():
                        if tbl=="batting": w = int(rx['Runs']>rp['Runs'])+int(rx['Ave']>rp['Ave'])+int(rx['SR']>rp['SR'])
                        else: w = int(rx['Wkts']>rp['Wkts'])+int(rx['Ave']<rp['Ave'])+int(rx['Econ']<rp['Econ'])
                        if w >= 2: beaten += 1
                    if beaten == len(py): beat.add(p)
                kill_sets.append(beat)
            unb = []
            for c in combinations(pl, k_val):
                cs = set(c); possible = True
                for ks in kill_sets:
                    if cs.issubset(ks): possible = False; break
                if possible: unb.append(list(c))
            st.subheader(f"Found {len(unb)} sets")
            if unb: st.dataframe(pd.DataFrame(unb, columns=[f"P{i+1}" for i in range(k_val)]), hide_index=True)

conn.close()
