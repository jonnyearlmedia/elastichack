"""Run this FIRST in the room. It confirms your connection and prints the exact
EIS inference endpoint ids available on your cluster, so you can set
CHAT_INFERENCE_ID in .env correctly."""
from config import get_client


def main():
    es = get_client()
    info = es.info()
    print(f"✅ Connected to: {info['name']}  (v{info['version']['number']})\n")

    print("── Inference endpoints (EIS) ──")
    try:
        endpoints = es.inference.get()  # GET _inference
        for ep in endpoints.get("endpoints", []):
            print(f"  id={ep.get('inference_id'):<40} task={ep.get('task_type')}")
        print(
            "\n➡️  Put a chat_completion (or completion) id above into "
            "CHAT_INFERENCE_ID in .env"
        )
    except Exception as e:  # noqa: BLE001
        print(f"  Could not list endpoints: {e}")


if __name__ == "__main__":
    main()
