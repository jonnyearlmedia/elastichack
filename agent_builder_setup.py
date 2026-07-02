"""Create the Agent Builder tools + agent that the judges want to see.

This registers two custom ES|QL tools and an "Injury Replacement Scout" agent in
Elastic Agent Builder. The agent's LLM runs on AWS Bedrock via EIS by default.

Run AFTER ingest.py:
    python agent_builder_setup.py

If the API schema differs on your cluster, the printed JSON is exactly what to
paste into the Agent Builder UI (Manage components → Tools / Agents → New).
"""
from __future__ import annotations

import json
import urllib.request

from config import ES_API_KEY, INDEX_NAME, KIBANA_URL

GET_PLAYER_TOOL = {
    "id": "get_player",
    "type": "esql",
    "description": (
        "Look up one player by exact name. Returns their team, position, and a "
        "scouting description of their playing style. Call this first to learn an "
        "injured player's position."
    ),
    "tags": ["soccer", "scout"],
    "configuration": {
        "query": (
            f"FROM {INDEX_NAME} | WHERE name.kw == ?player_name "
            "| KEEP name, team, position, scouting_text | LIMIT 1"
        ),
        "params": {
            "player_name": {"type": "string", "description": "exact player name"}
        },
    },
}

FIND_REPLACEMENTS_TOOL = {
    "id": "find_replacements",
    "type": "esql",
    "description": (
        "Find candidate replacement players who play the SAME position as an "
        "injured player. Returns each candidate's name, team, and scouting "
        "description so you can compare playing styles."
    ),
    "tags": ["soccer", "scout"],
    "configuration": {
        "query": (
            f"FROM {INDEX_NAME} | WHERE position == ?position AND name.kw != ?exclude_name "
            "| KEEP name, team, position, scouting_text | LIMIT 8"
        ),
        "params": {
            "position": {"type": "string", "description": "position to match, e.g. Forward"},
            "exclude_name": {"type": "string", "description": "injured player's name to exclude"},
        },
    },
}

TOP_SCORERS_TOOL = {
    "id": "top_scorers",
    "type": "esql",
    "description": (
        "Leaderboard: the top players at a given position ranked by total goals "
        "scored in the tournament. Use for questions like 'top 5 forwards by goals'."
    ),
    "tags": ["soccer", "scout"],
    "configuration": {
        "query": (
            f"FROM {INDEX_NAME} | WHERE position == ?position "
            "| SORT goals DESC "
            "| KEEP name, team, goals, assists, player_rating | LIMIT ?limit"
        ),
        "params": {
            "position": {"type": "string", "description": "position, e.g. Forward"},
            "limit": {"type": "integer", "description": "how many players to return"},
        },
    },
}

BUDGET_REPLACEMENT_TOOL = {
    "id": "budget_replacement",
    "type": "esql",
    "description": (
        "Moneyball mode: find the best-rated replacement players at a position "
        "whose market value is at or below a budget cap (in euros). Use for "
        "questions like 'who can replace X for under 50 million euros?'."
    ),
    "tags": ["soccer", "scout"],
    "configuration": {
        "query": (
            f"FROM {INDEX_NAME} "
            "| WHERE position == ?position AND market_value_eur <= ?max_value_eur "
            "AND name.kw != ?exclude_name "
            "| SORT player_rating DESC "
            "| KEEP name, team, market_value_eur, player_rating, scouting_text | LIMIT 8"
        ),
        "params": {
            "position": {"type": "string", "description": "position to match, e.g. Forward"},
            "max_value_eur": {"type": "float", "description": "budget cap in euros, e.g. 50000000"},
            "exclude_name": {"type": "string", "description": "injured player's name to exclude"},
        },
    },
}

AGENT = {
    "id": "injury_scout",
    "name": "Injury Replacement Scout",
    "description": "Recommends the best like-for-like replacement when a player is injured.",
    "configuration": {
        "instructions": (
            "You are an expert football scout with four tools:\n"
            "- get_player: look up an injured player's position and playing style.\n"
            "- find_replacements: same-position candidates to compare styles.\n"
            "- top_scorers: leaderboard of top goalscorers at a position.\n"
            "- budget_replacement: best replacements under a market-value cap.\n\n"
            "For a standard 'who replaces X' question: call get_player, then "
            "find_replacements, then recommend the single best like-for-like pick "
            "with a punchy brief (<150 words) — your #1 pick and why, how the team's "
            "shape changes, and one risk. If the user gives a budget, use "
            "budget_replacement. If they ask for a leaderboard, use top_scorers. "
            "Be decisive."
        ),
        "tools": [
            {"tool_ids": [
                "get_player", "find_replacements", "top_scorers", "budget_replacement",
            ]}
        ],
    },
}

TOOLS = [GET_PLAYER_TOOL, FIND_REPLACEMENTS_TOOL, TOP_SCORERS_TOOL, BUDGET_REPLACEMENT_TOOL]


def _req(method: str, path: str, payload: dict | None = None):
    if not KIBANA_URL or not ES_API_KEY:
        raise SystemExit("Set KIBANA_URL and ES_API_KEY in .env first.")
    url = f"{KIBANA_URL.rstrip('/')}/api/agent_builder/{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"ApiKey {ES_API_KEY}",
            "Content-Type": "application/json",
            "kbn-xsrf": "true",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        return r.status, r.read().decode()


def create(kind: str, payload: dict):
    # Delete first so re-runs cleanly replace existing tools/agents.
    try:
        _req("DELETE", f"{kind}/{payload['id']}")
    except Exception:  # noqa: BLE001
        pass
    try:
        status, _ = _req("POST", kind, payload)
        print(f"✅ {kind}: {payload['id']}  (HTTP {status})")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  Could not create {kind} '{payload['id']}' via API: {e}")
        print("   Paste this into the Agent Builder UI instead:")
        print(json.dumps(payload, indent=2))


def main():
    print("Registering Agent Builder tools + agent…\n")
    for tool in TOOLS:
        create("tools", tool)
    create("agents", AGENT)
    print(
        "\nDone. Open Agent Builder in Kibana → chat with 'Injury Replacement "
        "Scout'. Try:\n"
        '  • "Marcus Rashford just got injured, who should start?"\n'
        '  • "Who can replace Marcus Rashford for under 40 million euros?"\n'
        '  • "Top 5 forwards by goals"'
    )


if __name__ == "__main__":
    main()
