import streamlit as st
import pandas as pd

st.set_page_config(page_title="Squash Leaderboard & ELO Tracker", layout="wide", page_icon="🎾")

# 1. Roster and Existing History Initialization
players_list = ["Ambrus", "Andris", "Dávid", "Donát", "Marci", "Matyi", "Ricsi", "Zoli"]

if 'matches' not in st.session_state:
    # Seeding with a cross-section of your current match logs for demonstration
    st.session_state.matches = [
        {"Winner": "Zoli", "Winner_Score": 11, "Loser_Score": 6, "Loser": "Ambrus"},
        {"Winner": "Zoli", "Winner_Score": 13, "Loser_Score": 11, "Loser": "Ambrus"},
        {"Winner": "Zoli", "Winner_Score": 11, "Loser_Score": 1, "Loser": "Ambrus"},
        {"Winner": "Zoli", "Winner_Score": 11, "Loser_Score": 6, "Loser": "Ambrus"},
        {"Winner": "Ambrus", "Winner_Score": 12, "Loser_Score": 10, "Loser": "Zoli"},
        {"Winner": "Marci", "Winner_Score": 11, "Loser_Score": 5, "Loser": "Donát"},
        {"Winner": "Donát", "Winner_Score": 11, "Loser_Score": 7, "Loser": "Andris"},
        {"Winner": "Andris", "Winner_Score": 11, "Loser_Score": 9, "Loser": "Donát"},
        {"Winner": "Donát", "Winner_Score": 11, "Loser_Score": 4, "Loser": "Ambrus"}
    ]

# 2. Advanced ELO & Stats Engine
def calculate_leaderboard(matches):
    elo = {p: 1200 for p in players_list} # Base ELO starting score
    stats = {p: {"Played": 0, "Won": 0, "Pts_Scored": 0, "Pts_Conceded": 0} for p in players_list}
    K = 32 # ELO volatility factor
    
    for m in matches:
        w, l = m["Winner"], m["Loser"]
        w_pts, l_pts = m["Winner_Score"], m["Loser_Score"]
        
        # Accumulate Traditional Stats
        if w in stats:
            stats[w]["Played"] += 1; stats[w]["Won"] += 1
            stats[w]["Pts_Scored"] += w_pts; stats[w]["Pts_Conceded"] += l_pts
        if l in stats:
            stats[l]["Played"] += 1
            stats[l]["Pts_Scored"] += l_pts; stats[l]["Pts_Conceded"] += w_pts
            
        # Compute ELO
        r_w, r_l = elo[w], elo[l]
        expected_w = 1 / (1 + 10 ** ((r_l - r_w) / 400))
        elo[w] = round(r_w + K * (1 - expected_w))
        elo[l] = round(r_l - K * (0 - (1 - expected_w)))

    # Process metrics into a dataframe
    rows = []
    for p in players_list:
        s = stats[p]
        wr = f"{(s['Won'] / s['Played'] * 100):.1f}%" if s['Played'] > 0 else "0.0%"
        avg_pt = f"{(s['Pts_Scored'] / s['Played']):.2f}" if s['Played'] > 0 else "0.00"
        avg_diff = f"{((s['Pts_Scored'] - s['Pts_Conceded']) / s['Played']):.2f}" if s['Played'] > 0 else "0.00"
        
        rows.append({
            "Rank": 0, "Játékos": p, "🔮 ELO Rating": elo[p],
            "Játszott (H)": s["Played"], "Nyert (I)": s["Won"], "Winrate (J)": wr,
            "Össz. Pont (M)": s["Pts_Scored"], "átl. pont (K)": avg_pt, "átl. különbség (L)": avg_diff
        })
        
    df = pd.DataFrame(rows).sort_values(by="🔮 ELO Rating", ascending=False).reset_index(drop=True)
    df["Rank"] = df.index + 1
    return df

# 3. Application Interface Layout
st.sidebar.title("🏸 Squash Dashboard")
view = st.sidebar.radio("Go to:", ["🏆 Leaderboard", "📝 Record Match", "⚔️ 1v1 Head-to-Head"])

df_leaderboard = calculate_leaderboard(st.session_state.matches)

if view == "🏆 Leaderboard":
    st.title("🏆 Club Standings & Rankings")
    st.dataframe(df_leaderboard.set_index("Rank"), use_container_width=True)

elif view == "📝 Record Match":
    st.title("📝 Enter Match Result")
    with st.form("match_submission", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            winner = st.selectbox("Winner (A Column)", players_list)
            w_score = st.number_input("Winner Points (B Column)", min_value=0, value=11, step=1)
        with c2:
            loser = st.selectbox("Loser (D Column)", [p for p in players_list if p != winner])
            l_score = st.number_input("Loser Points (C Column)", min_value=0, value=8, step=1)
            
        submitted = st.form_submit_button("Submit & Re-calculate Ratings")
        if submitted:
            if w_score <= l_score:
                st.error("Error: Winner points must be strictly greater than loser points.")
            else:
                st.session_state.matches.append({
                    "Winner": winner, "Winner_Score": w_score, "Loser_Score": l_score, "Loser": loser
                })
                st.success(f"Match Saved! {winner} beat {loser} ({w_score}-{l_score})")
                st.rerun()

elif view == "⚔️ 1v1 Head-to-Head":
    st.title("⚔️ Rivalry Statistics")
    p1 = st.selectbox("Select Player One:", players_list)
    p2 = st.selectbox("Select Player Two:", [p for p in players_list if p != p1])
    
    # Filter historic matchups between the selected pair
    h2h_matches = [m for m in st.session_state.matches if (m["Winner"] == p1 and m["Loser"] == p2) or (m["Winner"] == p2 and m["Loser"] == p1)]
    p1_wins = sum(1 for m in h2h_matches if m["Winner"] == p1)
    p2_wins = sum(1 for m in h2h_matches if m["Winner"] == p2)
    
    st.subheader(f"Lifetime Matchup Record: {p1} vs {p2}")
    col_stat1, col_stat2 = st.columns(2)
    col_stat1.metric(f"{p1} Total Wins", p1_wins)
    col_stat2.metric(f"{p2} Total Wins", p2_wins)
    
    if h2h_matches:
        st.write("### Game History Breakdown")
        st.write(pd.DataFrame(h2h_matches))
    else:
        st.info("No recorded matches between these two players yet.")
