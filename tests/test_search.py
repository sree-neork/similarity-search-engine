import pytest

DISHES = ["Chicken Biriyani", "Paneer Butter Masala", "Fish Curry", "Mutton Rogan Josh"]


@pytest.fixture
def maincourse(client, namespace):
    ns_id = namespace["id"]
    client.post(f"/namespaces/{ns_id}/keywords", json={"texts": DISHES}).raise_for_status()
    return namespace


@pytest.mark.parametrize("query", ["chkn biriyani", "CB", "Chicken", "biriyani"])
def test_biriyani_cases_return_chicken_biriyani(client, maincourse, query):
    """The four example cases: misspelling, abbreviation, and two partial/semantic."""
    r = client.get("/search", params={"namespace": maincourse["name"], "q": query, "top_k": 3})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results, f"no results for {query!r}"
    assert results[0]["text"] == "Chicken Biriyani", f"top hit wrong for {query!r}: {results}"


def test_top_k_limits_and_sorted(client, maincourse):
    r = client.get("/search", params={"namespace": maincourse["name"], "q": "curry", "top_k": 2})
    results = r.json()["results"]
    assert len(results) <= 2
    scores = [h["score"] for h in results]
    assert scores == sorted(scores, reverse=True)


def test_namespace_isolation(client):
    """Same keyword in two namespaces must not cross-leak."""
    a = client.post("/namespaces", json={"name": "iso_a"}).json()
    b = client.post("/namespaces", json={"name": "iso_b"}).json()
    client.post(f"/namespaces/{a['id']}/keywords", json={"text": "Chicken Biriyani"}).raise_for_status()
    client.post(f"/namespaces/{b['id']}/keywords", json={"text": "Chocolate Cake"}).raise_for_status()

    res_a = client.get("/search", params={"namespace": "iso_a", "q": "biriyani", "top_k": 5}).json()
    texts_a = {h["text"] for h in res_a["results"]}
    assert "Chicken Biriyani" in texts_a
    assert "Chocolate Cake" not in texts_a


def test_search_by_name_or_id(client, maincourse):
    by_name = client.get("/search", params={"namespace": maincourse["name"], "q": "fish", "top_k": 1}).json()
    by_id = client.get("/search", params={"namespace": maincourse["id"], "q": "fish", "top_k": 1}).json()
    assert by_name["results"][0]["text"] == by_id["results"][0]["text"] == "Fish Curry"


def test_search_missing_namespace(client):
    assert client.get("/search", params={"namespace": "nope", "q": "x"}).status_code == 404
