import pytest

DISHES = ["Chicken Biriyani", "Paneer Butter Masala", "Fish Curry", "Mutton Rogan Josh"]


@pytest.fixture
def maincourse(client, ns_name):
    """Seed a namespace (by name) with the demo dishes and return its name."""
    client.post("/keywords", json={"namespace": ns_name, "texts": DISHES}).raise_for_status()
    return ns_name


@pytest.mark.parametrize("query", ["chkn biriyani", "CB", "Chicken", "biriyani"])
def test_biriyani_cases_return_chicken_biriyani(client, maincourse, query):
    """The four example cases: misspelling, abbreviation, and two partial/semantic."""
    r = client.get("/search", params={"namespace": maincourse, "q": query, "top_k": 3})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results, f"no results for {query!r}"
    assert results[0]["text"] == "Chicken Biriyani", f"top hit wrong for {query!r}: {results}"


def test_top_k_limits_and_sorted(client, maincourse):
    r = client.get("/search", params={"namespace": maincourse, "q": "curry", "top_k": 2})
    results = r.json()["results"]
    assert len(results) <= 2
    scores = [h["score"] for h in results]
    assert scores == sorted(scores, reverse=True)


def test_pagination(client, maincourse):
    # Page 1: first 2 of the 4 dishes, ranked by score.
    p1 = client.get(
        "/search", params={"namespace": maincourse, "q": "curry", "top_k": 2, "offset": 0}
    ).json()
    assert p1["total"] == len(DISHES)
    assert p1["offset"] == 0 and p1["limit"] == 2
    assert p1["count"] == 2 and p1["has_more"] is True

    # Page 2: next 2, no overlap with page 1, and now exhausted.
    p2 = client.get(
        "/search", params={"namespace": maincourse, "q": "curry", "top_k": 2, "offset": 2}
    ).json()
    assert p2["offset"] == 2 and p2["count"] == 2
    assert p2["has_more"] is False

    ids_p1 = {h["keyword_id"] for h in p1["results"]}
    ids_p2 = {h["keyword_id"] for h in p2["results"]}
    assert ids_p1.isdisjoint(ids_p2)

    # Offset past the end yields an empty page.
    p3 = client.get(
        "/search", params={"namespace": maincourse, "q": "curry", "top_k": 2, "offset": 99}
    ).json()
    assert p3["count"] == 0 and p3["results"] == [] and p3["has_more"] is False


def test_namespace_isolation(client):
    """Same query must not cross-leak between namespaces."""
    client.post("/keywords", json={"namespace": "iso_a", "text": "Chicken Biriyani"}).raise_for_status()
    client.post("/keywords", json={"namespace": "iso_b", "text": "Chocolate Cake"}).raise_for_status()

    res_a = client.get("/search", params={"namespace": "iso_a", "q": "biriyani", "top_k": 5}).json()
    texts_a = {h["text"] for h in res_a["results"]}
    assert "Chicken Biriyani" in texts_a
    assert "Chocolate Cake" not in texts_a


def test_search_by_name_or_id(client, maincourse):
    ns_id = next(n["id"] for n in client.get("/namespaces").json() if n["name"] == maincourse)
    by_name = client.get("/search", params={"namespace": maincourse, "q": "fish", "top_k": 1}).json()
    by_id = client.get("/search", params={"namespace": ns_id, "q": "fish", "top_k": 1}).json()
    assert by_name["results"][0]["text"] == by_id["results"][0]["text"] == "Fish Curry"


def test_search_missing_namespace(client):
    assert client.get("/search", params={"namespace": "nope", "q": "x"}).status_code == 404
