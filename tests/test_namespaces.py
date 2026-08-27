def test_namespace_crud(client):
    # Create
    r = client.post("/namespaces", json={"name": "desserts", "description": "sweet"})
    assert r.status_code == 201
    ns = r.json()
    assert ns["name"] == "desserts"
    assert ns["keyword_count"] == 0
    ns_id = ns["id"]

    # Duplicate name -> 409
    assert client.post("/namespaces", json={"name": "desserts"}).status_code == 409

    # Get
    r = client.get(f"/namespaces/{ns_id}")
    assert r.status_code == 200 and r.json()["description"] == "sweet"

    # List includes it
    names = {n["name"] for n in client.get("/namespaces").json()}
    assert "desserts" in names

    # Update
    r = client.put(f"/namespaces/{ns_id}", json={"description": "sugary"})
    assert r.status_code == 200 and r.json()["description"] == "sugary"

    # Delete
    assert client.delete(f"/namespaces/{ns_id}").status_code == 204
    assert client.get(f"/namespaces/{ns_id}").status_code == 404


def test_get_missing_namespace(client):
    assert client.get("/namespaces/999999").status_code == 404
