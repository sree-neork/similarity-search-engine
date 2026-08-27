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
        # Create (or reuse) the namespace.
        r = client.post("/namespaces", json={"name": "maincourse", "description": "Main course dishes"})
        if r.status_code == 201:
            ns_id = r.json()["id"]
        elif r.status_code == 409:
            ns_id = next(n["id"] for n in client.get("/namespaces").json() if n["name"] == "maincourse")
        else:
            r.raise_for_status()

        print(f"Namespace 'maincourse' id={ns_id}")

        client.post(f"/namespaces/{ns_id}/keywords", json={"texts": KEYWORDS}).raise_for_status()
        print(f"Added {len(KEYWORDS)} keywords.\n")

        for q in QUERIES:
            resp = client.get("/search", params={"namespace": "maincourse", "q": q, "top_k": 3}).json()
            top = resp["results"][0] if resp["results"] else None
            top_str = f'{top["text"]}  (score={top["score"]:.3f})' if top else "<no results>"
            print(f"  q={q!r:18} -> {top_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
