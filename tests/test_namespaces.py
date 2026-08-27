def test_namespace_autocreated_on_keyword_add(client, ns_name):
    # Namespace does not exist yet.
    assert ns_name not in {n["name"] for n in client.get("/namespaces").json()}

    # Adding a keyword creates the namespace.
    r = client.post("/keywords", json={"namespace": ns_name, "text": "Chicken Biriyani"})
    assert r.status_code == 201
    body = r.json()
    assert body["namespace"] == ns_name
    assert body["namespace_created"] is True
    ns_id = body["namespace_id"]
    assert ns_name in {n["name"] for n in client.get("/namespaces").json()}

    # Adding another keyword to the same namespace does NOT create a duplicate.
    r2 = client.post("/keywords", json={"namespace": ns_name, "text": "Fish Curry"})
    assert r2.status_code == 201
    assert r2.json()["namespace_created"] is False
    assert r2.json()["namespace_id"] == ns_id

    matches = [n for n in client.get("/namespaces").json() if n["name"] == ns_name]
    assert len(matches) == 1
    assert matches[0]["keyword_count"] == 2


def test_namespace_get_update_delete(client, ns_name):
    ns_id = client.post("/keywords", json={"namespace": ns_name, "text": "x"}).json()["namespace_id"]

    assert client.get(f"/namespaces/{ns_id}").status_code == 200

    r = client.put(f"/namespaces/{ns_id}", json={"description": "sugary"})
    assert r.status_code == 200 and r.json()["description"] == "sugary"

    assert client.delete(f"/namespaces/{ns_id}").status_code == 204
    assert client.get(f"/namespaces/{ns_id}").status_code == 404


def test_get_missing_namespace(client):
    assert client.get("/namespaces/999999").status_code == 404
