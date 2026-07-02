"""Turn raw player stats into natural-language scouting text.

This is the trick that makes vector search shine: we convert numeric rows into
a sentence describing *playing style*, store it in a `semantic_text` field, and
let Elasticsearch (via EIS) embed it. Similar STYLE then lives near in vector
space — not just similar numbers.
"""
from __future__ import annotations

import pandas as pd

# Fuzzy column detection — the CSV's exact headers vary, so we match on keywords.
COLUMN_HINTS = {
    "name": ["player_name", "name", "player", "full_name"],
    "team": ["team", "nation", "country", "national_team", "squad"],
    "position": ["position", "pos", "role"],
    "age": ["age"],
    "height": ["height", "height_cm"],
    "goals": ["goals", "goal"],
    "assists": ["assists", "assist"],
    "shots": ["shots", "shots_total", "shots_on_target"],
    "passes": ["passes_completed", "passes", "pass_accuracy", "passing_accuracy"],
    "key_passes": ["key_passes", "chances_created"],
    "dribbles": ["dribbles", "successful_dribbles", "take_ons"],
    "tackles": ["tackles", "tackles_won"],
    "interceptions": ["interceptions"],
    "minutes": ["minutes", "minutes_played", "mins"],
    "distance": ["distance", "distance_covered", "km"],
    "saves": ["saves", "save_pct", "clean_sheets"],
}


def resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map our logical fields -> the dataset's actual column names."""
    lower = {c.lower(): c for c in df.columns}
    resolved: dict[str, str] = {}
    for key, hints in COLUMN_HINTS.items():
        for h in hints:
            if h in lower:
                resolved[key] = lower[h]
                break
        else:  # partial contains match
            for lc, orig in lower.items():
                if any(h in lc for h in hints):
                    resolved[key] = orig
                    break
    return resolved


def _tag(value, thresholds, labels):
    for t, label in zip(thresholds, labels):
        if value >= t:
            return label
    return None


def build_scouting_text(row: pd.Series, cols: dict[str, str]) -> str:
    """Compose a human-readable style description from one player's stats."""
    def g(key, default=None):
        col = cols.get(key)
        if col is None:
            return default
        val = row.get(col)
        return default if pd.isna(val) else val

    name = g("name", "Unknown player")
    pos = g("position", "player")
    team = g("team", "")
    parts = [f"{name} is a {pos}" + (f" for {team}." if team else ".")]

    # Style tags derived from the numbers.
    style = []
    goals = _to_float(g("goals"))
    assists = _to_float(g("assists"))
    shots = _to_float(g("shots"))
    key_passes = _to_float(g("key_passes"))
    dribbles = _to_float(g("dribbles"))
    tackles = _to_float(g("tackles"))
    interceptions = _to_float(g("interceptions"))
    distance = _to_float(g("distance"))
    saves = _to_float(g("saves"))

    if goals is not None and goals >= 3:
        style.append("a clinical goalscorer")
    elif shots is not None and shots >= 10:
        style.append("a high-volume shooter")
    if assists is not None and assists >= 3:
        style.append("a creative provider")
    elif key_passes is not None and key_passes >= 8:
        style.append("a chance creator")
    if dribbles is not None and dribbles >= 8:
        style.append("a dribbler who beats his man")
    if (tackles or 0) + (interceptions or 0) >= 12:
        style.append("a strong ball-winner")
    if distance is not None and distance >= 90:
        style.append("a high-workload engine who covers huge ground")
    if saves is not None and saves >= 5:
        style.append("a busy, shot-stopping keeper")

    if style:
        parts.append("Playing style: " + ", ".join(style) + ".")

    # Raw numbers so the text stays grounded in real data.
    nums = []
    for label, key in [
        ("goals", "goals"), ("assists", "assists"), ("shots", "shots"),
        ("key passes", "key_passes"), ("dribbles", "dribbles"),
        ("tackles", "tackles"), ("interceptions", "interceptions"),
        ("minutes", "minutes"), ("distance covered (km)", "distance"),
    ]:
        v = g(key)
        if v is not None:
            nums.append(f"{label}: {v}")
    if nums:
        parts.append("Key numbers — " + "; ".join(nums) + ".")

    return " ".join(parts)


def _to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None
