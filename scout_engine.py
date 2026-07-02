"""Search (Elastic) + report generation (AWS Bedrock via EIS)."""
from __future__ import annotations

import json
import urllib.request

from config import CHAT_INFERENCE_ID, ES_API_KEY, ES_URL, INDEX_NAME, get_client


def list_players(prefix: str = "", size: int = 50):
    """Autocomplete-style player list for the dropdown."""
    es = get_client()
    query = {"match_all": {}} if not prefix else {
        "match_phrase_prefix": {"name": prefix}
    }
    resp = es.search(index=INDEX_NAME, query=query, size=size,
                     _source=["name", "team", "position"])
    return [h["_source"] for h in resp["hits"]["hits"]]


def get_player(name: str):
    es = get_client()
    resp = es.search(index=INDEX_NAME, size=1,
                     query={"term": {"name.kw": name}})
    hits = resp["hits"]["hits"]
    return hits[0]["_source"] if hits else None


def find_replacements(injured: dict, k: int = 3):
    """Elastic does the work: filter to the same position, exclude the injured
    player, then rank the rest by STYLE similarity via semantic (vector) search.
    """
    es = get_client()
    must_not = [{"term": {"name.kw": injured["name"]}}]
    filters = []
    if injured.get("position"):
        filters.append({"term": {"position": injured["position"]}})

    resp = es.search(
        index=INDEX_NAME,
        size=k,
        query={
            "bool": {
                "must": {
                    "semantic": {
                        "field": "scouting_semantic",
                        "query": injured["scouting_text"],
                    }
                },
                "filter": filters,
                "must_not": must_not,
            }
        },
    )
    return [
        {**h["_source"], "_score": h["_score"]} for h in resp["hits"]["hits"]
    ]


def generate_report(injured: dict, candidates: list[dict]) -> str:
    """AWS Bedrock (via EIS) writes the scouting report. Falls back to a
    deterministic summary so the live demo can never hard-fail."""
    cand_block = "\n".join(
        f"- {c['name']} ({c.get('team','?')}): {c['scouting_text']}"
        for c in candidates
    )
    prompt = (
        "You are a football scout. A key player just got injured and the "
        "manager needs a replacement from the squad pool below.\n\n"
        f"INJURED PLAYER:\n{injured['name']} — {injured['scouting_text']}\n\n"
        f"AVAILABLE REPLACEMENTS (already ranked by style similarity):\n{cand_block}\n\n"
        "Write a punchy scouting brief (max 150 words): name your #1 pick and why, "
        "note how the team's shape changes, and give one risk. Be decisive."
    )

    for attempt in (_via_completion, _via_chat_stream):
        try:
            out = attempt(prompt)
            if out and out.strip():
                return out.strip()
        except Exception as e:  # noqa: BLE001
            print(f"[report] {attempt.__name__} failed: {e}")
    return _fallback(injured, candidates)


def _via_completion(prompt: str) -> str | None:
    es = get_client()
    resp = es.inference.inference(
        inference_id=CHAT_INFERENCE_ID, task_type="completion", input=[prompt]
    )
    body = resp.body if hasattr(resp, "body") else resp
    comp = body.get("completion") if isinstance(body, dict) else None
    if comp:
        return comp[0].get("result")
    return None


def _via_chat_stream(prompt: str) -> str | None:
    """Hit the EIS chat_completion _stream endpoint over stdlib urllib and
    accumulate the SSE deltas."""
    url = f"{ES_URL.rstrip('/')}/_inference/chat_completion/{CHAT_INFERENCE_ID}/_stream"
    payload = json.dumps({"messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Authorization": f"ApiKey {ES_API_KEY}",
                 "Content-Type": "application/json"},
    )
    chunks: list[str] = []
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
        for raw in r:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data in ("", "[DONE]"):
                continue
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            for choice in obj.get("choices", []):
                delta = choice.get("delta", {}).get("content")
                if delta:
                    chunks.append(delta)
    return "".join(chunks) or None


def _fallback(injured: dict, candidates: list[dict]) -> str:
    if not candidates:
        return f"No stylistic replacements found for {injured['name']} in the pool."
    top = candidates[0]
    others = ", ".join(c["name"] for c in candidates[1:]) or "no strong alternatives"
    return (
        f"**Top pick: {top['name']} ({top.get('team','?')}).** Closest match to "
        f"{injured['name']}'s profile by playing style. {top['scouting_text']} "
        f"Backups: {others}. Risk: like-for-like on style, but check match "
        f"fitness and minutes before starting."
    )
