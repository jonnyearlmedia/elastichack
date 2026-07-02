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

AGENT = {
    "id": "injury_scout",
    "name": "Injury Replacement Scout",
    "description": "Recommends the best like-for-like replacement when a player is injured.",
    "configuration": {
        "instructions": (
            "You are an expert football scout. When the user names an injured player:\n"
            "1. Call get_player with that name to get their position and playing style.\n"
            "2. Call find_replacements with that position (and the injured player's name "
            "as exclude_name) to get the candidate pool.\n"
            "3. Compare playing styles and recommend the single best replacement. Give a "
            "punchy brief (<150 words): your #1 pick and why, how the team's shape "
            "changes, and one risk. Be decisive."
        ),
        "tools": [{"tool_ids": ["get_player", "find_replacements"]}],
    },
}


def _post(path: str, payload: dict):
    if not KIBANA_URL or not ES_API_KEY:
        raise SystemExit("Set KIBANA_URL and ES_API_KEY in .env first.")
    url = f"{KIBANA_URL.rstrip('/')}/api/agent_builder/{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"ApiKey {ES_API_KEY}",
            "Content-Type": "application/json",
            "kbn-xsrf": "true",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        return r.status, r.read().decode()


def create(kind: str, payload: dict):
    try:
        status, body = _post(kind, payload)
        print(f"✅ {kind}: {payload['id']}  (HTTP {status})")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  Could not create {kind} '{payload['id']}' via API: {e}")
        print("   Paste this into the Agent Builder UI instead:")
        print(json.dumps(payload, indent=2))


def main():
    print("Registering Agent Builder tools + agent…\n")
    create("tools", GET_PLAYER_TOOL)
    create("tools", FIND_REPLACEMENTS_TOOL)
    create("agents", AGENT)
    print(
        "\nDone. Open Agent Builder in Kibana → chat with 'Injury Replacement "
        "Scout' → try: \"Cristiano Ronaldo just got injured, who should start?\""
    )


if __name__ == "__main__":
    main()
