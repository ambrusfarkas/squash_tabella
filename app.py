import streamlit as st
import pandas as pd

st.set_page_config(page_title="Squash Leaderboard & ELO Tracker", layout="wide", page_icon="🎾")

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

    # Process metrics into a dataframe
    rows = []
    for p in players_list:
        s = stats[p]
        wr = f"{(s['Won'] / s['Played'] * 100):.0f}%" if s['Played'] > 0 else "0%"
        avg_pt = f"{(s['Pts_Scored'] / s['Played']):.2f}" if s['Played'] > 0 else "0.00"
        avg_diff = f"{((s['Pts_Scored'] - s['Pts_Conceded']) / s['Played']):.2f}" if s['Played'] > 0 else "0.00"
        
        rows.append({
            "Helyezés": 0, "Játékos": p, "🔮 ELO Rating": elo[p],
            "Játszott": s["Played"], "Nyert": s["Won"], "Winrate": wr,
            "Össz. Pont": s["Pts_Scored"], "átl. pont": avg_pt, "átl. különbség": avg_diff
        })
        
    df = pd.DataFrame(rows).sort_values(by="🔮 ELO Rating", ascending=False).reset_index(drop=True)
    df["Helyezés"] = df.index + 1
    return df, elo

# Calculate global stats to use across pages
df_leaderboard, current_elos = calculate_stats(st.session_state.matches)

# 3. Application Interface Layout
st.sidebar.title("🏸 Squash Dashboard")
view = st.sidebar.radio("Go to:", ["🏆 Leaderboard", "📝 Record Match", "⚔️ 1v1 Head-to-Head", "⚙️ Data Management"])

if view == "🏆 Leaderboard":
    st.title("🏆 Club Standings & Rankings")
    if not st.session_state.matches:
        st.warning("No matches recorded yet. Go to 'Data Management' to upload your CSV!")
    st.dataframe(df_leaderboard.set_index("Helyezés"), use_container_width=True)

elif view == "📝 Record Match":
    st.title("📝 Enter Match Result")
    with st.form("match_submission", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            winner = st.selectbox("Nyertes (Winner)", players_list)
            w_score = st.number_input("Nyertes pont (Winner Points)", min_value=0, value=11, step=1)
        with c2:
            loser = st.selectbox("Vesztes (Loser)", [p for p in players_list if p != winner])
            l_score = st.number_input("Vesztes pont (Loser Points)", min_value=0, value=8, step=1)
            
        submitted = st.form_submit_button("Mentés (Save)")
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
    
    # Current Elo for Predictions
    elo_p1 = current_elos.get(p1, 1200)
    elo_p2 = current_elos.get(p2, 1200)
    
    # Filter historic matchups
    h2h_matches = [m for m in st.session_state.matches if (m["Winner"] == p1 and m["Loser"] == p2) or (m["Winner"] == p2 and m["Loser"] == p1)]
    total_games = len(h2h_matches)
    
    p1_wins = sum(1 for m in h2h_matches if m["Winner"] == p1)
    p2_wins = sum(1 for m in h2h_matches if m["Winner"] == p2)
    
    p1_pts = sum(m["Winner_Score"] if m["Winner"] == p1 else m["Loser_Score"] for m in h2h_matches)
    p2_pts = sum(m["Winner_Score"] if m["Winner"] == p2 else m["Loser_Score"] for m in h2h_matches)
    
    # Calculate derived stats safely
    p1_wr = f"{(p1_wins / total_games * 100):.0f}%" if total_games > 0 else "0%"
    p2_wr = f"{(p2_wins / total_games * 100):.0f}%" if total_games > 0 else "0%"
    
    p1_avg_diff = (p1_pts - p2_pts) / total_games if total_games > 0 else 0
    p2_avg_diff = (p2_pts - p1_pts) / total_games if total_games > 0 else 0
    
    # ELO Prediction Math
    K = 32
    exp_p1_win = 1 / (1 + 10 ** ((elo_p2 - elo_p1) / 400))
    pts_if_p1_wins = round(K * (1 - exp_p1_win))
    
    exp_p2_win = 1 / (1 + 10 ** ((elo_p1 - elo_p2) / 400))
    pts_if_p2_wins = round(K * (1 - exp_p2_win))

    st.subheader(f"Current Matchup: {p1} vs {p2}")
    
    # Show Current ELO & Stakes
    st.markdown("### 🔮 Match Stakes")
    col_elo1, col_elo2 = st.columns(2)
    col_elo1.metric(f"{p1} Current Elo", elo_p1)
    col_elo2.metric(f"{p2} Current Elo", elo_p2)
    
    st.info(f"**If {p1} wins:** {p1} gains +{pts_if_p1_wins} Elo, {p2} drops -{pts_if_p1_wins} Elo. \n\n"
            f"**If {p2} wins:** {p2} gains +{pts_if_p2_wins} Elo, {p1} drops -{pts_if_p2_wins} Elo.")
    
    st.divider()
    
    # Show Lifetime Stats
    st.markdown("### 📊 Lifetime History")
    col_stat1, col_stat2 = st.columns(2)
    
    with col_stat1:
        st.markdown(f"#### {p1} Stats")
        st.metric("Total Wins vs Opponent", p1_wins)
        st.metric("Winrate", p1_wr)
        st.metric("Total Points Scored", p1_pts)
        st.metric("Avg Score Difference", f"{p1_avg_diff:+.1f}")

    with col_stat2:
        st.markdown(f"#### {p2} Stats")
        st.metric("Total Wins vs Opponent", p2_wins)
        st.metric("Winrate", p2_wr)
        st.metric("Total Points Scored", p2_pts)
        st.metric("Avg Score Difference", f"{p2_avg_diff:+.1f}")
    
    if h2h_matches:
        st.write("### Game History Breakdown")
        st.dataframe(pd.DataFrame(h2h_matches), use_container_width=True)
    else:
        st.info("No recorded matches between these two players yet.")

elif view == "⚙️ Data Management":
    st.title("⚙️ Manage Your Database")
    
    st.subheader("📥 Backup Your Data")
    st.write("Download your current match history to your device so you never lose it.")
    
    if st.session_state.matches:
        matches_df = pd.DataFrame(st.session_state.matches)
        # Ensure correct column order for exporting
        if set(["Winner", "Winner_Score", "Loser_Score", "Loser"]).issubset(matches_df.columns):
            export_df = matches_df[["Winner", "Winner_Score", "Loser_Score", "Loser"]]
            csv_data = export_df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="💾 Download Database Backup (CSV)",
                data=csv_data,
                file_name="squash_database_backup.csv",
                mime="text/csv"
            )
    else:
        st.info("No matches recorded yet. Add some matches to download a backup.")
        
    st.divider()

    st.subheader("📤 Upload Historical Matches")
    st.write("Upload a previously saved CSV backup to restore your data.")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    
    if uploaded_file is not None:
        try:
            df_upload = pd.read_csv(uploaded_file)
            
            # This checks for both our English app columns and your old Hungarian spreadsheet columns
            has_app_cols = "Winner" in df_upload.columns and "Loser" in df_upload.columns
            has_sheet_cols = "Nyertes" in df_upload.columns and "Vesztes" in df_upload.columns
            
            if has_app_cols or has_sheet_cols:
                imported_matches = []
                
                # Map column names based on the file type uploaded
                col_w = "Winner" if has_app_cols else "Nyertes"
                col_w_pts = "Winner_Score" if has_app_cols else "Nyertes pont"
                col_l_pts = "Loser_Score" if has_app_cols else "Vesztes pont"
                col_l = "Loser" if has_app_cols else "Vesztes"
                
                for index, row in df_upload.dropna(subset=[col_w, col_l]).iterrows():
                    imported_matches.append({
                        "Winner": str(row[col_w]).strip(),
                        "Winner_Score": int(row[col_w_pts]),
                        "Loser_Score": int(row[col_l_pts]),
                        "Loser": str(row[col_l]).strip()
                    })
                
                if st.button("Load Data & Overwrite Current Memory"):
                    st.session_state.matches = imported_matches
                    st.success(f"Successfully loaded {len(imported_matches)} matches!")
                    st.rerun()
            else:
                st.error("Could not find the correct columns in the CSV. Make sure you upload a valid backup.")
        except Exception as e:
            st.error(f"Error reading file: {e}")
