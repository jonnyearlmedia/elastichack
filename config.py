"""Shared config + Elasticsearch client for the Next Man Up scout."""
import os

from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

ES_URL = os.getenv("ES_URL")
ES_API_KEY = os.getenv("ES_API_KEY")
# Kibana endpoint (same project host as ES, usually the ".kb." URL) — needed for
# creating Agent Builder tools/agents via the API.
KIBANA_URL = os.getenv("KIBANA_URL")
# Elastic's default EIS managed chat endpoint. Override in .env if discover.py
# shows a different id on your cluster.
CHAT_INFERENCE_ID = os.getenv("CHAT_INFERENCE_ID", ".rainbow-sprinkles-elastic")
INDEX_NAME = os.getenv("INDEX_NAME", "wc2026_players")


def get_client() -> Elasticsearch:
    if not ES_URL or not ES_API_KEY:
        raise SystemExit(
            "Missing ES_URL / ES_API_KEY. Copy .env.example to .env and fill them in."
        )
    return Elasticsearch(ES_URL, api_key=ES_API_KEY, request_timeout=120)
