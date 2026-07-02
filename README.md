# ⚽ Next Man Up — AI Injury Replacement Scout

Built for the **Elastic + AWS Hack Night** (World Cup edition).

> A star goes down injured. You click their name. **Elasticsearch** finds the
> players whose *actual playing style* is closest, and **AWS Bedrock** (via the
> Elastic Inference Service) writes a scouting report on who to start instead.

## The loop the judges are scoring

```
player stats ──► scouting sentence ──(EIS embeds)──► semantic_text ──► Elastic index
"X is injured" ──► Elastic  (filter to position pool  +  kNN style similarity)
                                              │
                                     top-3 look-alikes
                                              │
                        AWS Bedrock (via EIS chat) ──► scouting report
```

- **Elastic** does retrieval: keyword filter + aggregation to build the candidate
  pool, then **semantic / vector (kNN)** search to rank by playing style — using a
  `semantic_text` field that auto-embeds at index time (no embedding code).
- **AWS Bedrock** does generation: the scouting report is written by an
  Elastic-managed LLM running on Bedrock, reached through EIS with just an Elastic
  API key (no boto3, no AWS keys).

## Run it (in the room)

```bash
pip install -r requirements.txt
cp .env.example .env          # paste in ES_URL, ES_API_KEY, KIBANA_URL

python discover.py            # 1. confirm connection + find your EIS chat endpoint id
                              #    (set CHAT_INFERENCE_ID in .env if it differs)
python ingest.py              # 2. download dataset + index it with semantic_text
python agent_builder_setup.py # 3. create the Agent Builder tools + agent
streamlit run app.py          # 4. (optional) the flashy visual demo
```

Point `ingest.py` at a local file instead of Kaggle with:
`python ingest.py path/to/players.csv`

**Presentation:** use `demo_queries.md` — it has the exact vector-search query and
Agent Builder tools to show on screen (that's what the judges ask for).

## Files

| File | Job |
|---|---|
| `config.py` | env + Elasticsearch client |
| `discover.py` | connection check + lists EIS inference endpoints |
| `scouting.py` | turns numeric stats → natural-language style text |
| `ingest.py` | creates the `semantic_text` index and bulk-loads players |
| `scout_engine.py` | Elastic search + Bedrock report (with a safe fallback) |
| `agent_builder_setup.py` | registers the ES|QL tools + Injury Scout agent |
| `app.py` | Streamlit demo UI |
| `demo_queries.md` | copy-paste queries + rubric checklist for the pitch |

## How it maps to the judging rubric

| Judging criterion | Where we hit it |
|---|---|
| Meaningful Elasticsearch (search, aggregations, vector search, **Agent Builder**) | filter/pool + `semantic` vector query + two ES|QL tools + the agent |
| Managed LLM via **AWS Bedrock / EIS** | the agent (and `scout_engine.py`) generate the report through EIS |
| Creativity / novel idea | injury-replacement scout by *playing style*, not stats lookup |
| Solves a real problem | "next man up" is a real manager decision |
| **Must**: serverless Elastic deployment | runs on Elastic Cloud Serverless |

## Data

FIFA World Cup 2026 Player Performance Dataset (Kaggle:
`rauffauzanrambe/fifa-world-cup-2026-player-performance-dataset`). Column names are
auto-detected, so it also works on similar player CSVs.
