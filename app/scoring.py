import re

from rapidfuzz import fuzz

_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return text.lower().strip()


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _acronym(text: str) -> str:
    """First letter of each word: 'Chicken Biriyani' -> 'cb'."""
    return "".join(tok[0] for tok in _tokens(text))


def fuzzy_score(query: str, text: str) -> float:
    """0..1 character/token similarity that tolerates typos & partials."""
    q, t = _normalize(query), _normalize(text)
    if not q or not t:
        return 0.0
    # WRatio blends several fuzzy strategies; token_set_ratio rewards partial-word
    # overlap ('biriyani' -> 'chicken biriyani'). Take the stronger signal.
    return max(fuzz.WRatio(q, t), fuzz.token_set_ratio(q, t)) / 100.0


def acronym_match(query: str, text: str) -> bool:
    """True if the query is the initials of the keyword ('CB' -> Chicken Biriyani)."""
    q = "".join(_tokens(query))
    if len(q) < 2:
        return False
    return q == _acronym(text)


def hybrid_score(
    query: str,
    text: str,
    semantic: float,
    w_semantic: float,
    w_fuzzy: float,
    w_acronym: float,
) -> dict:
    """Blend semantic cosine, fuzzy similarity and an acronym boost into one score."""
    sem = max(0.0, min(1.0, semantic))  # clamp cosine into [0, 1]
    fuz = fuzzy_score(query, text)
    acr = acronym_match(query, text)
    total_w = w_semantic + w_fuzzy + w_acronym
    if total_w <= 0:
        total_w = 1.0
    raw = w_semantic * sem + w_fuzzy * fuz + w_acronym * (1.0 if acr else 0.0)
    return {
        "score": raw / total_w,  # normalized back into [0, 1]
        "semantic_score": sem,
        "fuzzy_score": fuz,
        "acronym_match": acr,
    }
