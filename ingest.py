"""Load the FIFA WC 2026 Player Performance dataset into Elasticsearch with a
`semantic_text` scouting field so vector search works with zero embedding code.

Usage:
    python ingest.py                # auto-download from Kaggle via kagglehub
    python ingest.py path/to.csv    # or point at a CSV you already have
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd
from elasticsearch import helpers

from config import INDEX_NAME, get_client
from scouting import build_scouting_text, resolve_columns

KAGGLE_DATASET = "rauffauzanrambe/fifa-world-cup-2026-player-performance-dataset"


def find_csv() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    print("Downloading dataset from Kaggle via kagglehub…")
    import kagglehub

    path = kagglehub.dataset_download(KAGGLE_DATASET)
    csvs = sorted(glob.glob(os.path.join(path, "**", "*.csv"), recursive=True),
                  key=os.path.getsize, reverse=True)
    if not csvs:
        raise SystemExit(f"No CSV found under {path}")
    print(f"Using {csvs[0]}")
    return csvs[0]


def create_index(es):
    if es.indices.exists(index=INDEX_NAME):
        print(f"Deleting existing index {INDEX_NAME}…")
        es.indices.delete(index=INDEX_NAME)
    # `semantic_text` auto-embeds via the deployment's default EIS model at index
    # time — no pipeline, no model deploy, no API keys.
    es.indices.create(
        index=INDEX_NAME,
        mappings={
            # Numeric stat columns are auto-mapped so every stat is queryable in
            # ES|QL tools; we only pin the fields we filter/sort on as keywords.
            "dynamic": True,
            "properties": {
                "name": {"type": "text", "fields": {"kw": {"type": "keyword"}}},
                "player_name": {"type": "keyword"},
                "team": {"type": "keyword"},
                "position": {"type": "keyword"},
                "nationality": {"type": "keyword"},
                "club_name": {"type": "keyword"},
                "preferred_foot": {"type": "keyword"},
                "scouting_text": {"type": "text"},
                "scouting_semantic": {
                    "type": "semantic_text",
                    "inference_id": ".elser-2-elasticsearch",
                },
            },
        },
    )
    print(f"Created index {INDEX_NAME}")


# Columns that are ratings / rates / static attributes — average them across a
# player's matches. Everything else numeric is a counting stat we SUM to a total.
MEAN_HINTS = (
    "rating", "score", "value", "age", "height", "weight", "jersey",
    "accuracy", "percentage", "speed", "contribution", "impact",
    "resistance", "tournament", "_eur", "xg", "xa",
)


def one_row_per_player(df: pd.DataFrame) -> pd.DataFrame:
    """The dataset has one row per player PER MATCH. Collapse to one row per
    player: SUM counting stats into tournament totals, AVERAGE ratings/values,
    and keep the first value for text attributes (team, position, etc.)."""
    key = "player_id" if "player_id" in df.columns else "player_name"
    if key not in df.columns:
        return df
    agg = {}
    for c in df.columns:
        if c == key:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            agg[c] = "mean" if any(h in c.lower() for h in MEAN_HINTS) else "sum"
        else:
            agg[c] = "first"
    return df.groupby(key, as_index=False).agg(agg)


def main():
    csv = find_csv()
    df = pd.read_csv(csv)
    print(f"\nLoaded {len(df)} match-rows. Columns:\n  {list(df.columns)}\n")

    df = one_row_per_player(df)
    print(f"Collapsed to {len(df)} unique players.\n")

    cols = resolve_columns(df)
    print(f"Resolved columns: {cols}\n")
    if "name" not in cols:
        raise SystemExit("Could not find a player-name column — check the CSV headers above.")

    es = get_client()
    create_index(es)

    def gen():
        for _, row in df.iterrows():
            text = build_scouting_text(row, cols)
            src = {k: _clean(row.get(k)) for k in df.columns}
            src["name"] = row.get(cols["name"])
            src["scouting_text"] = text
            src["scouting_semantic"] = text
            yield {"_index": INDEX_NAME, "_source": src}

    print("Indexing (this embeds every player via EIS — give it a minute)…")
    ok, errors = helpers.bulk(es, gen(), request_timeout=300, raise_on_error=False)
    print(f"\n✅ Indexed {ok} players. Errors: {len(errors) if errors else 0}")
    if errors:
        print("First error:", errors[0])


def _clean(v):
    if pd.isna(v):
        return None
    return v.item() if hasattr(v, "item") else v


if __name__ == "__main__":
    main()
