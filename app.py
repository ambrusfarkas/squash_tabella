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
SHEET_URL = "https://docs.google.com/spreadsheets/d/1O1A0kF4rxf-oxoyTYCyeMFGXCCMi-GpURSjH7U8_ACY/edit"

# Initialize connection
conn = st.connection("gsheets", type=GSheetsConnection)

# Read Data safely
try:
    # Explicitly targeted to the "Matches" tab
    df_database = conn.read(spreadsheet=SHEET_URL, worksheet="Matches", usecols=[0, 1, 2, 3], ttl=0) 
    df_database = df_database.dropna(how="all")
    st.session_state.matches = df_database.to_dict('records')
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Error: {e}")
    if 'matches' not in st.session_state:
        st.session_state.matches = []
# -----------------------------------------

def calculate_stats(matches):
    elo = {p: 1200 for p in players_list}
    stats = {p: {"Played": 0, "Won": 0, "Pts_Scored": 0, "Pts_Conceded": 0} for p in players_list}
    K = 32
    
    for m in matches:
        w = str(m.get("Winner", "")).strip()
        l = str(m.get("Loser", "")).strip()
        
        if w == 'nan' or l == 'nan' or not w or not l:
            continue
            
        try:
            w_pts = int(m.get("Winner_Score", 0))
            l_pts = int(m.get("Loser_Score", 0))
        except ValueError:
            continue # Skip corrupted rows
        
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
        
        row_data = {
            "Rank": 0,
            "Player": p,
            "🔮 ELO Rating": elo[p],
            "Played": s["Played"],
            "Won": s["Won"],
            "Winrate": wr,
            "Total Points": s["Pts_Scored"],
            "Avg Points": avg_pt,
            "Avg Diff": avg_diff
        }
        rows.append(row_data)
        
    if rows:
        df = pd.DataFrame(rows).sort_values(by="🔮 ELO Rating", ascending=False).reset_index(drop=True)
        # Add ranking numbers 1, 2, 3...
        df["Rank"] = df.index + 1
    else:
        df = pd.DataFrame(columns=["Rank", "Player", "🔮 ELO Rating", "Played", "Won", "Winrate", "Total Points", "Avg Points", "Avg Diff"])
        
    return df, elo

df_leaderboard, current_elos = calculate_stats(st.session_state.matches)

st.sidebar.title("🏸 Squash Dashboard")
view = st.sidebar.radio("Navigation", ["🏆 Leaderboard", "📝 Record Match", "⚔️ 1v1 Head-to-Head"])

if view == "🏆 Leaderboard":
    st.title("🏆 Leaderboard")
    if not st.session_state.matches:
        st.warning("No matches recorded yet. Play a game!")
    else:
        st.table(df_leaderboard.style.hide(axis="index"))

elif view == "📝 Record Match":
    st.title("📝 Enter Match Result")
    
    c1, c2 = st.columns(2)
    with c1:
        winner = st.selectbox("Winner", players_list, index=None, placeholder="Select the winner...")
        w_score = st.number_input("Winner Points", min_value=0, value=11, step=1)
        
    with c2:
        loser_options = [p for p in players_list if p != winner] if winner else players_list
        loser = st.selectbox("Loser", loser_options, index=None, placeholder="Select the loser...")
        
        default_loser_points = 8
        if winner and loser:
            relevant_matches = [m for m in st.session_state.matches if m.get("Winner") == winner and m.get("Loser") == loser]
            if relevant_matches:
                try:
                    avg_loser_score = sum(int(m.get("Loser_Score", 0)) for m in relevant_matches) / len(relevant_matches)
                    default_loser_points = int(round(avg_loser_score))
                except ValueError:
                    pass
                
        l_score = st.number_input("Loser Points", min_value=0, value=default_loser_points, step=1)
        
        if winner and loser and default_loser_points != 8:
            st.caption(f"*(Auto-filled with {loser}'s avg score against {winner})*")
            
    st.write("")
    
    submitted = st.button("Save Match to Cloud Database ☁️")
    
    if submitted:
        if not winner or not loser:
            st.error("Please select both a winner and a loser.")
        elif w_score <= l_score:
            st.error("Error: Winner points must be strictly greater than loser points.")
        else:
            new_match = {
                "Winner": winner, 
                "Winner_Score": int(w_score), 
                "Loser_Score": int(l_score), 
                "Loser": loser
            }
            st.session_state.matches.append(new_match)
            
            updated_df = pd.DataFrame(st.session_state.matches)
            updated_df = updated_df[["Winner", "Winner_Score", "Loser_Score", "Loser"]]
            
            try:
                conn.update(spreadsheet=SHEET_URL, worksheet="Matches", data=updated_df)
                st.cache_data.clear()
                st.success(f"Match Saved to Google Sheets! {winner} beat {loser} ({w_score}-{l_score})")
                st.rerun() 
            except Exception as e:
                st.error(f"Failed to save to Google Sheets: {e}")

elif view == "⚔️ 1v1 Head-to-Head":
    st.title("⚔️ Rivalry Statistics")
    
    # Filter the list to only include players who have played at least one match
    active_players = df_leaderboard["Player"].tolist() if not df_leaderboard.empty else []
    
    if len(active_players) < 2:
        st.info("Not enough players have played matches to compare yet! Go record some matches.")
    else:
        p1 = st.selectbox("Select Player One:", active_players)
        p2 = st.selectbox("Select Player Two:", [p for p in active_players if p != p1])
        
        elo_p1, elo_p2 = current_elos.get(p1, 1200), current_elos.get(p2, 1200)
        h2h_matches = [m for m in st.session_state.matches if (m.get("Winner") == p1 and m.get("Loser") == p2) or (m.get("Winner") == p2 and m.get("Loser") == p1)]
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
            p1_wins = sum(1 for m in h2h_matches if m.get("Winner") == p1)
            p2_wins = sum(1 for m in h2h_matches if m.get("Winner") == p2)
            
            try:
                p1_pts = sum(int(m.get("Winner_Score", 0)) if m.get("Winner") == p1 else int(m.get("Loser_Score", 0)) for m in h2h_matches)
                p2_pts = sum(int(m.get("Winner_Score", 0)) if m.get("Winner") == p2 else int(m.get("Loser_Score", 0)) for m in h2h_matches)
                
                p1_wr = f"{(p1_wins / total_games * 100):.0f}%"
                p2_wr = f"{(p2_wins / total_games * 100):.0f}%"
                
                p1_avg_pts, p2_avg_pts = p1_pts / total_games, p2_pts / total_games
                
                blowout_match = max(h2h_matches, key=lambda m: abs(int(m.get('Winner_Score', 0)) - int(m.get('Loser_Score', 0))))
                blowout_margin = int(blowout_match.get('Winner_Score', 0)) - int(blowout_match.get('Loser_Score', 0))
                blowout_winner = blowout_match.get('Winner')
                
                close_games = [m for m in h2h_matches if abs(int(m.get('Winner_Score', 0)) - int(m.get('Loser_Score', 0))) <= 2]
                p1_close_wins = sum(1 for m in close_games if m.get('Winner') == p1)
                p2_close_wins = sum(1 for m in close_games if m.get('Winner') == p2)
                
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
                
                # Forced integer formatting to avoid .0 decimals in blowout string
                b_w_score = int(blowout_match.get('Winner_Score'))
                b_l_score = int(blowout_match.get('Loser_Score'))
                c1.info(f"**Biggest Blowout:** \n\n{blowout_winner} crushed by **{blowout_margin} points** ({b_w_score} - {b_l_score}).")
                
                if close_games:
                    c2.warning(f"**Nail-biters (1-2 point diff):** \n\nOut of {len(close_games)} close games, {p1} won **{p1_close_wins}**, and {p2} won **{p2_close_wins}**.")
                else:
                    c2.warning("**Nail-biters:** \n\nNone yet!")

                st.write("### Game History Breakdown")
                
                # Format dataframe to ensure clean integer values 
                display_df = pd.DataFrame(h2h_matches)
                display_df["Winner_Score"] = display_df["Winner_Score"].astype(int)
                display_df["Loser_Score"] = display_df["Loser_Score"].astype(int)
                
                st.table(display_df.style.hide(axis="index"))
                
            except ValueError:
                st.error("There is a formatting error in your historical match scores. Please check your Google Sheet for text inside the score columns.")
        else:
            st.info("No recorded matches between these two players yet.")
