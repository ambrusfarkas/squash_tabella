import streamlit as st
import pandas as pd
import altair as alt
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Squash Tabella", layout="wide", page_icon="🎾")

# --- CSS INJECTION TO FORCE CENTER ALIGNMENT ---
st.markdown("""
    <style>
    [data-testid="stTable"] th, [data-testid="stTable"] td { text-align: center !important; }
    [data-testid="stDataEditor"] { text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

players_list = ["Ambrus", "Andris", "Dávid", "Donát", "Marci", "Matyi", "Ricsi", "Zoli"]
SHEET_URL = "https://docs.google.com/spreadsheets/d/1O1A0kF4rxf-oxoyTYCyeMFGXCCMi-GpURSjH7U8_ACY/edit"
conn = st.connection("gsheets", type=GSheetsConnection)

# Initialize Session States
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

try:
    df_database = conn.read(spreadsheet=SHEET_URL, worksheet="Matches", usecols=[0, 1, 2, 3], ttl=0) 
    df_database = df_database.dropna(how="all")
    st.session_state.matches = df_database.to_dict('records')
except Exception as e:
    st.error(f"Could not connect to Google Sheets: {e}")
    if 'matches' not in st.session_state: st.session_state.matches = []

def calculate_stats(matches):
    elo = {p: 1200 for p in players_list}
    stats = {p: {"Played": 0, "Won": 0, "Pts_Scored": 0, "Pts_Conceded": 0} for p in players_list}
    K = 32
    
    # Initialize history to track the Elo timeline
    elo_history = [{"Match": 0, **elo}]
    match_count = 0
    
    for m in matches:
        w, l = str(m.get("Winner", "")).strip(), str(m.get("Loser", "")).strip()
        if w == 'nan' or l == 'nan' or not w or not l: continue
        try:
            w_pts, l_pts = int(m.get("Winner_Score", 0)), int(m.get("Loser_Score", 0))
        except ValueError: continue
        
        if w in stats:
            stats[w]["Played"] += 1; stats[w]["Won"] += 1
            stats[w]["Pts_Scored"] += w_pts; stats[w]["Pts_Conceded"] += l_pts
        if l in stats:
            stats[l]["Played"] += 1
            stats[l]["Pts_Scored"] += l_pts; stats[l]["Pts_Conceded"] += w_pts
            
        r_w, r_l = elo.get(w, 1200), elo.get(l, 1200)
        expected_w = 1 / (1 + 10 ** ((r_l - r_w) / 400))
        elo[w] = round(r_w + (K * (1 - expected_w)))
        elo[l] = round(r_l - (K * (1 - expected_w)))
        
        # Save a snapshot of the Elos after this match
        match_count += 1
        elo_history.append({"Match": match_count, **elo})
        
    rows = []
    for p in players_list:
        s = stats[p]
        if s["Played"] == 0: continue
        rows.append({"Rank": 0, "Player": p, "🔮 ELO Rating": elo[p], "Played": s["Played"], "Won": s["Won"], "Winrate": f"{(s['Won'] / s['Played'] * 100):.0f}%", "Total Points": s['Pts_Scored'], "Avg Points": f"{(s['Pts_Scored'] / s['Played']):.1f}", "Avg Diff": f"{((s['Pts_Scored'] - s['Pts_Conceded']) / s['Played']):.1f}"})
    
    df = pd.DataFrame(rows).sort_values(by="🔮 ELO Rating", ascending=False).reset_index(drop=True)
    df["Rank"] = df.index + 1
    
    return df, elo, elo_history

# Unpack the new elo_history
df_leaderboard, current_elos, elo_history = calculate_stats(st.session_state.matches)

st.sidebar.title("🏸 Squash Dashboard")
view = st.sidebar.radio("Navigation", ["🏆 Leaderboard", "📝 Record Match", "⚔️ 1v1 Head-to-Head"])

if view == "🏆 Leaderboard":
    st.title("🏆 Leaderboard")
    st.table(df_leaderboard.style.hide(axis="index"))
    
    st.subheader("🕒 Recent Matches")
    recent_df = pd.DataFrame(st.session_state.matches[-10:])
    recent_df["Winner_Score"] = recent_df["Winner_Score"].astype(int)
    recent_df["Loser_Score"] = recent_df["Loser_Score"].astype(int)

    if not st.session_state.edit_mode:
        st.table(recent_df.rename(columns={"Winner_Score": "Winner Score", "Loser_Score": "Loser Score"}).iloc[::-1])
        if st.button("Edit Matches"):
            st.session_state.edit_mode = True
            st.rerun()
    else:
        # Data Editor with Dropdowns
        edited_df = st.data_editor(
            recent_df.iloc[::-1], 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Winner": st.column_config.SelectboxColumn(options=players_list),
                "Loser": st.column_config.SelectboxColumn(options=players_list),
                "Winner_Score": st.column_config.NumberColumn(min_value=0),
                "Loser_Score": st.column_config.NumberColumn(min_value=0)
            }
        )
        if st.button("Save Changes & Sync"):
            all_matches_df = pd.DataFrame(st.session_state.matches)
            all_matches_df.iloc[-10:] = edited_df.iloc[::-1]
            conn.update(spreadsheet=SHEET_URL, worksheet="Matches", data=all_matches_df)
            st.session_state.edit_mode = False
            st.cache_data.clear()
            st.rerun()
            
    # --- NEW TALL ELO HISTORY CHART ---
    st.divider()
    st.subheader("📈 Elo Rating History")
    if len(elo_history) > 1:
        history_df = pd.DataFrame(elo_history)
        active_players = df_leaderboard["Player"].tolist()
        
        if active_players:
            # Reformat the data structure to work with Altair Charting
            melted_df = history_df.melt(id_vars="Match", value_vars=active_players, var_name="Player", value_name="Elo")
            
            # Build an explicit interactive chart
            chart = alt.Chart(melted_df).mark_line(size=3).encode(
                x=alt.X("Match:Q", title="Matches Played (Timeline)"),
                # Force the Y-axis to start at exactly 0
                y=alt.Y("Elo:Q", scale=alt.Scale(zero=True), title="Elo Rating"),
                color=alt.Color("Player:N", title="Player"),
                tooltip=["Match", "Player", "Elo"]
            ).properties(
                height=700 # Made the chart extremely tall!
            ).interactive()
            
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Play some matches to see your Elo history chart!")

elif view == "📝 Record Match":
    st.title("📝 Enter Match Result")
    c1, c2 = st.columns(2)
    with c1:
        winner = st.selectbox("Winner", players_list, index=None, placeholder="Select...")
        w_score = st.number_input("Winner Points", min_value=0, value=11, step=1)
    with c2:
        loser_options = [p for p in players_list if p != winner] if winner else players_list
        loser = st.selectbox("Loser", loser_options, index=None, placeholder="Select...")
        l_score = st.number_input("Loser Points", min_value=0, value=8, step=1)
    
    if st.button("Save Match"):
        if not winner or not loser: st.error("Select both players.")
        elif w_score <= l_score: st.error("Winner points must be > Loser points.")
        else:
            st.session_state.matches.append({"Winner": winner, "Winner_Score": int(w_score), "Loser_Score": int(l_score), "Loser": loser})
            conn.update(spreadsheet=SHEET_URL, worksheet="Matches", data=pd.DataFrame(st.session_state.matches))
            st.cache_data.clear(); st.rerun()

elif view == "⚔️ 1v1 Head-to-Head":
    st.title("⚔️ Rivalry Statistics")
    active = df_leaderboard["Player"].tolist()
    if len(active) < 2: st.info("Not enough data.")
    else:
        p1 = st.selectbox("Player One:", active)
        p2 = st.selectbox("Player Two:", [p for p in active if p != p1])
        
        h2h = [m for m in st.session_state.matches if (m.get("Winner") == p1 and m.get("Loser") == p2) or (m.get("Winner") == p2 and m.get("Loser") == p1)]
        if h2h:
            elo_p1, elo_p2 = current_elos.get(p1, 1200), current_elos.get(p2, 1200)
            total_games = len(h2h)
            
            K = 32
            exp_p1_win = 1 / (1 + 10 ** ((elo_p2 - elo_p1) / 400))
            pts_if_p1_wins = round(K * (1 - exp_p1_win))
            exp_p2_win = 1 / (1 + 10 ** ((elo_p1 - elo_p2) / 400))
            pts_if_p2_wins = round(K * (1 - exp_p2_win))

            st.subheader(f"Current Matchup: {p1} vs {p2}")
            st.markdown("### 🔮 Match Stakes")
            col_elo1, col_elo2 = st.columns(2)
            col_elo1.metric(f"{p1} Current Elo", elo_p1)
            col_elo2.metric(f"{p2} Current Elo", elo_p2)
            st.info(f"**If {p1} wins:** {p1} gains +{pts_if_p1_wins} Elo, {p2} drops -{pts_if_p1_wins} Elo. \n\n"
                    f"**If {p2} wins:** {p2} gains +{pts_if_p2_wins} Elo, {p1} drops -{pts_if_p2_wins} Elo.")
            
            st.divider()
            
            p1_wins = sum(1 for m in h2h if m.get("Winner") == p1)
            p2_wins = sum(1 for m in h2h if m.get("Winner") == p2)
            
            p1_pts = sum(int(m.get("Winner_Score", 0)) if m.get("Winner") == p1 else int(m.get("Loser_Score", 0)) for m in h2h)
            p2_pts = sum(int(m.get("Winner_Score", 0)) if m.get("Winner") == p2 else int(m.get("Loser_Score", 0)) for m in h2h)
            
            p1_wr = f"{(p1_wins / total_games * 100):.0f}%"
            p2_wr = f"{(p2_wins / total_games * 100):.0f}%"
            
            p1_avg_pts, p2_avg_pts = p1_pts / total_games, p2_pts / total_games
            
            blowout_match = max(h2h, key=lambda m: abs(int(m.get('Winner_Score', 0)) - int(m.get('Loser_Score', 0))))
            blowout_margin = int(blowout_match.get('Winner_Score', 0)) - int(blowout_match.get('Loser_Score', 0))
            blowout_winner = blowout_match.get('Winner')
            
            close_games = [m for m in h2h if abs(int(m.get('Winner_Score', 0)) - int(m.get('Loser_Score', 0))) <= 2]
            p1_close_wins = sum(1 for m in close_games if m.get('Winner') == p1)
            p2_close_wins = sum(1 for m in close_games if m.get('Winner') == p2)
            
            st.markdown("### 📊 Lifetime History")
            col_stat1, col_stat2 = st.columns(2)
            col_stat1.markdown(f"#### {p1} Stats"); col_stat1.metric("Total Wins", p1_wins); col_stat1.metric("Winrate", p1_wr); col_stat1.metric("Avg Points Scored", f"{p1_avg_pts:.1f}")
            col_stat2.markdown(f"#### {p2} Stats"); col_stat2.metric("Total Wins", p2_wins); col_stat2.metric("Winrate", p2_wr); col_stat2.metric("Avg Points Scored", f"{p2_avg_pts:.1f}")
            
            st.divider()
            st.markdown("### 🌶️ Insightful Data")
            c1, c2 = st.columns(2)
            c1.info(f"**Biggest Blowout:** \n\n{blowout_winner} crushed by **{blowout_margin} points** ({int(blowout_match.get('Winner_Score'))} - {int(blowout_match.get('Loser_Score'))}).")
            if close_games:
                c2.warning(f"**Nail-biters (1-2 point diff):** \n\nOut of {len(close_games)} close games, {p1} won **{p1_close_wins}**, and {p2} won **{p2_close_wins}**.")
            else:
                c2.warning("**Nail-biters:** \n\nNone yet!")

            st.write("### Game History Breakdown")
            df_h2h = pd.DataFrame(h2h).rename(columns={"Winner_Score": "Winner Score", "Loser_Score": "Loser Score"})
            df_h2h["Winner Score"] = df_h2h["Winner Score"].astype(int)
            df_h2h["Loser Score"] = df_h2h["Loser Score"].astype(int)
            st.table(df_h2h.style.hide(axis="index"))
        else: st.info("No matches recorded between them.")
