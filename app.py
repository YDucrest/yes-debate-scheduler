import streamlit as st
import io
import csv
from typing import Dict, List, Tuple
from debate_scheduler import build_pairings, schedule_sessions, verify

st.set_page_config(page_title="YES Debate Scheduler", page_icon="💬", layout="wide")

st.image("yes_logo.png", width=160)
st.markdown(
    "<h1 style='color:#00A0AF;'>YES – Debate Scheduler</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "Planify debates automatically for **S1** and **S2** categories — "
    "no intra-school matches, 2 debates per team, and balanced sessions."
)

# ========================
# Helpers
# ========================

def sessions_to_csv_bytes(sessions: List[List[Tuple[str, str, str]]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Session", "Room", "Category", "Team A", "Team B"])
    for i, sess in enumerate(sessions, 1):
        for room_idx, (lvl, a, b) in enumerate(sess, 1):
            writer.writerow([i, room_idx, lvl, a, b])
    return buf.getvalue().encode("utf-8")

def render_school_list(level_label: str, key_prefix: str) -> Tuple[List[str], Dict[str, str]]:
    """Display dynamic school inputs with add/remove buttons"""
    st.subheader(f"{level_label} schools")

    if f"{key_prefix}_schools" not in st.session_state:
        st.session_state[f"{key_prefix}_schools"] = [{"name": "", "teams": 2}]

    schools = st.session_state[f"{key_prefix}_schools"]

    for i, school in enumerate(schools):
        cols = st.columns([3, 1, 0.3])
        school["name"] = cols[0].text_input(
            f"🏫 School {i+1} name", value=school["name"], key=f"{key_prefix}_name_{i}"
        )
        school["teams"] = cols[1].number_input(
            "Teams", min_value=1, max_value=6, value=school["teams"], key=f"{key_prefix}_teams_{i}"
        )
        if cols[2].button("🗑️", key=f"{key_prefix}_remove_{i}"):
            del schools[i]
            st.rerun()

    add_col = st.columns([1, 5])[0]
    if add_col.button(f"➕ Add school to {level_label}", key=f"{key_prefix}_add"):
        schools.append({"name": "", "teams": 2})
        st.rerun()

    # Build teams list
    teams, t2s = [], {}
    for school in schools:
        if school["name"].strip():
            for k in range(1, int(school["teams"]) + 1):
                team = f"{school['name'].strip()} #{k}"
                teams.append(team)
                t2s[team] = school["name"].strip()
    return teams, t2s


def render_sessions_table(sessions: List[List[Tuple[str, str, str]]], rooms: int):
    for i, sess in enumerate(sessions, 1):
        st.markdown(f"### 🕐 Session {i}")
        padded = sess + [("—", "Free", "")] * max(0, rooms - len(sess))
        rows = []
        for idx, (lvl, a, b) in enumerate(padded, 1):
            if lvl == "—":
                rows.append((idx, "Free", "—", "—"))
            else:
                rows.append((idx, lvl, a, b))
        st.table({
            "Room": [r[0] for r in rows],
            "Category": [r[1] for r in rows],
            "Team A": [r[2] for r in rows],
            "Team B": [r[3] for r in rows]
        })

# ========================
# Sidebar config
# ========================

with st.sidebar:
    st.header("⚙️ Configuration")
    rooms = st.number_input("Rooms per session", min_value=1, max_value=20, value=4)
    games_per_team = 2
    generate = st.button("Generate schedule")

# ========================
# Inputs
# ========================

tab1, tab2 = st.tabs(["Category S1", "Category S2"])

with tab1:
    teams_S1, t2s_S1 = render_school_list("S1", "s1")

with tab2:
    teams_S2, t2s_S2 = render_school_list("S2", "s2")

# ========================
# Schedule generation
# ========================

if generate:
    try:
        if len(teams_S1) < 2 or len(teams_S2) < 2:
            st.error("❌ You need at least 2 teams in each category.")
            st.stop()

        # 1) Build pairings (from your algorithm)
        pairings_S1 = build_pairings(teams_S1, t2s_S1, games_per_team)
        pairings_S2 = build_pairings(teams_S2, t2s_S2, games_per_team)

        # 2) Schedule sessions
        sessions = schedule_sessions(
            rooms=rooms,
            pairings_by_level={"S1": pairings_S1, "S2": pairings_S2},
            games_per_team=games_per_team,
            want_mix_each_session=True,
        )

        # 3) Display results
        st.success("✅ Schedule generated successfully!")
        render_sessions_table(sessions, rooms)

        # 4) Verify (your original function)
        verify(
            sessions,
            teams_by_level={"S1": teams_S1, "S2": teams_S2},
            t2s_by_level={"S1": t2s_S1, "S2": t2s_S2},
            games_per_team=games_per_team,
            rooms=rooms,
        )
        st.info("All constraints satisfied ✅")

        # 5) Download CSV
        st.download_button(
            "⬇️ Download CSV file",
            data=sessions_to_csv_bytes(sessions),
            file_name="YES_debate_schedule.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"❌ Error: {e}")
else:
    st.caption("Add schools and teams below, then click **Generate schedule** in the sidebar.")
