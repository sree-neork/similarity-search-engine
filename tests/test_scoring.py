from app import scoring


def test_acronym_match():
    assert scoring.acronym_match("CB", "Chicken Biriyani")
    assert scoring.acronym_match("pbm", "Paneer Butter Masala")
    assert not scoring.acronym_match("XY", "Chicken Biriyani")
    assert not scoring.acronym_match("C", "Chicken")  # single char too weak


def test_fuzzy_tolerates_typos_and_partials():
    assert scoring.fuzzy_score("chkn biriyani", "Chicken Biriyani") > 0.6
    assert scoring.fuzzy_score("biriyani", "Chicken Biriyani") > 0.5
    assert scoring.fuzzy_score("pizza", "Chicken Biriyani") < 0.4


def test_hybrid_blends_and_normalizes():
    s = scoring.hybrid_score(
        query="CB", text="Chicken Biriyani", semantic=0.1,
        w_semantic=0.5, w_fuzzy=0.4, w_acronym=0.1,
    )
    assert s["acronym_match"] is True
    assert 0.0 <= s["score"] <= 1.0
