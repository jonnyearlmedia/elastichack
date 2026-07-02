# Demo queries — show these in your 1–2 min presentation

The judging guidance says: *"show the Elasticsearch portion from the queries you
used, the custom tools and agents you built within Agent Builder."* Here's exactly
what to pull up. Run the DSL one in **Kibana → Dev Console**.

## 1. Vector search — the money query (paste in Dev Console)
This is the "why Elastic beats a normal database" moment. It ranks players by
*playing style* using the `semantic_text` field (embedded via EIS at index time).

```
POST wc2026_players/_search
{
  "size": 3,
  "query": {
    "bool": {
      "must": {
        "semantic": {
          "field": "scouting_semantic",
          "query": "a clinical goalscorer and high-volume shooter who leads the line"
        }
      },
      "filter":   [ { "term": { "position": "Forward" } } ],
      "must_not": [ { "term": { "name.kw": "Cristiano Ronaldo" } } ]
    }
  }
}
```

Say: *"There's no keyword for 'plays like this.' Elastic ranked these on the
vector — semantic meaning — not text matching."*

## 2. Agent Builder — the custom ES|QL tools (show in the UI)

**`get_player`**
```
FROM wc2026_players | WHERE name == ?player_name
| KEEP name, team, position, scouting_text | LIMIT 1
```

**`find_replacements`**
```
FROM wc2026_players | WHERE position == ?position AND name != ?exclude_name
| KEEP name, team, position, scouting_text | LIMIT 8
```

## 3. Agent Builder — the agent (show the chat)
Chat with **Injury Replacement Scout**:
> "Cristiano Ronaldo just got injured — who should start instead?"

The agent calls both tools, then AWS Bedrock (via EIS) writes the scouting brief.
Show the tool-call trace — that's the Agent Builder + Bedrock story in one screen.

## Checklist for the judges' rubric
- [x] **Search / aggregations** — the `filter` / position pool
- [x] **Vector search** — query #1 (`semantic`)
- [x] **Agent Builder** — the two ES|QL tools + the agent
- [x] **AWS Bedrock via EIS** — the agent's LLM writes the report
- [x] **Serverless Elastic** — the whole thing runs on your Serverless project
