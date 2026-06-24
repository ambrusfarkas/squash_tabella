import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Squash Leaderboard & ELO Tracker", layout="wide", page_icon="🎾")

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

try:
    df_database = conn.read(spreadsheet=SHEET_URL, worksheet="Matches", usecols=[0, 1, 2, 3], ttl=0) 
    df_database = df_database.dropna(how="all")
    st.session_state.matches = df_database.to_dict('records')
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Error: {e}")
    if 'matches' not in st.session_state:
        st.session_state.matches = []

def calculate_stats(matches):
    elo = {p: 1200 for p in players_list}
    stats = {p: {"Played": 0, "Won": 0, "Pts_Scored": 0, "Pts_Conceded": 0} for p in players_list}
    K = 32
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
    rows = []
    for p in players_list:
        s = stats[p]
        if s["Played"] == 0: continue
        row_data = {"Rank": 0, "Player": p, "🔮 ELO Rating": elo[p], "Played": s["Played"], "Won": s["Won"], "Winrate": f"{(s['Won'] / s['Played'] * 100):.0f}%", "Total Points": s['Pts_Scored'], "Avg Points": f"{(s['Pts_Scored'] / s['Played']):.1f}", "Avg Diff": f"{((s['Pts_Scored'] - s['Pts_Conceded']) / s['Played']):.1f}"}
        rows.append(row_data)
    df = pd.DataFrame(rows).sort_values(by="🔮 ELO Rating", ascending=False).reset_index(drop=True)
    df["Rank"] = df.index + 1
    return df, elo

df_leaderboard, current_elos = calculate_stats(st.session_state.matches)

st.sidebar.title("🏸 Squash Dashboard")
view = st.sidebar.radio("Navigation", ["🏆 Leaderboard", "📝 Record Match", "⚔️ 1v1 Head-to-Head"])

if view == "🏆 Leaderboard":
    st.title("🏆 Leaderboard")
    if not st.session_state.matches: st.warning("No matches recorded.")
    else:
        st.table(df_leaderboard.style.hide(axis="index"))
        st.subheader("🕒 Recent Matches (Edit to Update)")
        
        # Prepare Dataframe for Editing
        recent_df = pd.DataFrame(st.session_state.matches[-10:]).iloc[::-1]
        recent_df = recent_df.rename(columns={"Winner_Score": "Winner Score", "Loser_Score": "Loser Score"})
        
        edited_df = st.data_editor(recent_df, hide_index=True, use_container_width=True)
        
        if st.button("Save Changes to Recent Matches"):
            # Rename back to original keys
            final_recent = edited_df.rename(columns={"Winner Score": "Winner_Score", "Loser Score": "Loser_Score"})
            # Merge back into full list
            all_matches = pd.DataFrame(st.session_state.matches)
            all_matches.iloc[-10:] = final_recent.iloc[::-1] # Ensure order is maintained
            
            conn.update(spreadsheet=SHEET_URL, worksheet="Matches", data=all_matches)
            st.cache_data.clear()
            st.success("Matches updated successfully!")
            st.rerun()

elif view == "📝 Record Match":
    st.title("📝 Enter Match Result")
    c1, c2 = st.columns(2)
    with c1:
        winner = st.selectbox("Winner", players_list, index=None, placeholder="Select...")
        w_score = st.number_input("Winner Points", min_value=0, value=11, step=1)
    with c2:
        loser_options = [p for p in players_list if p != winner] if winner else players_list
        loser = st.selectbox("Loser", loser_options, index=None, placeholder="Select...")
        default_loser_points = 8
        if winner and loser:
            relevant = [m for m in st.session_state.matches if m.get("Winner") == winner and m.get("Loser") == loser]
            if relevant: default_loser_points = int(round(sum(int(m.get("Loser_Score", 0)) for m in relevant) / len(relevant)))
        l_score = st.number_input("Loser Points", min_value=0, value=default_loser_points, step=1)
    
    if st.button("Save Match ☁️"):
        if not winner or not loser: st.error("Select both players.")
        elif w_score <= l_score: st.error("Winner must have more points.")
        else:
            st.session_state.matches.append({"Winner": winner, "Winner_Score": int(w_score), "Loser_Score": int(l_score), "Loser": loser})
            conn.update(spreadsheet=SHEET_URL, worksheet="Matches", data=pd.DataFrame(st.session_state.matches))
            st.cache_data.clear(); st.rerun()

elif view == "⚔️ 1v1 Head-to-Head":
    st.title("⚔️ Rivalry Statistics")
    active = df_leaderboard["Player"].tolist()
    if len(active) < 2: st.info("Not enough data.")
    else:
        p1, p2 = st.selectbox("Player One:", active), st.selectbox("Player Two:", [p for p in active if p != p1])
        h2h = [m for m in st.session_state.matches if (m.get("Winner") == p1 and m.get("Loser") == p2) or (m.get("Winner") == p2 and m.get("Loser") == p1)]
        if h2h:
            st.markdown("### 📊 Lifetime History")
            st.table(pd.DataFrame(h2h).rename(columns={"Winner_Score": "Winner Score", "Loser_Score": "Loser Score"}).style.hide(axis="index"))
        else: st.info("No matches recorded between them.")
