import streamlit as st
import pandas as pd

st.set_page_config(page_title="Squash Leaderboard & ELO Tracker", layout="wide", page_icon="🎾")

# --- CSS INJECTION TO FORCE CENTER ALIGNMENT ---
st.markdown("""
    <style>
    /* Target the exact Streamlit table containers to force center alignment */
    [data-testid="stTable"] th {
        text-align: center !important;
    }
    [data-testid="stTable"] td {
        text-align: center !important;
    }
    </style>
    """, unsafe_allow_html=True)
# -----------------------------------------------

# 1. Roster Initialization
players_list = ["Ambrus", "Andris", "Dávid", "Donát", "Marci", "Matyi", "Ricsi", "Zoli"]

if 'matches' not in st.session_state:
    st.session_state.matches = []

# 2. Advanced ELO & Stats Engine
def calculate_stats(matches):
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
        r_w, r_l = elo.get(w, 1200), elo.get(l, 1200)
        expected_w = 1 / (1 + 10 ** ((r_l - r_w) / 400))
        
        # Calculate the exact number of points that change hands
        points_exchanged = K * (1 - expected_w)
        
        # Winner takes the points, loser drops the points
        elo[w] = round(r_w + points_exchanged)
        elo[l] = round(r_l - points_exchanged)

    # Process metrics into a dataframe (Filtering out players with 0 matches)
    rows = []
    for p in players_list:
        s = stats[p]
        if s["Played"] == 0:
            continue # Skip adding to leaderboard if they haven't played
            
        wr = f"{(s['Won'] / s['Played'] * 100):.0f}%"
        avg_pt = f"{(s['Pts_Scored'] / s['Played']):.2f}"
        avg_diff = f"{((s['Pts_Scored'] - s['Pts_Conceded']) / s['Played']):.2f}"
        
        rows.append({
            "Rank": 0, "Player": p, "🔮 ELO Rating": elo[p],
            "Played": s["Played"], "Won": s["Won"],
