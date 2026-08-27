def test_keyword_crud_and_reembed(client, ns_name):
    # Bulk add — auto-creates the namespace.
    r = client.post("/keywords", json={"namespace": ns_name, "texts": ["Chicken Biriyani", "Fish Curry"]})
    assert r.status_code == 201
    body = r.json()
    assert body["namespace_created"] is True
    ns_id = body["namespace_id"]
    created = body["created"]
    assert len(created) == 2
    kw_id = created[0]["id"]

    # List
    r = client.get(f"/namespaces/{ns_id}/keywords")
    assert r.status_code == 200 and len(r.json()) == 2

    # Namespace count reflects keywords
    assert client.get(f"/namespaces/{ns_id}").json()["keyword_count"] == 2

    # Get one
    assert client.get(f"/keywords/{kw_id}").status_code == 200

    # Update re-embeds and the new text becomes searchable
    r = client.put(f"/keywords/{kw_id}", json={"text": "Mutton Rogan Josh"})
    assert r.status_code == 200 and r.json()["text"] == "Mutton Rogan Josh"
    hit = client.get("/search", params={"namespace": ns_id, "q": "rogan josh", "top_k": 1}).json()
    assert hit["results"][0]["text"] == "Mutton Rogan Josh"

    # Delete
    assert client.delete(f"/keywords/{kw_id}").status_code == 204
    assert client.get(f"/keywords/{kw_id}").status_code == 404


def test_add_requires_text(client, ns_name):
    assert client.post("/keywords", json={"namespace": ns_name}).status_code == 422
