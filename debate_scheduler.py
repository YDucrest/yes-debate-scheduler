from __future__ import annotations
import math
import random
import itertools
import csv
from collections import Counter, defaultdict
from typing import List, Tuple, Dict, Set, Optional

random.seed(42)  # reproducibility

# ------------------------------
# Simple I/O helpers
# ------------------------------

def ask_int(prompt: str, *, min_val: int = 0) -> int:
    while True:
        s = input(prompt).strip()
        try:
            v = int(s)
            if v < min_val:
                print(f"Please enter an integer ≥ {min_val}.")
                continue
            return v
        except ValueError:
            print("Invalid number, try again.")

def ask_yesno(prompt: str) -> bool:
    while True:
        v = input(prompt).strip().lower()
        if v in {"y", "yes"}:
            return True
        if v in {"n", "no"}:
            return False
        print("Please answer yes/y or no/n.")

# ------------------------------
# Schools → teams input
# ------------------------------

def input_schools(level_label: str) -> Tuple[List[str], Dict[str, str]]:
    """
    Ask for schools and team counts.
    Returns (team_list, team->school mapping).
    """
    print(f"\n=== Enter schools for {level_label} ===")
    n_schools: int = ask_int(f"How many schools in {level_label}? ", min_val=1)

    teams: List[str] = []
    team2school: Dict[str, str] = {}

    for idx in range(1, n_schools + 1):
        school_name: str = input(f"School #{idx} name: ").strip()
        while not school_name:
            print("Name cannot be empty.")
            school_name = input(f"School #{idx} name: ").strip()
        n_teams: int = ask_int(f"How many teams for \"{school_name}\"? ", min_val=1)
        for k in range(1, n_teams + 1):
            team = f"{school_name} #{k}"
            teams.append(team)
            team2school[team] = school_name

    if len(teams) < 2:
        raise ValueError(f"You need at least 2 teams in {level_label}.")
    return teams, team2school

# ------------------------------
# Pairings inside one level
# ------------------------------

def all_allowed_pairs(teams: List[str], t2s: Dict[str, str]) -> List[Tuple[str, str]]:
    """All inter-school pairs (no intra-school)."""
    out: List[Tuple[str, str]] = []
    for a, b in itertools.combinations(teams, 2):
        if t2s[a] != t2s[b]:
            out.append((a, b))
    return out

def build_pairings(
    teams: List[str],
    t2s: Dict[str, str],
    games_per_team: int = 2
) -> List[Tuple[str, str]]:
    """
    Greedy weighted heuristic:
      - each team plays games_per_team times
      - no intra-school
      - minimize repeated school pairs and opponent repeats
    """
    n = len(teams)
    if n < 2:
        raise ValueError("Need at least 2 teams.")
    if games_per_team < 1:
        raise ValueError("games_per_team must be ≥ 1.")
    need = n * games_per_team
    if need % 2 != 0:
        raise ValueError("Total team-slots must be even.")

    required_matches = need // 2
    pairs = all_allowed_pairs(teams, t2s)
    if not pairs:
        raise ValueError("No inter-school pairs available.")

    degree: Counter[str] = Counter()
    used_vs: Dict[str, Set[str]] = defaultdict(set)
    school_pair_count: Counter[Tuple[str, str]] = Counter()
    result: List[Tuple[str, str]] = []

    def sp_key(a: str, b: str) -> Tuple[str, str]:
        sa, sb = t2s[a], t2s[b]
        return (sa, sb) if sa < sb else (sb, sa)

    def pair_cost(a: str, b: str) -> Tuple[float, float, float, float]:
        sp = sp_key(a, b)
        c1 = float(max(degree[a], degree[b]))       # spread load
        c2 = float(school_pair_count[sp])           # avoid repeating school pair
        c3 = 1.0 if (b in used_vs[a]) else 0.0      # avoid opponent repeat
        c4 = random.random()                        # tiny randomness
        return (c1, c2, c3, c4)

    for _ in range(required_matches):
        candidates: List[Tuple[str, str]] = []
        for a, b in pairs:
            if degree[a] >= games_per_team or degree[b] >= games_per_team:
                continue
            if b in used_vs[a]:
                continue
            candidates.append((a, b))

        if not candidates:
            # allow one opponent repeat if stuck
            for a, b in pairs:
                if degree[a] < games_per_team and degree[b] < games_per_team:
                    candidates.append((a, b))
            if not candidates:
                raise RuntimeError("Stuck: cannot complete pairings.")

        a, b = min(candidates, key=lambda p: pair_cost(p[0], p[1]))
        result.append((a, b))
        degree[a] += 1
        degree[b] += 1
        used_vs[a].add(b); used_vs[b].add(a)
        school_pair_count[sp_key(a, b)] += 1

    # sanity
    for t in teams:
        if degree[t] != games_per_team:
            raise AssertionError(f"{t} has {degree[t]} matches (expected {games_per_team}).")

    return result

# ------------------------------
# Session scheduling
# ------------------------------

def min_sessions_needed(rooms: int, teams_by_level: Dict[str, List[str]], games_per_team: int) -> int:
    total_matches = sum((len(v) * games_per_team) // 2 for v in teams_by_level.values())
    return max(games_per_team, math.ceil(total_matches / rooms))

def capacities_with_free_spread_at_end(
    rooms: int, total_matches: int, min_sessions: int
) -> List[int]:
    """
    Compute per-session capacities so that:
      - we use exactly 'min_sessions' sessions initially,
      - earlier sessions are as full as possible,
      - any free rooms are spread across the LAST sessions (not only the very last).
    """
    S = max(2, min_sessions)
    total_capacity = S * rooms
    if total_capacity < total_matches:
        # not enough sessions, bump S to fit all matches
        S = math.ceil(total_matches / rooms)
        total_capacity = S * rooms

    # Start with full capacity for all sessions.
    caps = [rooms] * S
    free_slots = total_capacity - total_matches  # how many empty slots we must leave overall
    # Spread free slots across the last sessions: 1 per session from the end
    i = S - 1
    while free_slots > 0 and i >= 0:
        if caps[i] > 0:
            caps[i] -= 1
            free_slots -= 1
        i -= 1
        if i < 0 and free_slots > 0:
            i = S - 1  # wrap again if more free than sessions (very rare)
    return caps

def schedule_sessions(
    rooms: int,
    pairings_by_level: Dict[str, List[Tuple[str, str]]],
    games_per_team: int,
    want_mix_each_session: bool = True
) -> List[List[Tuple[str, str, str]]]:
    """
    Build sessions:
      - at most 1 match per team per session
      - balanced S1/S2 per session as much as possible
      - ORDER in each session: S1 matches occupy the first room numbers, then S2.
      - free rooms are spread across the last sessions.
    """
    remaining: Dict[str, List[Tuple[str, str]]] = {lvl: pairings[:] for lvl, pairings in pairings_by_level.items()}
    for v in remaining.values():
        random.shuffle(v)

    total_remaining = sum(len(v) for v in remaining.values())
    teams_by_level: Dict[str, List[str]] = {k: list({t for pair in v for t in pair}) for k, v in pairings_by_level.items()}

    est_min_sessions = min_sessions_needed(rooms, teams_by_level, games_per_team)
    caps = capacities_with_free_spread_at_end(rooms, total_remaining, est_min_sessions)

    sessions: List[List[Tuple[str, str, str]]] = []

    def pop_match(level: str, used_teams: Set[str]) -> Optional[Tuple[str, str]]:
        for i, (a, b) in enumerate(remaining[level]):
            if a not in used_teams and b not in used_teams:
                remaining[level].pop(i)
                return (a, b)
        return None

    for s_idx, cap in enumerate(caps):
        if total_remaining == 0:
            sessions.append([])  # this one will be entirely free
            continue

        used: Set[str] = set()
        s1_matches: List[Tuple[str, str, str]] = []
        s2_matches: List[Tuple[str, str, str]] = []

        # Target split per level for this session to keep balance
        sessions_left = len(caps) - s_idx
        target: Dict[str, int] = {
            lvl: math.ceil(len(lst) / sessions_left) for lvl, lst in remaining.items()
        }

        def place_from_level(level: str) -> bool:
            nonlocal total_remaining
            match = pop_match(level, used)
            if match is None:
                return False
            if level == "S1":
                s1_matches.append((level, match[0], match[1]))
            else:
                s2_matches.append((level, match[0], match[1]))
            used.update(match)
            total_remaining -= 1
            return True

        # Fill up to 'cap' matches, trying to respect 'target' per level.
        while (len(s1_matches) + len(s2_matches)) < cap and total_remaining > 0:
            chosen: Optional[str] = None
            if want_mix_each_session:
                # Prefer the level that is currently under its target
                for lvl in ("S1", "S2"):
                    if len(s1_matches) + len(s2_matches) >= cap:
                        break
                    already = len(s1_matches) if lvl == "S1" else len(s2_matches)
                    if already < target.get(lvl, 0) and remaining[lvl]:
                        chosen = lvl
                        break
            if chosen is None:
                # Otherwise pick the level with more matches left
                chosen = "S1" if len(remaining["S1"]) >= len(remaining["S2"]) else "S2"
                if not remaining[chosen]:
                    chosen = "S2" if chosen == "S1" else "S1"
                    if not remaining[chosen]:
                        break

            if not place_from_level(chosen):
                # Try the other level if blocked by per-session team reuse
                other = "S2" if chosen == "S1" else "S1"
                if not place_from_level(other):
                    # Nothing placeable -> stop this session
                    break

        # ORDER: S1 first, then S2 (rooms 1..k = S1, rest = S2)
        session_matches = s1_matches + s2_matches
        sessions.append(session_matches)

    # If any matches remain (rare corner), add extra sessions (also spread free naturally at the end)
    while total_remaining > 0:
        caps = capacities_with_free_spread_at_end(rooms, total_remaining, 1)
        for cap in caps:
            used_extra: Set[str] = set()
            s1_extra: List[Tuple[str, str, str]] = []
            s2_extra: List[Tuple[str, str, str]] = []
            while (len(s1_extra) + len(s2_extra)) < cap and total_remaining > 0:
                chosen = "S1" if len(remaining["S1"]) >= len(remaining["S2"]) else "S2"
                if not remaining[chosen]:
                    chosen = "S2" if chosen == "S1" else "S1"
                    if not remaining[chosen]:
                        break
                m = pop_match(chosen, used_extra)
                if m is None:
                    other = "S2" if chosen == "S1" else "S1"
                    m2 = pop_match(other, used_extra)
                    if m2 is None:
                        break
                    if other == "S1":
                        s1_extra.append((other, m2[0], m2[1]))
                    else:
                        s2_extra.append((other, m2[0], m2[1]))
                    used_extra.update(m2); total_remaining -= 1
                else:
                    if chosen == "S1":
                        s1_extra.append((chosen, m[0], m[1]))
                    else:
                        s2_extra.append((chosen, m[0], m[1]))
                    used_extra.update(m); total_remaining -= 1
            sessions.append(s1_extra + s2_extra)

    return sessions

# ------------------------------
# Output & verification
# ------------------------------

def pretty_print(sessions: List[List[Tuple[str, str, str]]], rooms: int) -> None:
    print("\n====== SCHEDULE ======")
    for i, sess in enumerate(sessions, 1):
        print(f"\nSession {i}")
        # pad with "Free" up to number of rooms
        padded: List[Tuple[str, str, str]] = sess + [("—", "Free", "")] * max(0, rooms - len(sess))
        for room_idx, (lvl, a, b) in enumerate(padded, 1):
            if lvl == "—":
                print(f"  Room {room_idx}: Free")
            else:
                print(f"  Room {room_idx}: {lvl} | {a}  vs  {b}")

def export_csv(sessions: List[List[Tuple[str, str, str]]], filename: str) -> None:
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Session", "Room", "Category", "Team A", "Team B"])
        for i, sess in enumerate(sessions, 1):
            for room_idx, (lvl, a, b) in enumerate(sess, 1):
                writer.writerow([i, room_idx, lvl, a, b])
    print(f"\nCSV exported → {filename}")

def verify(
    sessions: List[List[Tuple[str, str, str]]],
    teams_by_level: Dict[str, List[str]],
    t2s_by_level: Dict[str, Dict[str, str]],
    games_per_team: int,
    rooms: int
) -> None:
    per_team: Counter[str] = Counter()
    for sess in sessions:
        assert len(sess) <= rooms
        used: Set[str] = set()
        for lvl, a, b in sess:
            if lvl not in teams_by_level:
                continue
            # correct category
            assert a in teams_by_level[lvl] and b in teams_by_level[lvl], f"Wrong level for {a} or {b}"
            # no intra-school
            assert t2s_by_level[lvl][a] != t2s_by_level[lvl][b], f"Intra-school: {a} vs {b}"
            # at most one match/team/session
            assert a not in used and b not in used, "Team scheduled twice in same session"
            used.update([a, b])
            per_team[a] += 1; per_team[b] += 1

    for lvl, teams in teams_by_level.items():
        for t in teams:
            assert per_team[t] == games_per_team, f"{t} has {per_team[t]} matches (expected {games_per_team})"
    print("\nVERIFICATION OK ✅ (all constraints satisfied)")

# ------------------------------
# Main
# ------------------------------

def main() -> None:
    print("=== Debate Schedule Generator (S1 & S2) ===")
    rooms: int = ask_int("How many rooms per session? ", min_val=1)
    games_per_team: int = 2  # fixed as requested

    teams_S1, t2s_S1 = input_schools("S1")
    teams_S2, t2s_S2 = input_schools("S2")

    # 1) pairings per level
    pairings_S1 = build_pairings(teams_S1, t2s_S1, games_per_team)
    pairings_S2 = build_pairings(teams_S2, t2s_S2, games_per_team)

    # 2) schedule sessions (S1 first rooms, then S2; mixed & balanced)
    sessions = schedule_sessions(
        rooms=rooms,
        pairings_by_level={"S1": pairings_S1, "S2": pairings_S2},
        games_per_team=games_per_team,
        want_mix_each_session=True,
    )

    # 3) print & verify
    pretty_print(sessions, rooms)
    verify(
        sessions,
        teams_by_level={"S1": teams_S1, "S2": teams_S2},
        t2s_by_level={"S1": t2s_S1, "S2": t2s_S2},
        games_per_team=games_per_team,
        rooms=rooms,
    )

    # 4) optional CSV
    if ask_yesno("\nExport to CSV? (y/n) "):
        filename = input("Filename (e.g., schedule.csv): ").strip() or "schedule.csv"
        export_csv(sessions, filename)

if __name__ == "__main__":
    main()
