"""Run this FIRST in the room. It confirms your connection and prints the exact
EIS inference endpoint ids available on your cluster, so you can set
CHAT_INFERENCE_ID in .env correctly."""
from config import get_client


def main():
    es = get_client()
    # Serverless blocks GET / (es.info), so verify with a supported call instead.
    print("── Inference endpoints (EIS) ──")
    try:
        endpoints = es.inference.get()  # GET _inference
        print("✅ Connected.\n")
        for ep in endpoints.get("endpoints", []):
            print(f"  id={ep.get('inference_id'):<40} task={ep.get('task_type')}")
        print(
            "\n➡️  Put a chat_completion (or completion) id above into "
            "CHAT_INFERENCE_ID in .env"
        )
    except Exception as e:  # noqa: BLE001
        print(f"❌ Could not reach Elasticsearch / list endpoints: {e}")
        print("   Double-check ES_URL (must use '.es.') and ES_API_KEY in .env")


if __name__ == "__main__":
    main()
