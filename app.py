import streamlit as st
import io
import csv
from typing import Dict, List, Tuple
from debate_scheduler import build_pairings, schedule_sessions, verify

# ------------------------------
# Page & brand
# ------------------------------
st.set_page_config(page_title="YES Debate Scheduler", page_icon="💬", layout="wide")

st.image("yes_logo.png", width=160)
st.markdown(
    "<h1 style='color:#00A0AF; margin-top:0'>YES – Debate Scheduler</h1>",
    unsafe_allow_html=True
)

# ------------------------------
# i18n (FR / DE)
# ------------------------------
I18N = {
    "fr": {
        "desc": "Planifie automatiquement des débats pour les catégories **S1** et **S2** — sans intra-école, 2 débats par équipe, et sessions équilibrées.",
        "cfg": "⚙️ Configuration",
        "rooms": "Salles par session",
        "generate": "Générer le planning",
        "tab_s1": "Catégorie S1",
        "tab_s2": "Catégorie S2",
        "schools_title": "{} — Écoles",
        "school_name": "🏫 École {}",
        "teams": "Équipes",
        "add_school": "➕ Ajouter une école à {}",
        "remove": "🗑️",
        "need_2_teams_either": "❌ Il faut au minimum 2 équipes en S1 **ou** en S2.",
        "success": "✅ Planning généré avec succès !",
        "verified": "Toutes les contraintes sont satisfaites ✅",
        "download": "⬇️ Télécharger le CSV",
        "caption": "Ajoute des écoles/équipes dans chaque onglet, puis clique **Générer le planning**.",
        "session": "🕐 Session {}",
        "room": "Salle",
        "category": "Catégorie",
        "team_a": "Équipe A",
        "team_b": "Équipe B",
        "free": "Libre",
        "error": "❌ Erreur : {}",
        "lang": "Langue",
        "lang_fr": "Français",
        "lang_de": "Allemand",
    },
    "de": {
        "desc": "Plane Debatten für **S1** und **S2** automatisch – keine schulinternen Duelle, 2 Debatten pro Team und ausgewogene Sessions.",
        "cfg": "⚙️ Einstellungen",
        "rooms": "Räume pro Session",
        "generate": "Zeitplan erstellen",
        "tab_s1": "Kategorie S1",
        "tab_s2": "Kategorie S2",
        "schools_title": "{} – Schulen",
        "school_name": "🏫 Schule {}",
        "teams": "Teams",
        "add_school": "➕ Schule zu {} hinzufügen",
        "remove": "🗑️",
        "need_2_teams_either": "❌ Mindestens 2 Teams in S1 **oder** in S2 erforderlich.",
        "success": "✅ Zeitplan erfolgreich erstellt!",
        "verified": "Alle Bedingungen sind erfüllt ✅",
        "download": "⬇️ CSV herunterladen",
        "caption": "Füge in jedem Tab Schulen/Teams hinzu und klicke dann auf **Zeitplan erstellen**.",
        "session": "🕐 Session {}",
        "room": "Raum",
        "category": "Kategorie",
        "team_a": "Team A",
        "team_b": "Team B",
        "free": "Frei",
        "error": "❌ Fehler: {}",
        "lang": "Sprache",
        "lang_fr": "Französisch",
        "lang_de": "Deutsch",
    },
}

# Lang selector in sidebar (persist in session)
with st.sidebar:
    st.header("YES")
    lang_label = I18N["fr"]["lang"]  # default label
    # small mapping so labels themselves are also translated
    choice = st.selectbox(
        I18N["fr"]["lang"] + " / " + I18N["de"]["lang"],
        (("fr", I18N["fr"]["lang_fr"]), ("de", I18N["de"]["lang_de"])),
        format_func=lambda x: x[1],
    )
    LANG = choice[0]

T = I18N[LANG]  # shorthand

st.markdown(T["desc"])

# ------------------------------
# Helpers
# ------------------------------
def sessions_to_csv_bytes(sessions: List[List[Tuple[str, str, str]]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Session", "Room", "Category", "Team A", "Team B"])
    for i, sess in enumerate(sessions, 1):
        for room_idx, (lvl, a, b) in enumerate(sess, 1):
            writer.writerow([i, room_idx, lvl, a, b])
    return buf.getvalue().encode("utf-8")

def render_school_list(level_label: str, key_prefix: str) -> Tuple[List[str], Dict[str, str]]:
    """Dynamic school inputs with add/remove buttons."""
    st.subheader(T["schools_title"].format(level_label))

    # Init session state for this level
    if f"{key_prefix}_schools" not in st.session_state:
        st.session_state[f"{key_prefix}_schools"] = [{"name": "", "teams": 2}]

    schools = st.session_state[f"{key_prefix}_schools"]

    for i, school in enumerate(schools):
        cols = st.columns([3, 1, 0.3])
        school["name"] = cols[0].text_input(
            T["school_name"].format(i + 1),
            value=school["name"],
            key=f"{key_prefix}_name_{i}",
        )
        school["teams"] = cols[1].number_input(
            T["teams"], min_value=1, max_value=12, value=school["teams"], key=f"{key_prefix}_teams_{i}"
        )
        if cols[2].button(T["remove"], key=f"{key_prefix}_remove_{i}"):
            del schools[i]
            st.rerun()

    add_col = st.columns([1, 5])[0]
    if add_col.button(T["add_school"].format(level_label), key=f"{key_prefix}_add"):
        schools.append({"name": "", "teams": 2})
        st.rerun()

    # Build teams list from entered schools
    teams: List[str] = []
    t2s: Dict[str, str] = {}
    for school in schools:
        name = school["name"].strip()
        if name:
            for k in range(1, int(school["teams"]) + 1):
                team = f"{name} #{k}"
                teams.append(team)
                t2s[team] = name
    return teams, t2s

def render_sessions_table(sessions: List[List[Tuple[str, str, str]]], rooms: int):
    for i, sess in enumerate(sessions, 1):
        st.markdown(f"### {T['session'].format(i)}")
        padded = sess + [("—", T["free"], "")] * max(0, rooms - len(sess))
        rows = []
        for idx, (lvl, a, b) in enumerate(padded, 1):
            if lvl == "—":
                rows.append((idx, T["free"], "—", "—"))
            else:
                rows.append((idx, lvl, a, b))
        st.table({
            T["room"]: [r[0] for r in rows],
            T["category"]: [r[1] for r in rows],
            T["team_a"]: [r[2] for r in rows],
            T["team_b"]: [r[3] for r in rows],
        })

# ------------------------------
# Sidebar config
# ------------------------------
with st.sidebar:
    st.header(T["cfg"])
    rooms = st.number_input(T["rooms"], min_value=1, max_value=50, value=4)
    games_per_team = 2  # fixed
    generate = st.button(T["generate"])

# ------------------------------
# Inputs
# ------------------------------
tab1, tab2 = st.tabs([T["tab_s1"], T["tab_s2"]])

with tab1:
    teams_S1, t2s_S1 = render_school_list("S1", "s1")

with tab2:
    teams_S2, t2s_S2 = render_school_list("S2", "s2")

# ------------------------------
# Schedule generation
# ------------------------------
if generate:
    try:
        # allow only S1 or only S2
        if len(teams_S1) < 2 and len(teams_S2) < 2:
            st.error(T["need_2_teams_either"])
            st.stop()

        pairings_by_level = {}
        if len(teams_S1) >= 2:
            pairings_by_level["S1"] = build_pairings(teams_S1, t2s_S1, games_per_team)
        if len(teams_S2) >= 2:
            pairings_by_level["S2"] = build_pairings(teams_S2, t2s_S2, games_per_team)

        sessions = schedule_sessions(
            rooms=rooms,
            pairings_by_level=pairings_by_level,
            games_per_team=games_per_team,
            want_mix_each_session=True,
        )

        st.success(T["success"])
        render_sessions_table(sessions, rooms)

        verify(
            sessions,
            teams_by_level={lvl: (teams_S1 if lvl == "S1" else teams_S2) for lvl in pairings_by_level},
            t2s_by_level={lvl: (t2s_S1 if lvl == "S1" else t2s_S2) for lvl in pairings_by_level},
            games_per_team=games_per_team,
            rooms=rooms,
        )
        st.info(T["verified"])

        st.download_button(
            T["download"],
            data=sessions_to_csv_bytes(sessions),
            file_name="YES_debate_schedule.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(T["error"].format(e))
else:
    st.caption(T["caption"])
