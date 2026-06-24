import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Squash Leaderboard & ELO Tracker", layout="wide", page_icon="🎾")

# --- CSS INJECTION TO FORCE CENTER ALIGNMENT ---
st.markdown("""
    <style>
    [data-testid="stTable"] th { text-align: center !important; }
    [data-testid="stTable"] td { text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)
# -----------------------------------------------

players_list = ["Ambrus", "Andris", "Dávid", "Donát", "Marci", "Matyi", "Ricsi", "Zoli"]

# --- GOOGLE SHEETS DATABASE CONNECTION ---
# This creates the connection using the secret credentials you provided
conn = st.connection("gsheets", type=GSheetsConnection)

# Read the data from the Google Sheet (cache expires every 5 seconds to stay live)
try:
    df_database = conn.read(worksheet="Matches", usecols=[0, 1, 2, 3], ttl=5)
    # Drop any completely empty rows
    df_database = df_database.dropna(how="all")
    # Convert it to the dictionary format the rest of our app expects
    st.session_state.matches = df_database.to_dict('records')
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Make sure the sheet name is 'Matches'. Error: {e}")
    if 'matches' not in st.session_state:
        st.session_state.matches = []
# -----------------------------------------

def calculate_stats(matches):
    elo = {p: 1200 for p in players_list}
    stats = {p: {"Played": 0, "Won": 0, "Pts_Scored": 0, "Pts_Conceded": 0} for p in players_list}
    K = 32
    
    for m in matches:
        w = str(m["Winner"]).strip()
        l = str(m["Loser"]).strip()
        
        # Handle cases where empty rows sneak in
        if w == 'nan' or l == 'nan' or not w or not l:
            continue
            
        w_pts = int(m["Winner_Score"])
        l_pts = int(m["Loser_Score"])
        
        if w in stats:
            stats[w]["Played"] += 1; stats[w]["Won"] += 1
            stats[w]["Pts_Scored"] += w_pts; stats[w]["Pts_Conceded"] += l_pts
        if l in stats:
            stats[l]["Played"] += 1
            stats[l]["Pts_Scored"] += l_pts; stats[l]["Pts_Conceded"] += w_pts
            
        r_w, r_l = elo.get(w, 1200), elo.get(l, 1200)
        expected_w = 1 / (1 + 10 ** ((r_l - r_w) / 400))
        points_exchanged = K * (1 - expected_w)
        
        elo[w] = round(r_w + points_exchanged)
        elo[l] = round(r_l - points_exchanged)

    rows = []
    for p in players_list:
        s = stats[p]
        if s["Played"] == 0:
            continue
            
        wr = f"{(s['Won'] / s['Played'] * 100):.0f}%"
        avg_pt = f"{(s['Pts_Scored'] / s['Played']):.2f}"
        avg_diff = f"{((s['Pts_Scored'] - s['Pts_Conceded']) / s['Played']):.2f}"
        
        rows.append({
            "Rank": 0, "Player": p, "🔮 ELO Rating": elo[p],
            "Played": s["Played"], "Won": s["Won"], "Winrate": wr,
            "Total Points": s["Pts_Scored"], "Avg Points": avg_pt, "Avg Diff": avg_diff
        })
        
    if rows:
        df = pd.DataFrame(rows).sort_values(by="🔮 ELO Rating", ascending=False).reset_index(drop=True)
        df["Rank"] = df.index + 1
    else:
        df = pd.DataFrame(columns=["Rank", "Player", "🔮 ELO Rating", "Played", "Won", "Winrate", "Total Points", "Avg Points", "Avg Diff"])
        
    return df, elo

df_leaderboard, current_elos = calculate_stats(st.session_state.matches)

st.sidebar.title("🏸 Squash Dashboard")
# Note: I removed the Data Management tab, because Google Sheets is your management now!
view = st.sidebar.radio("Navigation", ["🏆 Leaderboard", "📝 Record Match", "⚔️ 1v1 Head-to-Head"])

if view == "🏆 Leaderboard":
    st.title("🏆 Club Standings & Rankings")
    if not st.session_state.matches:
        st.warning("No matches recorded yet. Play a game!")
    else:
        st.table(df_leaderboard.set_index("Rank"))

elif view == "📝 Record Match":
    st.title("📝 Enter Match Result")
    
    with st.form("match_submission", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            winner = st.selectbox("Winner", players_list, index=None, placeholder="Select the winner...")
            w_score = st.number_input("Winner Points", min_value=0, value=11, step=1)
        with c2:
            loser_options = [p for p in players_list if p != winner] if winner else players_list
            loser = st.selectbox("Loser", loser_options, index=None, placeholder="Select the loser...")
            
            default_loser_points = 8
            if winner and loser:
                relevant_matches = [m for m in st.session_state.matches if m["Winner"] == winner and m["Loser"] == loser]
                if relevant_matches:
                    avg_loser_score = sum(int(m["Loser_Score"]) for m in relevant_matches) / len(relevant_matches)
                    default_loser_points = int(round(avg_loser_score))
                    
            l_score = st.number_input("Loser Points", min_value=0, value=default_loser_points, step=1)
            
            if winner and loser and default_loser_points != 8:
                st.caption(f"*(Auto-filled with {loser}'s avg score against {winner})*")
                
        st.write("")
        submitted = st.form_submit_button("Save Match to Cloud Database ☁️")
        
        if submitted:
            if not winner or not loser:
                st.error("Please select both a winner and a loser.")
            elif w_score <= l_score:
                st.error("Error: Winner points must be strictly greater than loser points.")
            else:
                # Add to local state
                new_match = {"Winner": winner, "Winner_Score": w_score, "Loser_Score": l_score, "Loser": loser}
                st.session_state.matches.append(new_match)
                
                # Push the entirely new state to Google Sheets
                updated_df = pd.DataFrame(st.session_state.matches)
                conn.update(worksheet="Matches", data=updated_df)
                
                # Clear the cache so it pulls the fresh data immediately
                st.cache_data.clear()
                st.success(f"Match Saved to Google Sheets! {winner} beat {loser} ({w_score}-{l_score})")
                st.rerun()

elif view == "⚔️ 1v1 Head-to-Head":
    st.title("⚔️ Rivalry Statistics")
    p1 = st.selectbox("Select Player One:", players_list)
    p2 = st.selectbox("Select Player Two:", [p for p in players_list if p != p1])
    
    elo_p1, elo_p2 = current_elos.get(p1, 1200), current_elos.get(p2, 1200)
    h2h_matches = [m for m in st.session_state.matches if (m["Winner"] == p1 and m["Loser"] == p2) or (m["Winner"] == p2 and m["Loser"] == p1)]
    total_games = len(h2h_matches)
    
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
    
    if total_games > 0:
        p1_wins = sum(1 for m in h2h_matches if m["Winner"] == p1)
        p2_wins = sum(1 for m in h2h_matches if m["Winner"] == p2)
        
        p1_pts = sum(int(m["Winner_Score"]) if m["Winner"] == p1 else int(m["Loser_Score"]) for m in h2h_matches)
        p2_pts = sum(int(m["Winner_Score"]) if m["Winner"] == p2 else int(m["Loser_Score"]) for m in h2h_matches)
        
        p1_wr = f"{(p1_wins / total_games * 100):.0f}%"
        p2_wr = f"{(p2_wins / total_games * 100):.0f}%"
        
        p1_avg_pts, p2_avg_pts = p1_pts / total_games, p2_pts / total_games
        
        blowout_match = max(h2h_matches, key=lambda m: abs(int(m['Winner_Score']) - int(m['Loser_Score'])))
        blowout_margin = int(blowout_match['Winner_Score']) - int(blowout_match['Loser_Score'])
        blowout_winner = blowout_match['Winner']
        
        close_games = [m for m in h2h_matches if abs(int(m['Winner_Score']) - int(m['Loser_Score'])) <= 2]
        p1_close_wins = sum(1 for m in close_games if m['Winner'] == p1)
        p2_close_wins = sum(1 for m in close_games if m['Winner'] == p2)
        
        st.markdown("### 📊 Lifetime History")
        col_stat1, col_stat2 = st.columns(2)
        
        with col_stat1:
            st.markdown(f"#### {p1} Stats")
            st.metric("Total Wins vs Opponent", p1_wins)
            st.metric("Winrate", p1_wr)
            st.metric("Avg Points Scored per Game", f"{p1_avg_pts:.1f}")

        with col_stat2:
            st.markdown(f"#### {p2} Stats")
            st.metric("Total Wins vs Opponent", p2_wins)
            st.metric("Winrate", p2_wr)
            st.metric("Avg Points Scored per Game", f"{p2_avg_pts:.1f}")
            
        st.divider()
        
        st.markdown("### 🌶️ Insightful Data")
        c1, c2 = st.columns(2)
        c1.info(f"**Biggest Blowout:** \n\n{blowout_winner} crushed by **{blowout_margin} points** ({blowout_match['Winner_Score']} - {blowout_match['Loser_Score']}).")
        
        if close_games:
            c2.warning(f"**Nail-biters (1-2 point diff):** \n\nOut of {len(close_games)} close games, {p1} won **{p1_close_wins}**, and {p2} won **{p2_close_wins}**.")
        else:
            c2.warning("**Nail-biters:** \n\nNone yet!")

        st.write("### Game History Breakdown")
        st.table(pd.DataFrame(h2h_matches).reset_index(drop=True))
    else:
        st.info("No recorded matches between these two players yet.")
