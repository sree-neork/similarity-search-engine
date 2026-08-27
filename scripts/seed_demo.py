"""Seed a demo namespace and keywords, then run the biriyani query cases.

Usage (with the stack running):
    python scripts/seed_demo.py            # uses http://localhost:8000
    BASE_URL=http://host:8000 python scripts/seed_demo.py
"""

import os
import sys

import httpx

BASE = os.environ.get("BASE_URL", "http://localhost:8000")

KEYWORDS = [
    "Chicken Biriyani",
    "Paneer Butter Masala",
    "Fish Curry",
    "Mutton Rogan Josh",
    "Veg Fried Rice",
]

QUERIES = ["chkn biriyani", "CB", "Chicken", "biriyani"]


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        # Adding keywords auto-creates the namespace if it doesn't exist yet.
        r = client.post("/keywords", json={"namespace": "maincourse", "texts": KEYWORDS})
        r.raise_for_status()
        body = r.json()
        state = "created" if body["namespace_created"] else "reused existing"
        print(f"Namespace 'maincourse' ({state}) id={body['namespace_id']}")
        print(f"Added {len(body['created'])} keywords.\n")

        for q in QUERIES:
            resp = client.get("/search", params={"namespace": "maincourse", "q": q, "top_k": 3}).json()
            top = resp["results"][0] if resp["results"] else None
            top_str = f'{top["text"]}  (score={top["score"]:.3f})' if top else "<no results>"
            print(f"  q={q!r:18} -> {top_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
